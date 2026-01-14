from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, desc
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models.analytics import UsageMetric, DailyStats

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


async def track_event(
    db: Session,
    event_type: str,
    endpoint: str = None,
    user_id: int = None,
    standard_number: str = None,
    category: str = None,
    response_time_ms: float = None,
    data_size_bytes: int = None,
    device_type: str = None
):
    metric = UsageMetric(
        event_type=event_type,
        endpoint=endpoint,
        user_id=user_id,
        standard_number=standard_number,
        category=category,
        response_time_ms=response_time_ms,
        data_size_bytes=data_size_bytes,
        device_type=device_type
    )
    db.add(metric)
    db.commit()


@router.get("/summary")
async def get_analytics_summary(
    days: int = 7,
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)
    
    total_events = db.query(UsageMetric).filter(
        UsageMetric.created_at >= since
    ).count()
    
    event_breakdown = db.query(
        UsageMetric.event_type,
        sql_func.count(UsageMetric.id).label('count')
    ).filter(
        UsageMetric.created_at >= since
    ).group_by(UsageMetric.event_type).all()
    
    popular_standards = db.query(
        UsageMetric.standard_number,
        sql_func.count(UsageMetric.id).label('views')
    ).filter(
        UsageMetric.created_at >= since,
        UsageMetric.standard_number.isnot(None)
    ).group_by(UsageMetric.standard_number).order_by(
        desc('views')
    ).limit(10).all()
    
    avg_response = db.query(
        sql_func.avg(UsageMetric.response_time_ms)
    ).filter(
        UsageMetric.created_at >= since,
        UsageMetric.response_time_ms.isnot(None)
    ).scalar()
    
    total_data = db.query(
        sql_func.sum(UsageMetric.data_size_bytes)
    ).filter(
        UsageMetric.created_at >= since,
        UsageMetric.data_size_bytes.isnot(None)
    ).scalar()
    
    unique_users = db.query(
        sql_func.count(sql_func.distinct(UsageMetric.user_id))
    ).filter(
        UsageMetric.created_at >= since,
        UsageMetric.user_id.isnot(None)
    ).scalar()
    
    device_breakdown = db.query(
        UsageMetric.device_type,
        sql_func.count(UsageMetric.id).label('count')
    ).filter(
        UsageMetric.created_at >= since,
        UsageMetric.device_type.isnot(None)
    ).group_by(UsageMetric.device_type).all()
    
    return {
        "period_days": days,
        "total_events": total_events,
        "unique_users": unique_users or 0,
        "avg_response_time_ms": round(avg_response, 2) if avg_response else None,
        "total_data_transferred_mb": round((total_data or 0) / 1024 / 1024, 2),
        "events_by_type": {e.event_type: e.count for e in event_breakdown},
        "popular_standards": [{"standard": s.standard_number, "views": s.views} for s in popular_standards],
        "device_breakdown": {d.device_type: d.count for d in device_breakdown if d.device_type}
    }


@router.get("/insights")
async def get_optimization_insights(
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=7)
    
    ai_calls = db.query(UsageMetric).filter(
        UsageMetric.created_at >= since,
        UsageMetric.event_type.in_(['quiz_generate', 'answer_evaluate', 'ask_question'])
    ).count()
    
    audio_calls = db.query(UsageMetric).filter(
        UsageMetric.created_at >= since,
        UsageMetric.event_type == 'audio_synthesize'
    ).count()
    
    doc_views = db.query(UsageMetric).filter(
        UsageMetric.created_at >= since,
        UsageMetric.event_type == 'document_view'
    ).count()
    
    mobile_pct = 0
    total_with_device = db.query(UsageMetric).filter(
        UsageMetric.created_at >= since,
        UsageMetric.device_type.isnot(None)
    ).count()
    
    if total_with_device > 0:
        mobile_count = db.query(UsageMetric).filter(
            UsageMetric.created_at >= since,
            UsageMetric.device_type == 'mobile'
        ).count()
        mobile_pct = round(mobile_count / total_with_device * 100, 1)
    
    recommendations = []
    
    if ai_calls > 100:
        recommendations.append({
            "area": "AI Usage",
            "finding": f"{ai_calls} AI calls in 7 days",
            "suggestion": "Consider caching common quiz questions to reduce API costs"
        })
    
    if audio_calls > 50:
        recommendations.append({
            "area": "Audio",
            "finding": f"{audio_calls} audio requests",
            "suggestion": "Audio is popular - consider pre-generating common sections"
        })
    
    if mobile_pct > 60:
        recommendations.append({
            "area": "Mobile",
            "finding": f"{mobile_pct}% mobile users",
            "suggestion": "High mobile usage - consider data saver mode"
        })
    
    if doc_views > 200:
        recommendations.append({
            "area": "Documents",
            "finding": f"{doc_views} document views",
            "suggestion": "Heavy document usage - offline mode could help"
        })
    
    return {
        "period": "last_7_days",
        "ai_api_calls": ai_calls,
        "audio_requests": audio_calls,
        "document_views": doc_views,
        "mobile_percentage": mobile_pct,
        "recommendations": recommendations
    }
