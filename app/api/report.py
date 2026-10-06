"""Report card: turns a user's past quiz results into per-subject strengths and
weaknesses, with study hints drawn from the questions they actually missed.

Unlocks after MIN_QUIZZES completed quizzes. Subjects at or below WEAK_MAX are
flagged and each gets a "practice" target the frontend can launch as a fresh quiz.
Completed Mock Formal Assessments also feed the per-standard figures and get
their own summary against the real pass mark.

WEAK_MAX sits just under the real Formal Assessment pass mark (15/20 = 75%, LVV ORS
Chapter 5, 10.3(2)(a)): anything that would not pass the real test is flagged.
"""
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enhanced import PracticeExam, ExamStatus
from app.models.quiz import QuizResult, Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.quiz.grading import is_answer_correct
from app.api.practice_exam import FORMAL_MODE, FORMAL_PASS_CORRECT, FORMAL_QUESTIONS

router = APIRouter(prefix="/api/report", tags=["Report Card"])

MIN_QUIZZES = 5
PASS_MARK = 75.0      # real Formal Assessment written test: 15 of 20
WEAK_MAX = 74.0       # below the pass mark => needs work
MASTERY_MIN = 80.0
MIN_EXAM_QUESTIONS_PER_STANDARD = 2   # too few questions on a standard says little
MAX_MISSED_PER_SUBJECT = 5


@dataclass
class _Entry:
    """One scored attempt on a standard — a quiz result or a standard's slice of a
    mock exam — in the shape the helpers below need."""
    score: float
    answers: Any
    created_at: Any


def _when(dt: Optional[datetime]) -> datetime:
    """Naive-UTC timestamp usable as a sort key whether the DB gave aware or naive."""
    if dt is None:
        return datetime.min
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _exam_entries(exam: PracticeExam) -> Dict[str, "_Entry"]:
    """Split a completed mock exam into per-standard attempts, with each missed
    question in the same shape quiz answers use."""
    per: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"right": 0, "n": 0, "answers": []})
    given = exam.answers if isinstance(exam.answers, dict) else {}
    for q in exam.questions or []:
        sn = q.get("standard_number")
        if not sn:
            continue
        ua = str(given.get(str(q.get("question_id")), "") or "")
        ok = is_answer_correct(q, ua)
        bucket = per[sn]
        bucket["n"] += 1
        bucket["right"] += ok
        if not ok:
            bucket["answers"].append({
                "question": q.get("question"),
                "userAnswer": ua,
                "correctAnswer": q.get("correct_answer", ""),
                "isCorrect": False,
                "explanation": q.get("explanation", ""),
            })
    return {
        sn: _Entry(b["right"] / b["n"] * 100, b["answers"], exam.completed_at or exam.started_at)
        for sn, b in per.items() if b["n"] >= MIN_EXAM_QUESTIONS_PER_STANDARD
    }


def letter_grade(pct: float) -> str:
    for cutoff, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if pct >= cutoff:
            return grade
    return "F"


def _avg(values: List[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _missed_questions(results: List[Any]) -> List[dict]:
    """Missed questions across a set of results (oldest-first input), newest first, de-duplicated."""
    seen, missed = set(), []
    for r in reversed(results):
        answers = r.answers if isinstance(r.answers, list) else []
        for a in answers:
            if not isinstance(a, dict) or a.get("isCorrect", a.get("is_correct", True)):
                continue
            q = a.get("question")
            if not q or q in seen:
                continue
            seen.add(q)
            missed.append({
                "question": q,
                "your_answer": a.get("userAnswer", ""),
                "correct_answer": a.get("correctAnswer", ""),
                "hint": a.get("explanation", ""),
            })
    return missed[:MAX_MISSED_PER_SUBJECT]


def _subject_stats(label: str, results: List[Any]) -> dict:
    # `results` arrive oldest-first (see build_report_card's query ordering).
    scores = [r.score for r in results]
    avg = _avg(scores)
    return {
        "name": label,
        "attempts": len(scores),
        "average": avg,
        "latest": round(scores[-1], 1),
        "grade": letter_grade(avg),
        "is_weak": avg <= WEAK_MAX,
        "improving": len(scores) >= 2 and scores[-1] > scores[0],
    }


def _study_hint(subject: dict, standard: Optional[Standard]) -> str:
    where = f"Re-read '{standard.title}'" if standard else f"Review the {subject['name']} standards"
    if subject["average"] < 40:
        return f"{where} from the start, then retake a quiz — the fundamentals aren't sticking yet."
    if subject["improving"]:
        return f"You're trending up. {where} once more, focusing on the questions you missed below."
    return f"{where} and focus on the questions you missed below, then try a fresh quiz."


def _mock_exam_summary(exams: List[PracticeExam]) -> dict:
    """Mock Formal Assessments against the real pass mark (15 of 20)."""
    attempts = [{
        "score": round(e.score or 0, 1),
        "correct": e.correct_answers or 0,
        "total": e.total_questions or 0,
        "passed": (e.correct_answers or 0) >= min(e.total_questions or 0,
                                                  math.ceil((e.total_questions or 0) * PASS_MARK / 100)),
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
    } for e in exams[-5:]]
    return {
        "attempts": len(exams),
        "pass_rule": f"{FORMAL_PASS_CORRECT} of {FORMAL_QUESTIONS} correct in 30 minutes",
        "best": max((e.score or 0 for e in exams), default=None),
        "recent": list(reversed(attempts)),
        "passes": sum(a["passed"] for a in attempts),
    }


def build_report_card(user: User, db: Session) -> dict:
    results: List[QuizResult] = (
        db.query(QuizResult).filter(QuizResult.user_id == user.id)
        .order_by(QuizResult.created_at.asc(), QuizResult.id.asc()).all()
    )
    total = len(results)
    if total < MIN_QUIZZES:
        return {
            "eligible": False,
            "quizzes_completed": total,
            "quizzes_needed": MIN_QUIZZES - total,
            "min_quizzes": MIN_QUIZZES,
        }

    standards: Dict[int, Standard] = {s.id: s for s in db.query(Standard).all()}
    by_number = {s.standard_number: s for s in standards.values()}
    overall = _avg([r.score for r in results])

    exams: List[PracticeExam] = (
        db.query(PracticeExam)
        .filter(PracticeExam.user_id == user.id, PracticeExam.status == ExamStatus.COMPLETED.value,
                PracticeExam.description == FORMAL_MODE)
        .order_by(PracticeExam.completed_at.asc()).all()
    )

    by_standard: Dict[int, List[Any]] = defaultdict(list)
    by_category: Dict[str, List[Any]] = defaultdict(list)

    def add(std: Optional[Standard], entry: Any):
        if std:
            by_standard[std.id].append(entry)
            by_category[std.category or "Uncategorized"].append(entry)

    for r in results:
        add(standards.get(r.standard_id), r)
    for exam in exams:
        for sn, entry in _exam_entries(exam).items():
            add(by_number.get(sn), entry)

    # Per-standard breakdown is what drives practice targets; categories give the
    # big-picture "which subject area" view.
    standard_rows = []
    for sid, rs in by_standard.items():
        rs.sort(key=lambda e: _when(e.created_at))
        std = standards[sid]
        row = _subject_stats(std.title, rs)
        row.update({"standard_number": std.standard_number, "category": std.category})
        if row["is_weak"]:
            row["missed_questions"] = _missed_questions(rs)
            row["hint"] = _study_hint(row, std)
        standard_rows.append(row)
    standard_rows.sort(key=lambda r: r["average"])

    category_rows = sorted(
        (_subject_stats(cat, sorted(rs, key=lambda e: _when(e.created_at))) for cat, rs in by_category.items()),
        key=lambda r: r["average"],
    )

    recent = [r.score for r in results[-MIN_QUIZZES:]]
    earlier = [r.score for r in results[:-MIN_QUIZZES]]
    trend = None
    if earlier:
        diff = round(_avg(recent) - _avg(earlier), 1)
        trend = {"change": diff, "direction": "up" if diff > 0 else "down" if diff < 0 else "flat"}

    weak = [r for r in standard_rows if r["is_weak"]]
    strong = [r for r in standard_rows if r["average"] >= MASTERY_MIN]
    needs_support = overall <= WEAK_MAX

    if needs_support:
        summary = (f"Your average is {overall}% across {total} quizzes — below the {int(PASS_MARK)}% "
                   "you'd need to pass the real written test. Focus on the subjects below, using the "
                   "hints from questions you missed.")
    elif weak:
        summary = (f"Solid overall ({overall}%), but {len(weak)} standard(s) are below the "
                   f"{int(PASS_MARK)}% real-exam pass mark. Targeted practice there will round you out.")
    else:
        summary = f"Great work — {overall}% overall with no weak subjects."

    return {
        "eligible": True,
        "quizzes_completed": total,
        "overall_average": overall,
        "grade": letter_grade(overall),
        "needs_support": needs_support,
        "summary": summary,
        "trend": trend,
        "pass_mark": PASS_MARK,
        "weak_threshold": WEAK_MAX,
        "mock_exams": _mock_exam_summary(exams),
        "categories": category_rows,
        "standards": standard_rows,
        "focus_areas": weak,
        "strengths": [{"name": s["name"], "average": s["average"]} for s in strong],
    }


@router.get("/card")
def report_card(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return build_report_card(current_user, db)
