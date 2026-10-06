"""Report card: turns a user's past quiz results into per-subject strengths and
weaknesses, with study hints drawn from the questions they actually missed.

Unlocks after MIN_QUIZZES completed quizzes. Subjects at or below WEAK_MAX
(69%) are flagged and each gets a "practice" target the frontend can launch as a
fresh quiz.
"""
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.quiz import QuizResult, Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user

router = APIRouter(prefix="/api/report", tags=["Report Card"])

MIN_QUIZZES = 5
WEAK_MAX = 69.0       # 69% or less => needs work
MASTERY_MIN = 80.0
MAX_MISSED_PER_SUBJECT = 5


def letter_grade(pct: float) -> str:
    for cutoff, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if pct >= cutoff:
            return grade
    return "F"


def _avg(values: List[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _missed_questions(results: List[QuizResult]) -> List[dict]:
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


def _subject_stats(label: str, results: List[QuizResult]) -> dict:
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
    overall = _avg([r.score for r in results])

    by_standard: Dict[int, List[QuizResult]] = defaultdict(list)
    by_category: Dict[str, List[QuizResult]] = defaultdict(list)
    for r in results:
        std = standards.get(r.standard_id)
        if not std:
            continue
        by_standard[std.id].append(r)
        by_category[std.category or "Uncategorized"].append(r)

    # Per-standard breakdown is what drives practice targets; categories give the
    # big-picture "which subject area" view.
    standard_rows = []
    for sid, rs in by_standard.items():
        std = standards[sid]
        row = _subject_stats(std.title, rs)
        row.update({"standard_number": std.standard_number, "category": std.category})
        if row["is_weak"]:
            row["missed_questions"] = _missed_questions(rs)
            row["hint"] = _study_hint(row, std)
        standard_rows.append(row)
    standard_rows.sort(key=lambda r: r["average"])

    category_rows = sorted(
        (_subject_stats(cat, rs) for cat, rs in by_category.items()),
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
        summary = (f"Your average is {overall}% across {total} quizzes. Below are the subjects "
                   "to focus on, with hints from questions you missed.")
    elif weak:
        summary = (f"Solid overall ({overall}%), but {len(weak)} standard(s) are at or below "
                   f"{int(WEAK_MAX)}%. Targeted practice there will round you out.")
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
        "weak_threshold": WEAK_MAX,
        "categories": category_rows,
        "standards": standard_rows,
        "focus_areas": weak,
        "strengths": [{"name": s["name"], "average": s["average"]} for s in strong],
    }


@router.get("/card")
def report_card(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return build_report_card(current_user, db)
