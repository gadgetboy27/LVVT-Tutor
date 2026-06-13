from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from app.core.database import get_db
from app.models.quiz import Standard, QuizResult, SavedQuizState
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

    model_config = ConfigDict(from_attributes=True)


def _fallback_quiz_questions(standard: Standard, db: Session, num_questions: int) -> List[QuizQuestion]:
    """Deterministic, non-AI quiz so "Take Quiz" never dead-ends when the vector
    store has no content for a standard or the AI service is unavailable. Builds
    questions from the standard's own metadata and its sibling standards."""
    questions: List[QuizQuestion] = []
    topic = standard.category or "this area"

    # MCQ: identify the standard's subject area among the real categories.
    categories = [c[0] for c in db.query(Standard.category).distinct().all() if c[0]]
    distractor_cats = [c for c in categories if c != standard.category][:3]
    if standard.category and distractor_cats:
        questions.append(QuizQuestion(
            question=f"Which subject area does the '{standard.title}' standard belong to?",
            options=sorted(distractor_cats + [standard.category]),
            correct_answer=standard.category,
            explanation=f"'{standard.title}' is categorised under {standard.category}.",
            difficulty="easy",
        ))

    # MCQ: pick the correct standard title among siblings.
    other_titles = [
        t[0] for t in db.query(Standard.title).filter(Standard.id != standard.id).distinct().all()
        if t[0] and t[0] != standard.title
    ][:3]
    if other_titles:
        questions.append(QuizQuestion(
            question=f"Which LVV standard covers {topic}?",
            options=sorted(other_titles + [standard.title]),
            correct_answer=standard.title,
            explanation=f"{standard.title} is the LVV standard for {topic}.",
            difficulty="easy",
        ))

    # Short-answer recall prompts fill any remaining slots (the frontend renders
    # these as free-text and grades them with its own substring fallback).
    reference = standard.summary or f"the requirements of the {standard.title} standard"
    prompts = [
        f"Describe a key requirement covered by the '{standard.title}' standard.",
        f"Why is the '{standard.title}' standard important for vehicle safety?",
        f"What might cause a modification to fail an inspection under '{standard.title}'?",
        f"Who is responsible for ensuring compliance with the '{standard.title}' standard?",
    ]
    i = 0
    while len(questions) < num_questions and i < len(prompts):
        questions.append(QuizQuestion(
            question=prompts[i],
            options=[],
            correct_answer=reference,
            explanation=f"Refer to the {standard.title} document. {reference}",
            difficulty="medium",
            type="short",
        ))
        i += 1

    return questions[:num_questions] if questions else [QuizQuestion(
        question=f"Describe what the '{standard.title}' standard covers.",
        options=[],
        correct_answer=standard.summary or standard.title,
        explanation=f"Refer to the {standard.title} document.",
        difficulty="medium",
        type="short",
    )]


@router.post("/generate", response_model=QuizGenerateResponse)
def generate_quiz(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db)
):
    standard = db.query(Standard).filter(
        Standard.standard_number == request.standard_number
    ).first()

    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")

    chroma_client = get_chroma_client()
    collection = get_or_create_collection(chroma_client)

    # Scope retrieval to THIS standard's chunks so questions are on-topic.
    results = query_documents(
        collection,
        f"LVV Standard {request.standard_number} requirements specifications",
        n_results=10,
        where={"standard_number": request.standard_number},
    )

    questions = None
    documents = results.get('documents') or []
    if documents and documents[0]:
        context = "\n\n".join(documents[0])
        try:
            questions_data = generate_quiz_questions(
                context,
                request.standard_number,
                request.num_questions
            )
            if questions_data:
                questions = [QuizQuestion(**q) for q in questions_data]
        except Exception as e:
            print(f"AI quiz generation failed for {request.standard_number}: {e}")

    # No indexed content or the AI service failed -> deterministic fallback.
    if not questions:
        questions = _fallback_quiz_questions(standard, db, request.num_questions)

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


class QuizStateRequest(BaseModel):
    state: dict


@router.get("/state")
def get_quiz_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return the user's saved in-progress quiz (or null)."""
    row = db.query(SavedQuizState).filter(
        SavedQuizState.user_id == current_user.id
    ).first()
    return {"state": row.state if row else None}


@router.put("/state")
def save_quiz_state(
    request: QuizStateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upsert the user's in-progress quiz state."""
    row = db.query(SavedQuizState).filter(
        SavedQuizState.user_id == current_user.id
    ).first()
    if row:
        row.state = request.state
    else:
        db.add(SavedQuizState(user_id=current_user.id, state=request.state))
    db.commit()
    return {"ok": True}


@router.delete("/state")
def clear_quiz_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.query(SavedQuizState).filter(
        SavedQuizState.user_id == current_user.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.post("/evaluate-answer", response_model=EvaluateAnswerResponse)
def evaluate_user_answer(
    request: EvaluateAnswerRequest
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
