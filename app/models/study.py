from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class StudyPoint(Base):
    """One exam-relevant passage from an official PDF. `quote` is verbatim text that was
    machine-checked against the page it cites; `point` is a short plain-English restatement."""
    __tablename__ = "study_points"

    id = Column(Integer, primary_key=True, index=True)
    standard_id = Column(Integer, ForeignKey("standards.id"), nullable=False, index=True)
    page = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    importance = Column(Integer, nullable=False, default=2)     # 1 must know, 2 should know, 3 useful
    point = Column(Text, nullable=False)
    quote = Column(Text, nullable=False)
    section = Column(String, nullable=True)
    source_hash = Column(String, nullable=True)                 # sha256 of the PDF it was built from
    created_at = Column(DateTime(timezone=True), server_default=func.now())
