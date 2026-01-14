from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.models.quiz import Standard, QuizResult
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag.vector_store import (
    get_chroma_client,
    get_or_create_collection,
    query_documents
)
from app.services.rag.ai_service import generate_quiz_questions

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: str


class QuizGenerateRequest(BaseModel):
    standard_number: str
    num_questions: int = 5


class QuizGenerateResponse(BaseModel):
    standard_number: str
    questions: List[QuizQuestion]


class QuizSubmitRequest(BaseModel):
    standard_number: str
    answers: dict


class QuizResultResponse(BaseModel):
    id: int
    score: float
    total_questions: int
    correct_answers: int
    
    class Config:
        from_attributes = True


@router.post("/generate", response_model=QuizGenerateResponse)
def generate_quiz(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == request.standard_number
    ).first()
    
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    
    chroma_client = get_chroma_client()
    collection = get_or_create_collection(chroma_client)
    
    results = query_documents(
        collection, 
        f"LVV Standard {request.standard_number} requirements specifications", 
        n_results=10
    )
    
    if not results['documents'] or not results['documents'][0]:
        raise HTTPException(
            status_code=404,
            detail="No content found for this standard. Please ensure it has been indexed."
        )
    
    context = "\n\n".join(results['documents'][0])
    
    questions_data = generate_quiz_questions(
        context, 
        request.standard_number, 
        request.num_questions
    )
    
    if not questions_data:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate quiz questions"
        )
    
    questions = [QuizQuestion(**q) for q in questions_data]
    
    return QuizGenerateResponse(
        standard_number=request.standard_number,
        questions=questions
    )


@router.post("/submit", response_model=QuizResultResponse)
def submit_quiz(
    request: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == request.standard_number
    ).first()
    
    total_questions = len(request.answers)
    correct_answers = sum(1 for q, a in request.answers.items() if a.get('is_correct', False))
    score = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    
    result = QuizResult(
        user_id=current_user.id,
        standard_id=standard.id if standard else None,
        score=score,
        total_questions=total_questions,
        correct_answers=correct_answers,
        answers=request.answers
    )
    
    db.add(result)
    db.commit()
    db.refresh(result)
    
    return result


@router.get("/history", response_model=List[QuizResultResponse])
def get_quiz_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = db.query(QuizResult).filter(
        QuizResult.user_id == current_user.id
    ).order_by(QuizResult.created_at.desc()).limit(20).all()
    
    return results
