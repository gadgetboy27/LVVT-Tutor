from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func
from app.core.database import Base


class UsageMetric(Base):
    __tablename__ = "usage_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), index=True, nullable=False)
    endpoint = Column(String(100), nullable=True)
    user_id = Column(Integer, nullable=True)
    standard_number = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)
    response_time_ms = Column(Float, nullable=True)
    data_size_bytes = Column(Integer, nullable=True)
    device_type = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class DailyStats(Base):
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, unique=True, index=True)
    total_requests = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    quiz_starts = Column(Integer, default=0)
    quiz_completions = Column(Integer, default=0)
    documents_viewed = Column(Integer, default=0)
    ai_calls = Column(Integer, default=0)
    audio_requests = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, nullable=True)
    total_data_bytes = Column(Integer, default=0)
