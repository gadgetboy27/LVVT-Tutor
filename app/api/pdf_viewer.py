from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
import os
from app.core.database import get_db
from app.models.quiz import Standard

router = APIRouter(prefix="/api/pdf", tags=["PDF Viewer"])

PDF_CACHE_DIR = "pdf_cache"


@router.get("/view/{standard_number}")
async def get_pdf_for_viewing(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    
    safe_filename = standard_number.replace("/", "_").replace("\\", "_")
    pdf_path = os.path.join(PDF_CACHE_DIR, f"{safe_filename}.pdf")
    
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"{standard_number}.pdf",
            headers={
                "Content-Disposition": f"inline; filename=\"{standard_number}.pdf\""
            }
        )
    
    if standard.pdf_url:
        return {
            "redirect_url": standard.pdf_url,
            "message": "PDF not cached locally, use original URL"
        }
    
    raise HTTPException(status_code=404, detail="PDF not available")


@router.get("/download/{standard_number}")
async def download_pdf(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    
    safe_filename = standard_number.replace("/", "_").replace("\\", "_")
    pdf_path = os.path.join(PDF_CACHE_DIR, f"{safe_filename}.pdf")
    
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"{standard_number}.pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{standard_number}.pdf\""
            }
        )
    
    raise HTTPException(status_code=404, detail="PDF not cached locally")


@router.get("/available")
async def list_available_pdfs(
    db: Session = Depends(get_db)
):
    if not os.path.exists(PDF_CACHE_DIR):
        return {"pdfs": [], "total": 0}
    
    pdf_files = [f for f in os.listdir(PDF_CACHE_DIR) if f.endswith('.pdf')]
    
    available = []
    for pdf_file in pdf_files:
        std_num = pdf_file.replace('.pdf', '').replace('_', '/')
        standard = db.query(Standard).filter(
            Standard.standard_number.like(f"%{std_num.split('/')[-1]}%")
        ).first()
        
        available.append({
            "filename": pdf_file,
            "standard_number": std_num,
            "title": standard.title if standard else "Unknown",
            "size_kb": os.path.getsize(os.path.join(PDF_CACHE_DIR, pdf_file)) // 1024
        })
    
    return {"pdfs": available, "total": len(available)}


@router.get("/info/{standard_number}")
async def get_pdf_info(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    
    safe_filename = standard_number.replace("/", "_").replace("\\", "_")
    pdf_path = os.path.join(PDF_CACHE_DIR, f"{safe_filename}.pdf")
    
    is_cached = os.path.exists(pdf_path)
    file_size = os.path.getsize(pdf_path) if is_cached else 0
    
    return {
        "standard_number": standard_number,
        "title": standard.title,
        "pdf_url": standard.pdf_url,
        "is_cached_locally": is_cached,
        "file_size_kb": file_size // 1024 if is_cached else None,
        "view_url": f"/api/pdf/view/{standard_number}" if is_cached else standard.pdf_url,
        "download_url": f"/api/pdf/download/{standard_number}" if is_cached else None
    }
