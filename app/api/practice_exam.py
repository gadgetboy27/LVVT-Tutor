from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import math
import random
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.enhanced import PracticeExam, ExamStatus
from app.models.quiz import Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection, query_documents
from app.services.rag.ai_service import generate_quiz_questions
from app.services.quiz.grading import correct_index, is_answer_correct

router = APIRouter(prefix="/api/practice-exam", tags=["Practice Exam"])

# The real LVV Certifier Formal Assessment written test (LVV ORS Chapter 5, 10.3(2)(a)):
# 20 closed-book multiple-choice questions in 30 minutes, at least 15 correct to pass.
FORMAL_MODE = "formal-mock"
FORMAL_QUESTIONS = 20
FORMAL_MINUTES = 30
FORMAL_PASS_CORRECT = 15
FORMAL_PASS_PCT = FORMAL_PASS_CORRECT / FORMAL_QUESTIONS * 100   # 75
LEGACY_PASS_PCT = 80
LATE_GRACE_SECONDS = 30   # network slack before a late submission fails


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


def _generate_formal_questions(db: Session, total: int) -> List[dict]:
    """`total` MCQs spread across standards that have indexed content, so the mock
    covers the whole syllabus the way the real test samples it."""
    collection = get_or_create_collection(get_chroma_client())
    standards = db.query(Standard).all()
    random.shuffle(standards)

    questions: List[dict] = []
    seen = set()
    # Round 1 samples ~5 standards; later rounds top up (across the same standards)
    # when a corpus is small or the AI returned fewer usable questions than asked.
    for round_no in range(3):
        for std in standards:
            need = total - len(questions)
            if need <= 0:
                break
            per_standard = max(3, math.ceil(total / 5)) if round_no == 0 else max(2, need)
            try:
                results = query_documents(
                    collection, f"LVV Standard {std.standard_number} requirements specifications",
                    n_results=8, where={"standard_number": std.standard_number},
                )
                docs = (results.get("documents") or [[]])[0]
                if not docs:
                    continue
                generated = generate_quiz_questions("\n\n".join(docs), std.standard_number, per_standard, exam_style=True)
            except Exception as e:
                print(f"Formal mock: skipping {std.standard_number}: {e}")
                continue
            for q in generated or []:
                text = (q.get("question") or "").strip()
                if len(q.get("options") or []) < 2 or correct_index(q) < 0 or text.lower() in seen:
                    continue
                seen.add(text.lower())
                q["standard_number"] = std.standard_number
                q["standard_title"] = std.title
                questions.append(q)
        if len(questions) >= total:
            break

    random.shuffle(questions)
    questions = questions[:total]
    for i, q in enumerate(questions):
        q["question_id"] = i + 1
    return questions


@router.post("/formal/start")
def start_formal_mock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mock of the real written test: 20 closed-book MCQs, 30 minutes, 15 to pass."""
    questions = _generate_formal_questions(db, FORMAL_QUESTIONS)
    if not questions:
        raise HTTPException(
            status_code=503,
            detail="Couldn't generate exam questions right now (AI service or indexed standards unavailable). Try again shortly.",
        )

    required = min(len(questions), math.ceil(len(questions) * FORMAL_PASS_PCT / 100))
    exam = PracticeExam(
        user_id=current_user.id,
        title="Mock Formal Assessment",
        description=FORMAL_MODE,
        time_limit_minutes=FORMAL_MINUTES,
        total_questions=len(questions),
        standards_included=sorted({q["standard_number"] for q in questions}),
        questions=questions,
        status=ExamStatus.IN_PROGRESS.value,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    hidden = {"correct_answer", "explanation"}   # never ship the answer key to the browser
    return {
        "id": exam.id,
        "title": exam.title,
        "time_limit_minutes": FORMAL_MINUTES,
        "time_remaining_seconds": FORMAL_MINUTES * 60,
        "total_questions": len(questions),
        "required_correct": required,
        "pass_mark_pct": FORMAL_PASS_PCT,
        "questions": [{k: v for k, v in q.items() if k not in hidden} for q in questions],
    }


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
    
    formal = exam.description == FORMAL_MODE
    correct = 0
    results = []
    
    for q in exam.questions:
        q_id = str(q['question_id'])
        user_answer = str(submission.answers.get(q_id, "") or "")
        is_correct = is_answer_correct(q, user_answer)
        if is_correct:
            correct += 1
        results.append({
            "question_id": q['question_id'],
            "question": q.get('question'),
            "options": q.get('options'),
            "standard_number": q.get('standard_number'),
            "user_answer": user_answer,
            "correct_answer": q.get('correct_answer'),
            "explanation": q.get('explanation'),
            "is_correct": is_correct
        })
    
    total = exam.total_questions or 0
    score = (correct / total * 100) if total > 0 else 0

    elapsed = (datetime.utcnow() - exam.started_at.replace(tzinfo=None)).total_seconds()
    timed_out = elapsed > exam.time_limit_minutes * 60 + LATE_GRACE_SECONDS

    if formal:
        required = min(total, math.ceil(total * FORMAL_PASS_PCT / 100))
        passed = correct >= required and not timed_out
    else:
        required = math.ceil(total * LEGACY_PASS_PCT / 100)
        passed = score >= LEGACY_PASS_PCT
    
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
        "total_questions": total,
        "required_correct": required,
        "timed_out": timed_out,
        "results": results,
        "passed": passed
    }


@router.get("/history/all")
async def get_exam_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exams = db.query(PracticeExam).filter(
        PracticeExam.user_id == current_user.id
    ).order_by(PracticeExam.started_at.desc()).limit(20).all()
    
    return [{
        "id": e.id,
        "title": e.title,
        "status": e.status,
        "score": e.score,
        "total_questions": e.total_questions,
        "started_at": e.started_at,
        "completed_at": e.completed_at
    } for e in exams]
