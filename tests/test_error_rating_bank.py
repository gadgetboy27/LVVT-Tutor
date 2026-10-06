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


@pytest.mark.parametrize("sn,expected_min", [("ORS_Chapter_11", 10), ("ORS_Chapter_5", 5), ("ORS_Chapter_4", 5),
                                              ("ORS_Chapter_7", 5), ("ORS_Chapter_8", 10)])
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


# --------------------------------------------------------------------------- AI output hygiene
from app.services.quiz.grading import is_lookup_question, prepare_questions, shuffle_question


def _raw(q="Q?", correct="A"):
    return {"question": q, "options": ["A) right", "B) wrong one", "C) wrong two", "D) wrong three"],
            "correct_answer": correct, "explanation": "x"}


def test_shuffle_keeps_key_and_removes_position_bias():
    positions = set()
    for _ in range(60):
        s = shuffle_question(_raw())
        assert s["options"][correct_index(s)].endswith("right")
        assert s["correct_answer"] in s["options"]
        assert [o[0] for o in s["options"]] == list("ABCD")
        positions.add(correct_index(s))
    assert positions == {0, 1, 2, 3}          # the right answer is no longer always 'A'


def test_unresolvable_or_duplicate_keys_are_dropped():
    assert shuffle_question(_raw(correct="Z")) is None
    dup = _raw(); dup["options"][1] = "A) right"
    assert shuffle_question(dup) is None


def test_options_that_refer_to_each_other_keep_their_order():
    q = {"question": "Q?", "options": ["A) one", "B) two", "C) three", "D) All of the above"],
         "correct_answer": "D", "explanation": "x"}
    assert shuffle_question(q)["options"][3].endswith("All of the above")


@pytest.mark.parametrize("text,expected", [
    ("Which document must this standard be read in conjunction with?", True),
    ("Where are the detailed technical requirements contained?", True),
    ("What is the form called that supports the exclusion?", False),   # not matched; covered by prompt
    ("A certifier finds a cracked weld on a brake bracket. What must they do?", False),
    ("Which decision is correct when the droop is only 30 mm?", False),
])
def test_lookup_detector(text, expected):
    assert is_lookup_question(text) is expected


def test_prepare_prefers_application_questions_and_trims():
    raw = [_raw("Which chapter contains the requirements?")] + [_raw(f"Scenario {i}: what must the certifier do?") for i in range(3)]
    out = prepare_questions(raw, 3)
    assert len(out) == 3 and not any(is_lookup_question(q["question"]) for q in out)
    assert len(prepare_questions(raw[:1], 3)) == 1       # lookups still used to make up numbers
