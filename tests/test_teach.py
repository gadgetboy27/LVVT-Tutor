"""Tests for the Teach-Back ("Teach it") feature.

Runs without Postgres, a real vector store, or an OpenAI key: the AI path is
skipped (no key) so the deterministic, source-grounded fallback is exercised,
and the routes use an in-memory SQLite DB with a fake Chroma collection.

    python -m pytest tests/test_teach.py -v
"""
import os

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.quiz import Standard
from app.api import teach
from app.services.rag import ai_service

# A chunk of real-ish standard text used as the only "ground truth".
SOURCE = (
    "The braking system must maintain a dual-circuit hydraulic configuration so that "
    "failure of one circuit still provides stopping ability. A proportioning valve "
    "controls front-to-rear brake balance. The handbrake must operate independently "
    "on at least two wheels."
)


@pytest.fixture
def TestingSessionLocal():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield SessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# --------------------------------------------------------------------------- #
# ai_service.evaluate_teachback  (grounded fallback, no hallucination)
# --------------------------------------------------------------------------- #
def test_evaluate_teachback_fallback_is_grounded_and_scores_coverage():
    # An explanation that mentions some source concepts but omits others.
    explanation = "The braking system uses a dual-circuit hydraulic setup for safety."
    result = ai_service.evaluate_teachback(
        topic="Braking system purpose",
        learner_explanation=explanation,
        context=SOURCE,
        standard_number="LVVTA_STD_Braking_Systems",
    )
    assert result["method"] == "lexical-fallback"
    assert 0 < result["accuracy_score"] < 100          # partial coverage
    # every covered/gap term must come from the SOURCE (never invented)
    source_lower = SOURCE.lower()
    for term in result["covered_points"] + result["gaps"]:
        assert term in source_lower
    # covered terms must actually appear in the explanation; gaps must not
    expl = explanation.lower()
    assert all(t in expl for t in result["covered_points"])
    assert all(t not in expl for t in result["gaps"])
    # the fallback must never fabricate misconceptions
    assert result["misconceptions"] == []
    assert result["citations"] == ["LVVTA_STD_Braking_Systems"]


def test_evaluate_teachback_flags_insufficient_context():
    result = ai_service.evaluate_teachback(
        topic="Anything",
        learner_explanation="Some explanation.",
        context="",
        standard_number="X",
    )
    assert result["insufficient_context"] is True
    assert result["accuracy_score"] == 0
    assert result["method"] == "lexical-fallback"


def test_evaluate_teachback_uses_key_points_when_given():
    result = ai_service.evaluate_teachback(
        topic="Handbrake",
        learner_explanation="The handbrake works on two wheels independently.",
        context=SOURCE,
        standard_number="X",
        key_points=["handbrake operates independently", "at least two wheels"],
    )
    # 'independently' and 'wheels' are covered; score should be high
    assert result["accuracy_score"] >= 50
    assert result["method"] == "lexical-fallback"


# --------------------------------------------------------------------------- #
# ai_service.build_teach_tree  (grounded fallback)
# --------------------------------------------------------------------------- #
def test_build_teach_tree_fallback_derives_aspects_from_source():
    aspects = ai_service.build_teach_tree("LVVTA_STD_Braking_Systems", "Braking Systems", SOURCE)
    assert len(aspects) >= 1
    for a in aspects:
        assert a["aspect"] and a["prompt"]
        # key points are terms lifted from the source, not invented
        for kp in a["key_points"]:
            assert kp in SOURCE.lower()


def test_build_teach_tree_handles_empty_source():
    aspects = ai_service.build_teach_tree("X", "Mystery Standard", "")
    assert len(aspects) == 1
    assert "Mystery Standard" in aspects[0]["prompt"]


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
class FakeStandardCollection:
    """Returns the SOURCE text for any scoped query."""

    def query(self, query_texts=None, n_results=3, where=None):
        return {"documents": [[SOURCE]]}


@pytest.fixture
def client(TestingSessionLocal, monkeypatch):
    # Bypass the real vector store with a fake that always returns SOURCE.
    monkeypatch.setattr(teach, "get_chroma_client", lambda: object())
    monkeypatch.setattr(teach, "get_or_create_collection", lambda c: FakeStandardCollection())

    db = TestingSessionLocal()
    db.add(Standard(standard_number="LVVTA_STD_Braking_Systems", title="Braking Systems",
                    category="Brakes", summary="Braking system requirements"))
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(teach.router)

    def override_get_db():
        d = TestingSessionLocal()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_tree_route_returns_grounded_aspects(client):
    r = client.get("/api/teach/tree/LVVTA_STD_Braking_Systems")
    assert r.status_code == 200
    body = r.json()
    assert body["standard_number"] == "LVVTA_STD_Braking_Systems"
    assert body["grounded"] is True
    assert len(body["aspects"]) >= 1


def test_tree_route_404(client):
    assert client.get("/api/teach/tree/NOPE").status_code == 404


def test_evaluate_route_grades_explanation(client):
    r = client.post("/api/teach/evaluate", json={
        "standard_number": "LVVTA_STD_Braking_Systems",
        "topic": "Dual-circuit braking",
        "explanation": "It uses a dual-circuit hydraulic system so one failure still stops the car.",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["citations"] == ["LVVTA_STD_Braking_Systems"]
    assert body["insufficient_context"] is False
    assert 0 < body["accuracy_score"] <= 100


def test_evaluate_route_requires_explanation(client):
    r = client.post("/api/teach/evaluate", json={
        "standard_number": "LVVTA_STD_Braking_Systems",
        "topic": "x",
        "explanation": "   ",
    })
    assert r.status_code == 400


def test_evaluate_route_404_for_unknown_standard(client):
    r = client.post("/api/teach/evaluate", json={
        "standard_number": "NOPE", "topic": "x", "explanation": "y",
    })
    assert r.status_code == 404
