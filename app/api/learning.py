from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.models.quiz import Standard, StandardSection, SectionMastery
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag.ai_service import lookup_competency, generate_section_quiz

router = APIRouter(prefix="/api/learning", tags=["Learning"])


class SectionProgress(BaseModel):
    section_id: int
    section_title: str
    summary: Optional[str]
    mastery_score: int
    is_mastered: bool
    status: str


class TeachingSessionResponse(BaseModel):
    standard_number: str
    title: str
    category: str
    summary: Optional[str]
    sections: List[SectionProgress]
    overall_completion: float


class CompetencyRequest(BaseModel):
    skill: str


class CompetencyResponse(BaseModel):
    skill: str
    explanation: str


class SectionQuizRequest(BaseModel):
    section_id: int
    num_questions: int = 5


class SectionQuizSubmitRequest(BaseModel):
    section_id: int
    answers: dict
    total_questions: int
    correct_answers: int


class MasteryResponse(BaseModel):
    section_id: int
    score: int
    is_mastered: bool
    status: str


CORE_COMPETENCIES = [
    "High level of integrity",
    "Technically skilled",
    "Vastly experienced",
    "Conscientious",
    "Independent",
    "Reliable",
    "Good people skills"
]


@router.get("/competencies", response_model=List[str])
def list_competencies():
    return CORE_COMPETENCIES


@router.post("/competency", response_model=CompetencyResponse)
def get_competency_explanation(
    request: CompetencyRequest,
    current_user: User = Depends(get_current_user)
):
    explanation = lookup_competency(request.skill)
    return CompetencyResponse(skill=request.skill, explanation=explanation)


@router.get("/teaching/{standard_number}", response_model=TeachingSessionResponse)
def start_teaching_session(
    standard_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    
    sections_progress = []
    mastered_count = 0
    
    for section in standard.sections:
        mastery = db.query(SectionMastery).filter(
            SectionMastery.user_id == current_user.id,
            SectionMastery.section_id == section.id
        ).first()
        
        mastery_score = mastery.mastery_score if mastery else 0
        is_mastered = mastery.is_mastered if mastery else False
        
        if is_mastered:
            mastered_count += 1
            status = "MASTERED"
        elif mastery_score > 0:
            status = "IN_PROGRESS"
        else:
            status = "PENDING"
        
        sections_progress.append(SectionProgress(
            section_id=section.id,
            section_title=section.section_title,
            summary=section.summary,
            mastery_score=mastery_score,
            is_mastered=is_mastered,
            status=status
        ))
    
    total_sections = len(standard.sections)
    completion = (mastered_count / total_sections * 100) if total_sections > 0 else 0
    
    return TeachingSessionResponse(
        standard_number=standard.standard_number,
        title=standard.title,
        category=standard.category or "General",
        summary=standard.summary,
        sections=sections_progress,
        overall_completion=completion
    )


@router.post("/section-quiz")
def generate_section_quiz_endpoint(
    request: SectionQuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    section = db.query(StandardSection).filter(
        StandardSection.id == request.section_id
    ).first()
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    standard = db.query(Standard).filter(Standard.id == section.standard_id).first()
    
    content = section.content or section.summary or ""
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Section has no content for quiz generation"
        )
    
    questions = generate_section_quiz(
        content,
        section.section_title,
        standard.standard_number if standard else "Unknown",
        request.num_questions
    )
    
    return {
        "section_id": section.id,
        "section_title": section.section_title,
        "standard_number": standard.standard_number if standard else "Unknown",
        "questions": questions
    }


@router.post("/section-quiz/submit", response_model=MasteryResponse)
def submit_section_quiz(
    request: SectionQuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    section = db.query(StandardSection).filter(
        StandardSection.id == request.section_id
    ).first()
    
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    score = int((request.correct_answers / request.total_questions) * 100) if request.total_questions > 0 else 0
    is_mastered = score >= 80
    
    mastery = db.query(SectionMastery).filter(
        SectionMastery.user_id == current_user.id,
        SectionMastery.section_id == section.id
    ).first()
    
    if mastery:
        if score > mastery.mastery_score:
            mastery.mastery_score = score
        mastery.attempts += 1
        mastery.is_mastered = mastery.is_mastered or is_mastered
    else:
        mastery = SectionMastery(
            user_id=current_user.id,
            standard_id=section.standard_id,
            section_id=section.id,
            mastery_score=score,
            attempts=1,
            is_mastered=is_mastered
        )
        db.add(mastery)
    
    db.commit()
    db.refresh(mastery)
    
    status = "MASTERED" if mastery.is_mastered else ("PASSED" if score >= 80 else "FAILED")
    
    return MasteryResponse(
        section_id=section.id,
        score=score,
        is_mastered=mastery.is_mastered,
        status=status
    )


@router.get("/progress/summary")
def get_progress_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    masteries = db.query(SectionMastery).filter(
        SectionMastery.user_id == current_user.id
    ).all()
    
    total_sections = db.query(StandardSection).count()
    mastered_sections = sum(1 for m in masteries if m.is_mastered)
    
    standards_progress = {}
    for mastery in masteries:
        std_id = mastery.standard_id
        if std_id not in standards_progress:
            standards_progress[std_id] = {"mastered": 0, "total": 0}
        standards_progress[std_id]["mastered"] += 1 if mastery.is_mastered else 0
        standards_progress[std_id]["total"] += 1
    
    return {
        "total_sections": total_sections,
        "mastered_sections": mastered_sections,
        "overall_percentage": (mastered_sections / total_sections * 100) if total_sections > 0 else 0,
        "standards_progress": standards_progress
    }
