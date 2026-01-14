from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.enhanced import StudyGuideExport
from app.models.quiz import Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection

router = APIRouter(prefix="/api/offline", tags=["Offline Mode"])

EXPORT_DIR = "study_exports"
os.makedirs(EXPORT_DIR, exist_ok=True)


class ExportRequest(BaseModel):
    title: str = "LVV Study Guide"
    standard_numbers: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    include_quizzes: bool = True
    format: str = "json"


@router.post("/export")
async def create_study_guide_export(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        chroma_client = get_chroma_client()
        collection = get_or_create_collection(chroma_client)
        
        standards_to_export = []
        
        if request.standard_numbers:
            standards_to_export = request.standard_numbers
        elif request.categories:
            standards = db.query(Standard).filter(
                Standard.category.in_(request.categories)
            ).all()
            standards_to_export = [s.standard_number for s in standards]
        else:
            standards = db.query(Standard).limit(10).all()
            standards_to_export = [s.standard_number for s in standards]
        
        export_data = {
            "title": request.title,
            "created_at": datetime.utcnow().isoformat(),
            "standards": []
        }
        
        for std_num in standards_to_export:
            results = collection.get(
                where={"standard_number": std_num},
                include=["documents", "metadatas"]
            )
            
            standard_info = db.query(Standard).filter(
                Standard.standard_number == std_num
            ).first()
            
            standard_data = {
                "standard_number": std_num,
                "title": standard_info.title if standard_info else std_num,
                "category": standard_info.category if standard_info else "Unknown",
                "summary": standard_info.summary if standard_info else "",
                "content": results['documents'] if results and results.get('documents') else []
            }
            
            if request.include_quizzes:
                from app.services.rag.ai_service import generate_quiz_questions
                if results and results.get('documents'):
                    content = "\n".join(results['documents'][:3])
                    try:
                        questions = generate_quiz_questions(content, std_num, num_questions=5)
                        standard_data["practice_questions"] = questions
                    except:
                        standard_data["practice_questions"] = []
            
            export_data["standards"].append(standard_data)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"study_guide_{current_user.id}_{timestamp}.json"
        file_path = os.path.join(EXPORT_DIR, filename)
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        export_record = StudyGuideExport(
            user_id=current_user.id,
            title=request.title,
            standards_included=standards_to_export,
            format=request.format,
            file_path=file_path,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        db.add(export_record)
        db.commit()
        db.refresh(export_record)
        
        return {
            "export_id": export_record.id,
            "download_url": f"/api/offline/download/{export_record.id}",
            "standards_included": len(standards_to_export),
            "expires_at": export_record.expires_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{export_id}")
async def download_study_guide(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    export = db.query(StudyGuideExport).filter(
        StudyGuideExport.id == export_id,
        StudyGuideExport.user_id == current_user.id
    ).first()
    
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    
    if export.expires_at and export.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Export has expired")
    
    if not os.path.exists(export.file_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    
    export.download_count += 1
    db.commit()
    
    return FileResponse(
        export.file_path,
        media_type="application/json",
        filename=f"{export.title.replace(' ', '_')}.json"
    )


@router.get("/my-exports")
async def list_my_exports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exports = db.query(StudyGuideExport).filter(
        StudyGuideExport.user_id == current_user.id
    ).order_by(StudyGuideExport.created_at.desc()).limit(20).all()
    
    return [{
        "id": e.id,
        "title": e.title,
        "standards_count": len(e.standards_included) if e.standards_included else 0,
        "download_count": e.download_count,
        "created_at": e.created_at,
        "expires_at": e.expires_at,
        "is_expired": e.expires_at < datetime.utcnow() if e.expires_at else False
    } for e in exports]


@router.delete("/{export_id}")
async def delete_export(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    export = db.query(StudyGuideExport).filter(
        StudyGuideExport.id == export_id,
        StudyGuideExport.user_id == current_user.id
    ).first()
    
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    
    if os.path.exists(export.file_path):
        os.remove(export.file_path)
    
    db.delete(export)
    db.commit()
    
    return {"message": "Export deleted"}


@router.get("/quick-reference/{category}")
async def get_quick_reference(
    category: str,
    db: Session = Depends(get_db)
):
    standards = db.query(Standard).filter(
        Standard.category == category
    ).all()
    
    quick_ref = []
    for s in standards:
        quick_ref.append({
            "standard_number": s.standard_number,
            "title": s.title,
            "summary": s.summary or "No summary available"
        })
    
    return {
        "category": category,
        "standards": quick_ref,
        "total": len(quick_ref)
    }
