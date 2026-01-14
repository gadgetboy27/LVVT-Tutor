from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class ExamStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


class MentorStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class PracticeExam(Base):
    __tablename__ = "practice_exams"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    time_limit_minutes = Column(Integer, default=60)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default=ExamStatus.IN_PROGRESS.value)
    total_questions = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    score = Column(Float, nullable=True)
    standards_included = Column(JSON, nullable=True)
    questions = Column(JSON, nullable=True)
    answers = Column(JSON, nullable=True)
    
    user = relationship("User", backref="practice_exams")


class SpacedRepetitionCard(Base):
    __tablename__ = "spaced_repetition_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    standard_number = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source_chunk = Column(Text, nullable=True)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    repetitions = Column(Integer, default=0)
    next_review = Column(DateTime(timezone=True), server_default=func.now())
    last_review = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="spaced_repetition_cards")


class PeerStats(Base):
    __tablename__ = "peer_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    total_quizzes = Column(Integer, default=0)
    total_correct = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    average_score = Column(Float, default=0.0)
    standards_mastered = Column(Integer, default=0)
    exams_completed = Column(Integer, default=0)
    study_streak_days = Column(Integer, default=0)
    last_study_date = Column(DateTime(timezone=True), nullable=True)
    rank_percentile = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", backref="peer_stats")


class Mentor(Base):
    __tablename__ = "mentors"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    bio = Column(Text, nullable=True)
    specializations = Column(JSON, nullable=True)
    years_experience = Column(Integer, default=0)
    certification_categories = Column(JSON, nullable=True)
    status = Column(String, default=MentorStatus.AVAILABLE.value)
    rating = Column(Float, default=5.0)
    total_mentees = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MentorshipRequest(Base):
    __tablename__ = "mentorship_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    trainee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)
    
    trainee = relationship("User", backref="mentorship_requests")
    mentor = relationship("Mentor", backref="requests")


class StudyGuideExport(Base):
    __tablename__ = "study_guide_exports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    standards_included = Column(JSON, nullable=True)
    format = Column(String, default="pdf")
    file_path = Column(String, nullable=True)
    download_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User", backref="study_guide_exports")


class AudioCache(Base):
    __tablename__ = "audio_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    content_hash = Column(String, unique=True, index=True, nullable=False)
    standard_number = Column(String, nullable=True)
    text_preview = Column(String(500), nullable=True)
    audio_file_path = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    access_count = Column(Integer, default=0)
