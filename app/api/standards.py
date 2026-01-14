from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.models.quiz import Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.scraping.lvvta_scraper import scrape_lvvta_standards
from app.services.rag.pdf_processor import process_pdf
from app.services.rag.vector_store import (
    get_chroma_client, 
    get_or_create_collection,
    add_documents,
    query_documents
)
from app.services.rag.ai_service import generate_answer_with_citations

router = APIRouter(prefix="/api/standards", tags=["Standards"])


class StandardResponse(BaseModel):
    id: int
    standard_number: str
    title: str
    pdf_url: Optional[str]
    
    class Config:
        from_attributes = True


class QuestionRequest(BaseModel):
    question: str
    standard_number: Optional[str] = None


class AnswerResponse(BaseModel):
    answer: str
    sources: List[dict]


@router.get("/", response_model=List[StandardResponse])
def list_standards(db: Session = Depends(get_db)):
    standards = db.query(Standard).all()
    return standards


@router.post("/update")
def update_standards(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        
        if not existing:
            new_standard = Standard(
                standard_number=std_data['standard_number'],
                title=std_data['title'],
                pdf_url=std_data['pdf_url'],
                last_modified=std_data.get('last_modified')
            )
            db.add(new_standard)
            db.commit()
            should_process = True
        elif std_data.get('last_modified') and existing.last_modified:
            if std_data['last_modified'] > existing.last_modified:
                existing.last_modified = std_data['last_modified']
                db.commit()
                should_process = True
        
        if should_process and std_data.get('pdf_url'):
            try:
                chunks, content_hash = process_pdf(
                    std_data['pdf_url'], 
                    std_data['standard_number']
                )
                
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
