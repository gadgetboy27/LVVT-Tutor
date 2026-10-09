"""Question bank: generation safeguards, persistence, and serving without live AI."""
import json
import os

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import practice_exam, quiz
from app.core.database import Base, get_db
from app.models import study  # noqa: F401  (registers study_points, which the refresher also clears)
from app.models.bank import BankQuestion
from app.models.quiz import Standard
from app.models.user import User
from app.services.auth.jwt import get_current_user
from app.services.quiz.grading import correct_index
from app.services.rag import question_bank as qb

POINTS = [{"page": i, "quote": f"Quote number {i} says the certifier must do thing {i} every time", "point": f"p{i}",
           "section": f"2.{i}", "importance": 1} for i in range(1, 5)]


def _q(passage=1, key="A", question=None, **kw):
    d = {"passage": passage, "question": question or f"Scenario {passage}-{key}: what must the certifier do?",
         "options": ["A) right", "B) wrong one", "C) wrong two", "D) wrong three"], "correct_answer": key,
         "explanation": "Because clause says so."}
    d.update(kw)
    return d


def _llm(generated, verdicts):
    """Fake AI: first call(s) return `generated`, verification calls return `verdicts(group_prompt)`."""
    def llm(system, user, max_tokens):
        if system.startswith("You check"):
            return json.dumps(verdicts(user))
        return json.dumps(generated)
    return llm


def _key_for_all(user):
    """Verifier that always answers with the text-implied right option ('right')."""
    import re
    out = {}
    for m in re.finditer(r"\[(\d+)\] Passage:.*?Options: (.*?)(?:\n\n|\Z)", user, re.S):
        opts = [o.strip() for o in m.group(2).split("|")]
        out[m.group(1)] = "ABCD"[[i for i, o in enumerate(opts) if o.endswith("right")][0]]
    return out


def test_questions_carry_source_and_survive_the_independent_check():
    res = qb.build_questions(POINTS, "Braking", _llm([_q(1), _q(2), _q(3)], _key_for_all), workers=1)
    assert res["stats"]["kept"] == 3 and res["stats"]["rejected_by_check"] == 0
    q = res["questions"][0]
    assert q["source_page"] in (1, 2, 3) and q["source_quote"].startswith("Quote number") and q["source_section"].startswith("2.")
    assert q["correct_answer"] in q["options"] and q["options"][correct_index(q)].endswith("right")


def test_a_question_the_checker_disagrees_with_is_discarded():
    wrong = lambda user: {k: "B" for k in _key_for_all(user)}      # checker always picks B
    res = qb.build_questions(POINTS, "Braking", _llm([_q(1), _q(2)], wrong), workers=1)
    kept_ok = [q for q in res["questions"] if q["options"][correct_index(q)].endswith("right") and
               "ABCD"[correct_index(q)] == "B"]
    assert len(res["questions"]) == len(kept_ok)                   # only ones whose key happens to be B survive
    assert res["stats"]["rejected_by_check"] + res["stats"]["kept"] == res["stats"]["candidates"]


def test_failed_verification_never_lets_questions_through():
    def llm(system, user, max_tokens):
        if system.startswith("You check"):
            raise RuntimeError("api down")
        return json.dumps([_q(1), _q(2)])
    res = qb.build_questions(POINTS, "Braking", llm, workers=1)
    assert res["questions"] == [] and res["stats"]["unchecked"] == 2


def test_bad_items_are_dropped():
    bad = [_q(1, question="Which chapter contains the requirement?"),        # lookup question
           _q(9),                                                           # unknown passage
           _q(1, key="Z"),                                                  # unresolvable key
           _q(2, options=["A) x", "B) y"]),                                 # not four options
           _q(2, explanation=""),                                           # no explanation
           _q(3)]
    res = qb.build_questions(POINTS, "Braking", _llm(bad, _key_for_all), workers=1)
    assert res["stats"]["candidates"] == 1 and res["stats"]["dropped_format"] == 5


def test_answer_positions_are_shuffled():
    seen = set()
    for _ in range(40):
        res = qb.build_questions(POINTS, "T", _llm([_q(1)], _key_for_all), workers=1)
        seen.add(correct_index(res["questions"][0]))
    assert seen == {0, 1, 2, 3}


# --------------------------------------------------------------------------- persistence + serving
@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    user = User(email="a@b.co", hashed_password="x")
    stds = [Standard(standard_number=f"S{i}", title=f"Standard {i}", category="Cat") for i in range(6)]
    db.add_all([user, *stds]); db.commit()
    yield db, user, stds
    db.close(); engine.dispose()


def _fill(db, std, n):
    qb.replace_bank(db, std.id, [{"question": f"{std.standard_number} question {i}?",
                                  "options": ["A) one", "B) two", "C) three", "D) four"], "correct_answer": "B) two",
                                  "explanation": "Because.", "source_page": 4, "source_quote": "q" * 40,
                                  "source_section": "1.1"} for i in range(n)], "h")


def test_quiz_is_served_from_the_bank_without_any_ai(env, monkeypatch):
    db, user, stds = env
    _fill(db, stds[0], 8)
    def boom(*a, **k):
        raise AssertionError("AI must not be called when the bank can fill the quiz")
    monkeypatch.setattr(quiz, "generate_quiz_questions", boom)
    monkeypatch.setattr(quiz, "get_chroma_client", boom)
    app = FastAPI(); app.include_router(quiz.router); app.dependency_overrides[get_db] = lambda: db
    r = TestClient(app).post("/api/quiz/generate", json={"standard_number": "S0", "num_questions": 5})
    qs = r.json()["questions"]
    assert r.status_code == 200 and len(qs) == 5 and all("page 4" in q["explanation"] for q in qs)
    assert all(q["correct_answer"] in q["options"] for q in qs)


def test_mock_exam_is_drawn_from_the_bank_across_standards(env, monkeypatch):
    db, user, stds = env
    monkeypatch.setattr(practice_exam, "MIN_BANK_STANDARDS", 6)
    for s in stds:
        _fill(db, s, 6)
    monkeypatch.setattr(practice_exam, "generate_quiz_questions",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no AI needed")))
    app = FastAPI(); app.include_router(practice_exam.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    r = TestClient(app).post("/api/practice-exam/formal/start")
    d = r.json()
    assert r.status_code == 200 and d["total_questions"] == 20
    nums = [q["standard_number"] for q in d["questions"]]
    assert len(set(nums)) == 6 and max(nums.count(n) for n in set(nums)) <= 4      # spread, not one standard
    assert all("correct_answer" not in q and "explanation" not in q for q in d["questions"])


def test_export_and_idempotent_load(env, tmp_path):
    db, user, stds = env
    _fill(db, stds[0], 3); _fill(db, stds[1], 2)
    path = str(tmp_path / "b.json.gz")
    assert qb.export_bank(db, path) == 5
    db.query(BankQuestion).delete(); db.commit()
    assert qb.load_bank(db, path) == {"added": 5, "standards": 2}
    assert qb.load_bank(db, path) == {"added": 0, "standards": 0}


def test_changed_pdf_drops_its_bank(env, monkeypatch):
    from datetime import datetime
    from app.services.rag import pdf_refresh
    db, user, stds = env
    s = stds[0]; s.pdf_url = "u"; s.last_modified = datetime(2026, 1, 1); s.content_hash = "h1"; db.commit()
    _fill(db, s, 3)
    monkeypatch.setattr(pdf_refresh, "SessionLocal", lambda: type("S", (), {"__getattr__": lambda self, n: getattr(db, n), "close": lambda self: None})())
    monkeypatch.setattr(pdf_refresh, "remote_last_modified", lambda url: datetime(2026, 9, 1))
    monkeypatch.setattr(pdf_refresh, "index_pdf_to_vectordb",
                        lambda *a, **k: {"success": True, "content_hash": "new"})
    pdf_refresh.refresh_stale_pdfs()
    assert qb.bank_size(db, s.id) == 0


def test_narrow_bank_is_not_used_for_the_mock_exam(env, monkeypatch):
    """A bank covering only a few standards would make the mock a narrow quiz; fall back to live generation."""
    db, user, stds = env
    for s in stds[:3]:
        _fill(db, s, 30)                                            # plenty of questions, but only 3 standards
    assert practice_exam._questions_from_bank(db, 20) == []
