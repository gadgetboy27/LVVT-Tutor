import os
import requests
import hashlib
from typing import List, Dict, Optional
from PyPDF2 import PdfReader
from io import BytesIO
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection, add_documents
from app.core.database import SessionLocal
from app.models.quiz import Standard, StandardSection

PDF_CACHE_DIR = "./pdf_cache"

def ensure_cache_dir():
    os.makedirs(PDF_CACHE_DIR, exist_ok=True)

def download_pdf(url: str) -> Optional[bytes]:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

def extract_text_from_pdf(pdf_content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    if not text:
        return []
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks

def index_pdf_to_vectordb(standard_number: str, title: str, pdf_url: str, category: str) -> Dict:
    ensure_cache_dir()
    
    url_hash = hashlib.md5(pdf_url.encode()).hexdigest()[:8]
    cache_path = os.path.join(PDF_CACHE_DIR, f"{url_hash}.pdf")
    
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            pdf_content = f.read()
    else:
        pdf_content = download_pdf(pdf_url)
        if pdf_content:
            with open(cache_path, 'wb') as f:
                f.write(pdf_content)
    
    if not pdf_content:
        return {"success": False, "error": "Failed to download PDF"}
    
    text = extract_text_from_pdf(pdf_content)
    if not text:
        return {"success": False, "error": "Failed to extract text from PDF"}
    
    chunks = chunk_text(text)
    if not chunks:
        return {"success": False, "error": "No text chunks extracted"}
    
    client = get_chroma_client()
    collection = get_or_create_collection(client)
    
    documents = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        doc_id = f"{standard_number}_chunk_{i}"
        documents.append(chunk)
        metadatas.append({
            "standard_number": standard_number,
            "title": title,
            "category": category,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "pdf_url": pdf_url
        })
        ids.append(doc_id)
    
    add_documents(collection, documents, metadatas, ids)
    
    return {
        "success": True,
        "chunks_indexed": len(chunks),
        "text_length": len(text)
    }

def index_all_standards() -> Dict:
    db = SessionLocal()
    results = {"indexed": 0, "failed": 0, "errors": []}
    
    try:
        standards = db.query(Standard).filter(Standard.is_processed == False).all()
        
        for std in standards:
            if not std.pdf_url:
                continue
                
            print(f"Indexing: {std.title}")
            result = index_pdf_to_vectordb(
                std.standard_number,
                std.title,
                std.pdf_url,
                std.category or "General"
            )
            
            if result["success"]:
                std.is_processed = True
                std.full_text = f"Indexed {result['chunks_indexed']} chunks"
                results["indexed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{std.title}: {result.get('error')}")
        
        db.commit()
    except Exception as e:
        results["errors"].append(str(e))
        db.rollback()
    finally:
        db.close()
    
    return results

ORS_CHAPTERS = [
    {
        "number": "ORS_Chapter_2",
        "title": "Low Volume Vehicle Classifications",
        "url": "https://www.lvvta.org.nz/documents/operating_requirements_schedule/LVVTA_Operating_Requirements_Schedule_Chapter_2_Low_Volume_Vehicle_Classifications.pdf",
        "category": "Certification Process"
    },
    {
        "number": "ORS_Chapter_3",
        "title": "LVV Certification Categories",
        "url": "https://www.lvvta.org.nz/documents/operating_requirements_schedule/LVVTA_Operating_Requirements_Schedule_Chapter_3_LVV_Certification_Categories.pdf",
        "category": "Certification Process"
    },
    {
        "number": "ORS_Chapter_4",
        "title": "LVV Certifier Background Criteria",
        "url": "https://www.lvvta.org.nz/documents/operating_requirements_schedule/LVVTA_Operating_Requirements_Schedule_Chapter_4_LVV_Certifier_Background_Criteria.pdf",
        "category": "Certification Process"
    },
    {
        "number": "ORS_Chapter_5",
        "title": "LVV Certifier Application and Appointment",
        "url": "https://www.lvvta.org.nz/documents/operating_requirements_schedule/LVVTA_Operating_Requirements_Schedule_Chapter_5_LVV_Certifier_Application_Appointment.pdf",
        "category": "Certification Process"
    },
    {
        "number": "ORS_Full",
        "title": "Complete Operating Requirements Schedule",
        "url": "https://www.lvvta.org.nz/documents/operating_requirements_schedule/LVVTA_Operating_Requirements_Schedule.pdf",
        "category": "Certification Process"
    }
]

def index_ors_chapters() -> Dict:
    db = SessionLocal()
    results = {"indexed": 0, "failed": 0, "details": []}
    
    try:
        for ors in ORS_CHAPTERS:
            existing = db.query(Standard).filter(Standard.standard_number == ors["number"]).first()
            if not existing:
                new_std = Standard(
                    standard_number=ors["number"],
                    title=ors["title"],
                    pdf_url=ors["url"],
                    category=ors["category"],
                    summary=f"Operating Requirements Schedule - {ors['title']}",
                    is_processed=False
                )
                db.add(new_std)
                db.commit()
            
            print(f"Indexing ORS: {ors['title']}")
            result = index_pdf_to_vectordb(
                ors["number"],
                ors["title"],
                ors["url"],
                ors["category"]
            )
            
            if result["success"]:
                if existing:
                    existing.is_processed = True
                results["indexed"] += 1
                results["details"].append(f"{ors['title']}: {result['chunks_indexed']} chunks")
            else:
                results["failed"] += 1
                results["details"].append(f"{ors['title']}: FAILED - {result.get('error')}")
        
        db.commit()
    except Exception as e:
        results["details"].append(f"Error: {str(e)}")
        db.rollback()
    finally:
        db.close()
    
    return results
