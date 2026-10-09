from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class BankQuestion(Base):
    """A pre-generated, pre-checked exam-style question, so quizzes and mock exams need no live AI.
    Each one is grounded in a verified passage (`source_quote`, `source_page`) of the official PDF."""
    __tablename__ = "bank_questions"

    id = Column(Integer, primary_key=True, index=True)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_answer = Column(Text, nullable=False)      # full text of the right option
    explanation = Column(Text, nullable=False)
    difficulty = Column(String, default="medium")
    source_page = Column(Integer, nullable=True)
    source_quote = Column(Text, nullable=True)
    source_section = Column(String, nullable=True)
    source_hash = Column(String, nullable=True)        # sha256 of the PDF the notes came from
    created_at = Column(DateTime(timezone=True), server_default=func.now())
