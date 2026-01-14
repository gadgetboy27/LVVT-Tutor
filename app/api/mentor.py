from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.models.enhanced import Mentor, MentorshipRequest, MentorStatus
from app.models.user import User
from app.services.auth.jwt import get_current_user

router = APIRouter(prefix="/api/mentors", tags=["Mentors"])


class MentorCreate(BaseModel):
    name: str
    email: str
    bio: Optional[str] = None
    specializations: Optional[List[str]] = None
    years_experience: int = 10
    certification_categories: Optional[List[str]] = None


class MentorshipRequestCreate(BaseModel):
    mentor_id: int
    message: Optional[str] = None


@router.get("/")
async def list_mentors(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Mentor).filter(Mentor.status == MentorStatus.AVAILABLE.value)
    
    mentors = query.all()
    
    if category:
        mentors = [m for m in mentors if m.certification_categories and category in m.certification_categories]
    
    return [{
        "id": m.id,
        "name": m.name,
        "bio": m.bio,
        "specializations": m.specializations,
        "years_experience": m.years_experience,
        "certification_categories": m.certification_categories,
        "rating": m.rating,
        "total_mentees": m.total_mentees,
        "status": m.status
    } for m in mentors]


@router.get("/{mentor_id}")
async def get_mentor(
    mentor_id: int,
    db: Session = Depends(get_db)
):
    mentor = db.query(Mentor).filter(Mentor.id == mentor_id).first()
    
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    return {
        "id": mentor.id,
        "name": mentor.name,
        "email": mentor.email,
        "bio": mentor.bio,
        "specializations": mentor.specializations,
        "years_experience": mentor.years_experience,
        "certification_categories": mentor.certification_categories,
        "rating": mentor.rating,
        "total_mentees": mentor.total_mentees,
        "status": mentor.status
    }


@router.post("/request")
async def request_mentorship(
    request: MentorshipRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mentor = db.query(Mentor).filter(Mentor.id == request.mentor_id).first()
    
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    existing = db.query(MentorshipRequest).filter(
        MentorshipRequest.trainee_id == current_user.id,
        MentorshipRequest.mentor_id == request.mentor_id,
        MentorshipRequest.status == "pending"
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending request with this mentor")
    
    mentorship_request = MentorshipRequest(
        trainee_id=current_user.id,
        mentor_id=request.mentor_id,
        message=request.message
    )
    db.add(mentorship_request)
    db.commit()
    
    return {"message": "Mentorship request sent", "request_id": mentorship_request.id}


@router.get("/my-requests/")
async def get_my_mentorship_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    requests = db.query(MentorshipRequest).filter(
        MentorshipRequest.trainee_id == current_user.id
    ).all()
    
    result = []
    for r in requests:
        mentor = db.query(Mentor).filter(Mentor.id == r.mentor_id).first()
        result.append({
            "id": r.id,
            "mentor_name": mentor.name if mentor else "Unknown",
            "status": r.status,
            "message": r.message,
            "created_at": r.created_at,
            "responded_at": r.responded_at
        })
    
    return result


@router.post("/register")
async def register_as_mentor(
    mentor_data: MentorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="You are already registered as a mentor")
    
    mentor = Mentor(
        user_id=current_user.id,
        name=mentor_data.name,
        email=mentor_data.email,
        bio=mentor_data.bio,
        specializations=mentor_data.specializations,
        years_experience=mentor_data.years_experience,
        certification_categories=mentor_data.certification_categories
    )
    db.add(mentor)
    db.commit()
    db.refresh(mentor)
    
    return {"message": "Successfully registered as mentor", "mentor_id": mentor.id}


@router.put("/status/{status}")
async def update_mentor_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mentor = db.query(Mentor).filter(Mentor.user_id == current_user.id).first()
    
    if not mentor:
        raise HTTPException(status_code=404, detail="You are not registered as a mentor")
    
    if status not in [s.value for s in MentorStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    mentor.status = status
    db.commit()
    
    return {"message": f"Status updated to {status}"}
