from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, desc
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.enhanced import PeerStats
from app.models.quiz import QuizResult, SectionMastery
from app.models.user import User
from app.services.auth.jwt import get_current_user

router = APIRouter(prefix="/api/peers", tags=["Peer Comparison"])


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    stats = db.query(PeerStats).order_by(
        desc(PeerStats.average_score),
        desc(PeerStats.standards_mastered)
    ).limit(limit).all()
    
    leaderboard = []
    for i, s in enumerate(stats):
        leaderboard.append({
            "rank": i + 1,
            "anonymous_id": f"Trainee_{s.user_id % 1000:03d}",
            "average_score": round(s.average_score, 1),
            "standards_mastered": s.standards_mastered,
            "exams_completed": s.exams_completed,
            "study_streak": s.study_streak_days
        })
    
    return leaderboard


@router.get("/my-ranking")
async def get_my_ranking(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    my_stats = db.query(PeerStats).filter(
        PeerStats.user_id == current_user.id
    ).first()
    
    if not my_stats:
        my_stats = await update_user_stats(current_user.id, db)
    
    total_users = db.query(PeerStats).count()
    users_below = db.query(PeerStats).filter(
        PeerStats.average_score < my_stats.average_score
    ).count()
    
    percentile = (users_below / total_users * 100) if total_users > 0 else 50
    
    rank = db.query(PeerStats).filter(
        PeerStats.average_score > my_stats.average_score
    ).count() + 1
    
    return {
        "rank": rank,
        "total_users": total_users,
        "percentile": round(percentile, 1),
        "average_score": round(my_stats.average_score, 1),
        "standards_mastered": my_stats.standards_mastered,
        "exams_completed": my_stats.exams_completed,
        "study_streak": my_stats.study_streak_days
    }


@router.post("/update-stats")
async def refresh_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stats = await update_user_stats(current_user.id, db)
    return {
        "message": "Stats updated",
        "average_score": stats.average_score,
        "standards_mastered": stats.standards_mastered
    }


async def update_user_stats(user_id: int, db: Session) -> PeerStats:
    quiz_stats = db.query(
        sql_func.count(QuizResult.id).label('total_quizzes'),
        sql_func.sum(QuizResult.correct_answers).label('total_correct'),
        sql_func.sum(QuizResult.total_questions).label('total_questions'),
        sql_func.avg(QuizResult.score).label('avg_score')
    ).filter(QuizResult.user_id == user_id).first()
    
    mastered_count = db.query(SectionMastery).filter(
        SectionMastery.user_id == user_id,
        SectionMastery.is_mastered == True
    ).count()
    
    stats = db.query(PeerStats).filter(PeerStats.user_id == user_id).first()
    
    if not stats:
        stats = PeerStats(user_id=user_id)
        db.add(stats)
    
    stats.total_quizzes = quiz_stats.total_quizzes or 0
    stats.total_correct = int(quiz_stats.total_correct or 0)
    stats.total_questions = int(quiz_stats.total_questions or 0)
    stats.average_score = float(quiz_stats.avg_score or 0)
    stats.standards_mastered = mastered_count
    
    if stats.last_study_date:
        if stats.last_study_date.date() == (datetime.utcnow() - timedelta(days=1)).date():
            stats.study_streak_days += 1
        elif stats.last_study_date.date() != datetime.utcnow().date():
            stats.study_streak_days = 1
    else:
        stats.study_streak_days = 1
    
    stats.last_study_date = datetime.utcnow()
    
    db.commit()
    db.refresh(stats)
    
    return stats


@router.get("/category-rankings/{category}")
async def get_category_rankings(
    category: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    from app.models.quiz import Standard
    
    standards_in_category = db.query(Standard.id).filter(
        Standard.category == category
    ).all()
    standard_ids = [s[0] for s in standards_in_category]
    
    if not standard_ids:
        return []
    
    user_scores = db.query(
        QuizResult.user_id,
        sql_func.avg(QuizResult.score).label('avg_score'),
        sql_func.count(QuizResult.id).label('quiz_count')
    ).filter(
        QuizResult.standard_id.in_(standard_ids)
    ).group_by(QuizResult.user_id).order_by(
        desc('avg_score')
    ).limit(limit).all()
    
    return [{
        "rank": i + 1,
        "anonymous_id": f"Trainee_{u.user_id % 1000:03d}",
        "average_score": round(u.avg_score, 1),
        "quizzes_completed": u.quiz_count
    } for i, u in enumerate(user_scores)]
