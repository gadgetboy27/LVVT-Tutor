"""The hand-written, source-cited question bank (ORS Ch.5 / Ch.11)."""
import os

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import quiz
from app.core.database import Base, get_db
from app.models.quiz import Standard
from app.services.quiz import error_rating
from app.services.quiz.error_rating import curated_questions
from app.services.quiz.grading import correct_index, is_answer_correct


@pytest.mark.parametrize("sn,expected_min", [("ORS_Chapter_11", 10), ("ORS_Chapter_5", 5)])
def test_bank_items_are_well_formed_and_cited(sn, expected_min):
    items = error_rating._BANK[sn]
    assert len(items) >= expected_min
    for q, correct, wrong, why in items:
        assert len(wrong) == 3 and correct not in wrong
        assert len({correct, *wrong}) == 4              # no duplicate options
        assert "ORS Ch." in why                          # every answer names its source section


def test_built_question_marks_the_right_option_whatever_the_shuffle():
    for _ in range(25):
        for q in curated_questions("ORS_Chapter_11", 13):
            assert len(q["options"]) == 4 and q["type"] == "MCQ"
            assert correct_index(q) in range(4)
            assert is_answer_correct(q, q["correct_answer"])


def test_known_answer_survives_shuffling():
    q = next(x for x in curated_questions("ORS_Chapter_11", 13) if x["question"].startswith("In the Error Report points system, how many Technical Medium"))
    assert q["options"][correct_index(q)].endswith("Two")


def test_unknown_standard_and_limits():
    assert curated_questions("LVVTA_STD_Braking_Systems", 5) == []
    assert len(curated_questions("ORS_Chapter_11", 3)) == 3
    assert len(curated_questions("ORS_Chapter_5", 50)) == len(error_rating._BANK["ORS_Chapter_5"])


def test_generate_endpoint_mixes_curated_with_fallback(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(Standard(standard_number="ORS_Chapter_11", title="Error Recording", category="Certification Process"))
    s.commit()

    class Coll: ...
    monkeypatch.setattr(quiz, "get_chroma_client", lambda: None)
    monkeypatch.setattr(quiz, "get_or_create_collection", lambda c: Coll())
    monkeypatch.setattr(quiz, "query_documents", lambda *a, **k: {"documents": [[]]})   # nothing indexed -> fallback

    app = FastAPI()
    app.include_router(quiz.router)
    app.dependency_overrides[get_db] = lambda: s
    r = TestClient(app).post("/api/quiz/generate", json={"standard_number": "ORS_Chapter_11", "num_questions": 5})
    assert r.status_code == 200
    qs = r.json()["questions"]
    assert len(qs) == 5
    cited = [q for q in qs if "ORS Ch." in q["explanation"]]
    assert len(cited) == 3                                 # ceil(5 * 0.6) curated, the rest from fallback
