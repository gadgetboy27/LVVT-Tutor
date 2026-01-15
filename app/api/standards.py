from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.models.quiz import Standard, StandardSection
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.scraping.lvvta_scraper import scrape_lvvta_standards, categorize_by_topic
from app.services.rag.pdf_processor import process_pdf
from app.services.rag.vector_store import (
    get_chroma_client, 
    get_or_create_collection,
    add_documents,
    query_documents
)
from app.services.rag.ai_service import generate_answer_with_citations, summarize_and_categorize

router = APIRouter(prefix="/api/standards", tags=["Standards"])


class StandardResponse(BaseModel):
    id: int
    standard_number: str
    title: str
    category: Optional[str]
    summary: Optional[str]
    pdf_url: Optional[str]
    is_processed: bool
    
    class Config:
        from_attributes = True


class StandardDetailResponse(BaseModel):
    id: int
    standard_number: str
    title: str
    category: Optional[str]
    summary: Optional[str]
    pdf_url: Optional[str]
    sections: List[dict]
    
    class Config:
        from_attributes = True


class QuestionRequest(BaseModel):
    question: str
    standard_number: Optional[str] = None


class AnswerResponse(BaseModel):
    answer: str
    sources: List[dict]


class SearchRequest(BaseModel):
    query: str


class SearchResult(BaseModel):
    type: str
    title: str
    document: Optional[str]
    result: str


@router.get("/", response_model=List[StandardResponse])
def list_standards(db: Session = Depends(get_db)):
    standards = db.query(Standard).all()
    return standards


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    categories = db.query(Standard.category).distinct().all()
    cat_list = [c[0] for c in categories if c[0]]
    response = JSONResponse(content=cat_list)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/by-category/{category}")
def get_standards_by_category(
    category: str,
    db: Session = Depends(get_db)
):
    standards = db.query(Standard).filter(
        Standard.category == category
    ).all()
    return standards


@router.get("/content/{standard_number}")
def get_standard_content(
    standard_number: str,
    db: Session = Depends(get_db)
):
    try:
        chroma_client = get_chroma_client()
        collection = get_or_create_collection(chroma_client)
        
        results = collection.get(
            where={"standard_number": standard_number},
            include=["documents", "metadatas"]
        )
        
        if results and results.get('documents'):
            chunks = results['documents']
            return {
                "standard_number": standard_number,
                "content": "\n\n".join(chunks),
                "chunks": chunks,
                "total_chunks": len(chunks)
            }
        
        standard = db.query(Standard).filter(
            Standard.standard_number == standard_number
        ).first()
        
        if standard and standard.full_text:
            return {
                "standard_number": standard_number,
                "content": standard.full_text,
                "chunks": [standard.full_text],
                "total_chunks": 1
            }
        
        raise HTTPException(status_code=404, detail="Content not indexed yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{standard_number}", response_model=StandardDetailResponse)
def get_standard_detail(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    
    sections = [
        {
            "id": s.id,
            "title": s.section_title,
            "summary": s.summary
        }
        for s in standard.sections
    ]
    
    return StandardDetailResponse(
        id=standard.id,
        standard_number=standard.standard_number,
        title=standard.title,
        category=standard.category,
        summary=standard.summary,
        pdf_url=standard.pdf_url,
        sections=sections
    )


@router.post("/update")
def update_standards(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    background_tasks.add_task(sync_standards_background, db)
    return {"message": "Standards update started in background"}


def sync_standards_background(db: Session):
    scraped = scrape_lvvta_standards()
    chroma_client = get_chroma_client()
    collection = get_or_create_collection(chroma_client)
    
    for std_data in scraped:
        existing = db.query(Standard).filter(
            Standard.standard_number == std_data['standard_number']
        ).first()
        
        should_process = False
        standard = existing
        
        if not existing:
            category = categorize_by_topic(std_data['title'])
            new_standard = Standard(
                standard_number=std_data['standard_number'],
                title=std_data['title'],
                pdf_url=std_data['pdf_url'],
                category=category,
                last_modified=std_data.get('last_modified')
            )
            db.add(new_standard)
            db.commit()
            db.refresh(new_standard)
            standard = new_standard
            should_process = True
        elif std_data.get('last_modified') and existing.last_modified:
            if std_data['last_modified'] > existing.last_modified:
                existing.last_modified = std_data['last_modified']
                db.commit()
                should_process = True
        elif not existing.is_processed:
            should_process = True
        
        if should_process and std_data.get('pdf_url'):
            try:
                chunks, content_hash = process_pdf(
                    std_data['pdf_url'], 
                    std_data['standard_number']
                )
                
                full_text = "\n".join([chunk['text'] for chunk in chunks])
                
                ai_result = summarize_and_categorize(full_text, std_data['title'])
                
                standard.summary = ai_result.get('summary', '')
                if ai_result.get('category'):
                    standard.category = ai_result['category']
                standard.full_text = full_text[:50000]
                standard.content_hash = content_hash
                standard.is_processed = True
                
                for idx, section_data in enumerate(ai_result.get('sections', [])):
                    section = StandardSection(
                        standard_id=standard.id,
                        section_title=section_data.get('title', f'Section {idx+1}'),
                        summary=section_data.get('summary', ''),
                        order_index=idx
                    )
                    db.add(section)
                
                db.commit()
                
                documents = [chunk['text'] for chunk in chunks]
                metadatas = [
                    {
                        'standard_number': chunk['standard_number'],
                        'chunk_id': chunk['id'],
                        'source_url': chunk['source_url']
                    } 
                    for chunk in chunks
                ]
                ids = [
                    f"{std_data['standard_number']}_chunk_{chunk['id']}" 
                    for chunk in chunks
                ]
                
                add_documents(collection, documents, metadatas, ids)
                
            except Exception as e:
                print(f"Error processing {std_data['standard_number']}: {e}")


@router.post("/search", response_model=List[SearchResult])
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = request.query.lower()
    results = []
    
    standards = db.query(Standard).all()
    for doc in standards:
        if query in doc.title.lower() or (doc.summary and query in doc.summary.lower()):
            results.append(SearchResult(
                type="Document Summary",
                title=doc.title,
                document=None,
                result=doc.summary or doc.title
            ))
        
        for section in doc.sections:
            section_text = (section.section_title + " " + (section.summary or "")).lower()
            if query in section_text:
                results.append(SearchResult(
                    type="Section Summary",
                    title=section.section_title,
                    document=doc.title,
                    result=section.summary or section.section_title
                ))
    
    return results


@router.post("/ask", response_model=AnswerResponse)
def ask_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user)
):
    chroma_client = get_chroma_client()
    collection = get_or_create_collection(chroma_client)
    
    results = query_documents(collection, request.question, n_results=5)
    
    if not results['documents'] or not results['documents'][0]:
        raise HTTPException(
            status_code=404,
            detail="No relevant information found. Please ensure standards have been indexed."
        )
    
    context_chunks = []
    for i, doc in enumerate(results['documents'][0]):
        metadata = results['metadatas'][0][i] if results['metadatas'] else {}
        context_chunks.append({
            'text': doc,
            'standard_number': metadata.get('standard_number', 'Unknown'),
            'id': metadata.get('chunk_id', i)
        })
    
    answer = generate_answer_with_citations(request.question, context_chunks)
    
    sources = [
        {
            'standard_number': chunk['standard_number'],
            'chunk_id': chunk['id']
        } 
        for chunk in context_chunks
    ]
    
    return AnswerResponse(answer=answer, sources=sources)
