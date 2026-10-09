import threading
from collections import Counter
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.pdf_viewer import _ensure_cached_pdf
from app.core.database import SessionLocal, get_db
from app.models.quiz import Standard
from app.models.study import StudyPoint
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag import study_guide

router = APIRouter(prefix="/api/study", tags=["Study Guide"])

_generating: set = set()
_failed: Dict[str, str] = {}
_lock = threading.Lock()

NOTE = ("Passages are selected by AI as the most test-relevant. Every quote is checked against the official "
        "PDF and shown with its page. LVVTA does not publish what is examined, so the ranking is a judgement, "
        "not inside knowledge of the exam — the official document remains the authority.")


def _get_standard(standard_number: str, db: Session) -> Standard:
    std = db.query(Standard).filter(Standard.standard_number == standard_number).first()
    if not std:
        raise HTTPException(status_code=404, detail="Standard not found")
    return std


@router.get("/{standard_number}")
def get_study_guide(standard_number: str, db: Session = Depends(get_db)):
    std = _get_standard(standard_number, db)
    points = (db.query(StudyPoint).filter(StudyPoint.standard_id == std.id)
              .order_by(StudyPoint.page, StudyPoint.importance, StudyPoint.id).all())

    if standard_number in _generating:
        status = "generating"
    elif not points:
        status = "failed" if standard_number in _failed else "missing"
    else:
        built = points[0].source_hash
        # content_hash is a sha256 when the indexer set it; older rows hold other hashes.
        stale = bool(built and std.content_hash and len(std.content_hash) == 64 and std.content_hash != built)
        status = "outdated" if stale else "ready"

    return {
        "standard_number": std.standard_number,
        "title": std.title,
        "status": status,
        "error": _failed.get(standard_number),
        "note": NOTE,
        "original_pdf": f"/api/pdf/view/{std.standard_number}",
        "counts": dict(Counter(p.importance for p in points)),
        "pages_with_points": sorted({p.page for p in points}),
        "points": [{"id": p.id, "page": p.page, "category": p.category, "importance": p.importance,
                    "point": p.point, "quote": p.quote, "section": p.section or ""} for p in points],
    }


def _generate(standard_number: str):
    db = SessionLocal()
    try:
        std = db.query(Standard).filter(Standard.standard_number == standard_number).first()
        path = _ensure_cached_pdf(std) if std else None
        if not path:
            _failed[standard_number] = "The source PDF isn't available for this standard."
            return
        with open(path, "rb") as f:
            guide = study_guide.build_guide(f.read(), std.title, study_guide.default_llm())
        if guide["stats"]["windows"] and guide["stats"]["failed_windows"] == guide["stats"]["windows"]:
            _failed[standard_number] = "The AI service didn't respond. Try again shortly."
            return
        study_guide.replace_points(db, std.id, guide)
        _failed.pop(standard_number, None)
    except Exception as e:
        db.rollback()
        _failed[standard_number] = f"Couldn't build the study notes: {e}"
    finally:
        db.close()
        with _lock:
            _generating.discard(standard_number)


@router.post("/{standard_number}/generate")
def generate_study_guide(standard_number: str, background_tasks: BackgroundTasks,
                         db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Build (or rebuild) the study notes for one standard. Costs AI calls, so it needs a login
    and only one build per standard runs at a time."""
    _get_standard(standard_number, db)
    with _lock:
        if standard_number in _generating:
            return {"status": "generating"}
        _generating.add(standard_number)
        _failed.pop(standard_number, None)
    background_tasks.add_task(_generate, standard_number)
    return {"status": "generating"}
