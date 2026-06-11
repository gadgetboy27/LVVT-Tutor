from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import get_db
from app.models.quiz import Standard
from app.services.rag.vector_store import (
    get_chroma_client,
    get_or_create_collection,
    query_documents,
)
from app.services.rag.ai_service import build_teach_tree, evaluate_teachback

router = APIRouter(prefix="/api/teach", tags=["Teach-Back"])


class EvaluateTeachbackRequest(BaseModel):
    standard_number: str
    topic: str
    explanation: str
    key_points: Optional[List[str]] = None


def _standard_context(standard: Standard, query: str, n_results: int = 8) -> str:
    """Grounded source text for a standard: vector chunks scoped to that standard
    first, falling back to the stored full text / section summaries. This is the
    ONLY ground truth the teach-back grader is allowed to use."""
    try:
        collection = get_or_create_collection(get_chroma_client())
        results = query_documents(
            collection, query, n_results=n_results,
            where={"standard_number": standard.standard_number},
        )
        documents = results.get("documents") or []
        if documents and documents[0]:
            return "\n\n".join(documents[0])
    except Exception:
        pass

    parts: List[str] = []
    if standard.full_text:
        parts.append(standard.full_text[:6000])
    for section in standard.sections:
        if section.summary:
            parts.append(f"{section.section_title}: {section.summary}")
    if standard.summary:
        parts.append(standard.summary)
    return "\n\n".join(parts)


@router.get("/tree/{standard_number}")
def get_teach_tree(standard_number: str, db: Session = Depends(get_db)):
    """Break a standard into 'explain it in your own words' aspects."""
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")

    context = _standard_context(
        standard, f"key requirements and processes of {standard.title}"
    )
    aspects = build_teach_tree(standard.standard_number, standard.title, context)
    return {
        "standard_number": standard.standard_number,
        "title": standard.title,
        "aspects": aspects,
        "grounded": bool(context),
    }


@router.post("/evaluate")
def evaluate_explanation(
    request: EvaluateTeachbackRequest,
    db: Session = Depends(get_db)
):
    """Grade the trainee's own-words explanation against the standard's source."""
    standard = db.query(Standard).filter(
        Standard.standard_number == request.standard_number
    ).first()
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    if not request.explanation or not request.explanation.strip():
        raise HTTPException(status_code=400, detail="Explanation is required")

    # Retrieve excerpts specific to the topic being explained, within this standard.
    context = _standard_context(standard, request.topic or standard.title)

    return evaluate_teachback(
        topic=request.topic or standard.title,
        learner_explanation=request.explanation,
        context=context,
        standard_number=standard.standard_number,
        key_points=request.key_points,
    )
