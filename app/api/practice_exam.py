from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.enhanced import PracticeExam, ExamStatus
from app.models.quiz import Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection
from app.services.rag.ai_service import generate_quiz_questions

router = APIRouter(prefix="/api/practice-exam", tags=["Practice Exam"])


class ExamConfig(BaseModel):
    title: str = "Practice Certification Exam"
    time_limit_minutes: int = 60
    num_questions: int = 20
    categories: Optional[List[str]] = None
    standard_numbers: Optional[List[str]] = None


class ExamResponse(BaseModel):
    id: int
    title: str
    time_limit_minutes: int
    total_questions: int
    started_at: datetime
    time_remaining_seconds: int
    questions: List[dict]


class SubmitExamRequest(BaseModel):
    exam_id: int
    answers: dict


@router.post("/start", response_model=ExamResponse)
async def start_practice_exam(
    config: ExamConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        chroma_client = get_chroma_client()
        collection = get_or_create_collection(chroma_client)
        
        standards_to_include = []
        
        if config.standard_numbers:
            standards_to_include = config.standard_numbers
        elif config.categories:
            standards = db.query(Standard).filter(
                Standard.category.in_(config.categories)
            ).all()
            standards_to_include = [s.standard_number for s in standards]
        else:
            standards = db.query(Standard).limit(10).all()
            standards_to_include = [s.standard_number for s in standards]
        
        all_questions = []
        questions_per_standard = max(1, config.num_questions // len(standards_to_include)) if standards_to_include else config.num_questions
        
        for std_num in standards_to_include[:5]:
            results = collection.get(
                where={"standard_number": std_num},
                include=["documents"],
                limit=3
            )
            
            if results and results.get('documents'):
                content = "\n".join(results['documents'][:3])
                questions = generate_quiz_questions(content, std_num, num_questions=questions_per_standard)
                for q in questions:
                    q['standard_number'] = std_num
                all_questions.extend(questions)
        
        all_questions = all_questions[:config.num_questions]
        
        for i, q in enumerate(all_questions):
            q['question_id'] = i + 1
        
        exam = PracticeExam(
            user_id=current_user.id,
            title=config.title,
            time_limit_minutes=config.time_limit_minutes,
            total_questions=len(all_questions),
            standards_included=standards_to_include,
            questions=all_questions,
            status=ExamStatus.IN_PROGRESS.value
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
        
        time_remaining = config.time_limit_minutes * 60
        
        return ExamResponse(
            id=exam.id,
            title=exam.title,
            time_limit_minutes=exam.time_limit_minutes,
            total_questions=len(all_questions),
            started_at=exam.started_at,
            time_remaining_seconds=time_remaining,
            questions=[{k: v for k, v in q.items() if k != 'correct_answer'} for q in all_questions]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{exam_id}")
async def get_exam_status(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exam = db.query(PracticeExam).filter(
        PracticeExam.id == exam_id,
        PracticeExam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    elapsed = (datetime.utcnow() - exam.started_at.replace(tzinfo=None)).total_seconds()
    time_remaining = max(0, (exam.time_limit_minutes * 60) - elapsed)
    
    if time_remaining <= 0 and exam.status == ExamStatus.IN_PROGRESS.value:
        exam.status = ExamStatus.EXPIRED.value
        db.commit()
    
    return {
        "id": exam.id,
        "title": exam.title,
        "status": exam.status,
        "time_remaining_seconds": int(time_remaining),
        "total_questions": exam.total_questions,
        "score": exam.score
    }


@router.post("/submit")
async def submit_practice_exam(
    submission: SubmitExamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exam = db.query(PracticeExam).filter(
        PracticeExam.id == submission.exam_id,
        PracticeExam.user_id == current_user.id
    ).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    if exam.status == ExamStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Exam already submitted")
    
    correct = 0
    results = []
    
    for q in exam.questions:
        q_id = str(q['question_id'])
        user_answer = submission.answers.get(q_id, "")
        is_correct = user_answer.lower().strip() == q.get('correct_answer', '').lower().strip()
        if is_correct:
            correct += 1
        results.append({
            "question_id": q['question_id'],
            "user_answer": user_answer,
            "correct_answer": q.get('correct_answer'),
            "is_correct": is_correct
        })
    
    score = (correct / exam.total_questions * 100) if exam.total_questions > 0 else 0
    
    exam.answers = submission.answers
    exam.correct_answers = correct
    exam.score = score
    exam.status = ExamStatus.COMPLETED.value
    exam.completed_at = datetime.utcnow()
    db.commit()
    
    return {
        "exam_id": exam.id,
        "score": score,
        "correct_answers": correct,
        "total_questions": exam.total_questions,
        "results": results,
        "passed": score >= 80
    }


@router.get("/history/all")
async def get_exam_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exams = db.query(PracticeExam).filter(
        PracticeExam.user_id == current_user.id
    ).order_by(PracticeExam.created_at.desc()).limit(20).all()
    
    return [{
        "id": e.id,
        "title": e.title,
        "status": e.status,
        "score": e.score,
        "total_questions": e.total_questions,
        "started_at": e.started_at,
        "completed_at": e.completed_at
    } for e in exams]
