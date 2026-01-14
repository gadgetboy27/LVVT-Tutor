from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.enhanced import SpacedRepetitionCard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection
from app.services.rag.ai_service import generate_quiz_questions

router = APIRouter(prefix="/api/spaced-repetition", tags=["Spaced Repetition"])


class CardCreate(BaseModel):
    standard_number: str
    question: str
    answer: str
    source_chunk: Optional[str] = None


class CardReview(BaseModel):
    card_id: int
    quality: int


class GenerateCardsRequest(BaseModel):
    standard_number: str
    num_cards: int = 5


@router.get("/due")
async def get_due_cards(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.utcnow()
    cards = db.query(SpacedRepetitionCard).filter(
        SpacedRepetitionCard.user_id == current_user.id,
        SpacedRepetitionCard.next_review <= now
    ).order_by(SpacedRepetitionCard.next_review).limit(limit).all()
    
    return [{
        "id": c.id,
        "standard_number": c.standard_number,
        "question": c.question,
        "answer": c.answer,
        "repetitions": c.repetitions,
        "interval_days": c.interval_days
    } for c in cards]


@router.post("/review")
async def review_card(
    review: CardReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = db.query(SpacedRepetitionCard).filter(
        SpacedRepetitionCard.id == review.card_id,
        SpacedRepetitionCard.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    quality = max(0, min(5, review.quality))
    
    if quality < 3:
        card.repetitions = 0
        card.interval_days = 1
    else:
        if card.repetitions == 0:
            card.interval_days = 1
        elif card.repetitions == 1:
            card.interval_days = 6
        else:
            card.interval_days = int(card.interval_days * card.ease_factor)
        
        card.repetitions += 1
    
    card.ease_factor = max(1.3, card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    card.last_review = datetime.utcnow()
    card.next_review = datetime.utcnow() + timedelta(days=card.interval_days)
    
    db.commit()
    
    return {
        "card_id": card.id,
        "next_review": card.next_review,
        "interval_days": card.interval_days,
        "ease_factor": card.ease_factor
    }


@router.post("/generate")
async def generate_cards_from_standard(
    request: GenerateCardsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        chroma_client = get_chroma_client()
        collection = get_or_create_collection(chroma_client)
        
        results = collection.get(
            where={"standard_number": request.standard_number},
            include=["documents"],
            limit=5
        )
        
        if not results or not results.get('documents'):
            raise HTTPException(status_code=404, detail="No content found for this standard")
        
        content = "\n".join(results['documents'][:5])
        questions = generate_quiz_questions(content, request.standard_number, num_questions=request.num_cards)
        
        created_cards = []
        for q in questions:
            card = SpacedRepetitionCard(
                user_id=current_user.id,
                standard_number=request.standard_number,
                question=q.get('question', ''),
                answer=q.get('correct_answer', ''),
                source_chunk=content[:500]
            )
            db.add(card)
            created_cards.append(card)
        
        db.commit()
        
        return {
            "cards_created": len(created_cards),
            "standard_number": request.standard_number
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_card(
    card_data: CardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = SpacedRepetitionCard(
        user_id=current_user.id,
        standard_number=card_data.standard_number,
        question=card_data.question,
        answer=card_data.answer,
        source_chunk=card_data.source_chunk
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    
    return {"id": card.id, "message": "Card created successfully"}


@router.get("/stats")
async def get_study_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total_cards = db.query(SpacedRepetitionCard).filter(
        SpacedRepetitionCard.user_id == current_user.id
    ).count()
    
    due_now = db.query(SpacedRepetitionCard).filter(
        SpacedRepetitionCard.user_id == current_user.id,
        SpacedRepetitionCard.next_review <= datetime.utcnow()
    ).count()
    
    mastered = db.query(SpacedRepetitionCard).filter(
        SpacedRepetitionCard.user_id == current_user.id,
        SpacedRepetitionCard.interval_days >= 21
    ).count()
    
    return {
        "total_cards": total_cards,
        "due_now": due_now,
        "mastered": mastered,
        "learning": total_cards - mastered
    }


@router.delete("/{card_id}")
async def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = db.query(SpacedRepetitionCard).filter(
        SpacedRepetitionCard.id == card_id,
        SpacedRepetitionCard.user_id == current_user.id
    ).first()
    
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    db.delete(card)
    db.commit()
    
    return {"message": "Card deleted"}
