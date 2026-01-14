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
from app.services.rag.ai_service import generate_quiz_questions, evaluate_answer

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: str
    difficulty: str = "medium"
    type: str = "MCQ"


class QuizGenerateRequest(BaseModel):
    standard_number: str
    num_questions: int = 5


class QuizGenerateResponse(BaseModel):
    standard_number: str
    questions: List[QuizQuestion]


class QuizSubmitRequest(BaseModel):
    standard_number: str
    score: float = 0
    total_questions: int = 0
    correct_answers: int = 0
    answers: dict = {}


class EvaluateAnswerRequest(BaseModel):
    question: str
    user_answer: str
    correct_answer: str
    difficulty: str = "medium"
    standard_number: str


class EvaluateAnswerResponse(BaseModel):
    is_correct: bool
    score: int
    explanation: str
    citation: str = ""


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
    
    total_questions = request.total_questions if request.total_questions > 0 else len(request.answers)
    correct_answers = request.correct_answers if request.correct_answers > 0 else sum(
        1 for q, a in request.answers.items() if a.get('is_correct', False)
    )
    score = request.score if request.score > 0 else (
        (correct_answers / total_questions * 100) if total_questions > 0 else 0
    )
    
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


@router.post("/evaluate-answer", response_model=EvaluateAnswerResponse)
def evaluate_user_answer(
    request: EvaluateAnswerRequest,
    current_user: User = Depends(get_current_user)
):
    result = evaluate_answer(
        question=request.question,
        user_answer=request.user_answer,
        correct_answer=request.correct_answer,
        difficulty=request.difficulty,
        standard_number=request.standard_number
    )
    
    return EvaluateAnswerResponse(
        is_correct=result.get("is_correct", False),
        score=result.get("score", 0),
        explanation=result.get("explanation", ""),
        citation=result.get("citation", "")
    )
