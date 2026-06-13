from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Standard(Base):
    __tablename__ = "standards"
    
    id = Column(Integer, primary_key=True, index=True)
    standard_number = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    pdf_url = Column(String, nullable=True)
    category = Column(String, default="Uncategorized")
    summary = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    last_modified = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String, nullable=True)
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    sections = relationship("StandardSection", back_populates="standard", cascade="all, delete-orphan")


class StandardSection(Base):
    __tablename__ = "standard_sections"
    
    id = Column(Integer, primary_key=True, index=True)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=False)
    section_title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    standard = relationship("Standard", back_populates="sections")


class QuizResult(Base):
    __tablename__ = "quiz_results"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=True)
    section_id = Column(Integer, ForeignKey("standard_sections.id"), nullable=True)
    score = Column(Float, nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    answers = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="quiz_results")


class SectionMastery(Base):
    __tablename__ = "section_mastery"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("standard_sections.id"), nullable=False)
    mastery_score = Column(Integer, default=0)
    attempts = Column(Integer, default=0)
    is_mastered = Column(Boolean, default=False)
    last_attempt = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="section_masteries")


class SavedQuizState(Base):
    """One in-progress quiz per user, so 'continue where you left off' works
    across devices (not just same-browser localStorage)."""
    __tablename__ = "saved_quiz_state"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    state = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=True)
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())
    completion_percentage = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    
    user = relationship("User", back_populates="progress")
