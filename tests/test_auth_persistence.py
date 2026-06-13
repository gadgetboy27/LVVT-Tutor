"""Real email/password auth + per-user quiz persistence + resumable state.

In-memory SQLite, no external services.

    python -m pytest tests/test_auth_persistence.py -v
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
from app.api import auth as auth_api, quiz as quiz_api


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = SessionLocal()
    db.add(Standard(standard_number="LVVTA_STD_Braking_Systems", title="Braking Systems", category="Brakes"))
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(auth_api.router)
    app.include_router(quiz_api.router)

    def override_get_db():
        d = SessionLocal()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _auth(client, email="trainee@example.com", pw="secret123"):
    r = client.post("/api/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    r = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


SUBMIT = {
    "standard_number": "LVVTA_STD_Braking_Systems",
    "score": 100, "total_questions": 5, "correct_answers": 5, "answers": {},
}


def test_register_login_me(client):
    h = _auth(client)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "trainee@example.com"


def test_wrong_password_rejected(client):
    _auth(client)
    r = client.post("/api/auth/login", data={"username": "trainee@example.com", "password": "WRONG"})
    assert r.status_code == 401


def test_quiz_result_persists_and_history_returns_it(client):
    h = _auth(client)
    assert client.get("/api/quiz/history", headers=h).json() == []
    assert client.post("/api/quiz/submit", headers=h, json=SUBMIT).status_code == 200
    hist = client.get("/api/quiz/history", headers=h).json()
    assert len(hist) == 1
    assert hist[0]["score"] == 100 and hist[0]["correct_answers"] == 5


def test_history_isolated_between_users(client):
    h1 = _auth(client, "a@example.com")
    h2 = _auth(client, "b@example.com")
    client.post("/api/quiz/submit", headers=h1, json={**SUBMIT, "score": 80, "correct_answers": 4})
    assert len(client.get("/api/quiz/history", headers=h1).json()) == 1
    assert client.get("/api/quiz/history", headers=h2).json() == []   # b sees nothing of a's


def test_quiz_state_roundtrip_and_upsert(client):
    h = _auth(client)
    assert client.get("/api/quiz/state", headers=h).json()["state"] is None
    state = {"quiz": {"title": "Braking Systems", "standardNumber": "LVVTA_STD_Braking_Systems", "totalQuestions": 5},
             "questionIndex": 2, "answers": []}
    assert client.put("/api/quiz/state", headers=h, json={"state": state}).status_code == 200
    got = client.get("/api/quiz/state", headers=h).json()["state"]
    assert got["questionIndex"] == 2 and got["quiz"]["title"] == "Braking Systems"
    state["questionIndex"] = 4
    client.put("/api/quiz/state", headers=h, json={"state": state})
    assert client.get("/api/quiz/state", headers=h).json()["state"]["questionIndex"] == 4   # upsert, not duplicate
    client.delete("/api/quiz/state", headers=h)
    assert client.get("/api/quiz/state", headers=h).json()["state"] is None


def test_persistence_endpoints_require_auth(client):
    assert client.get("/api/quiz/history").status_code == 401
    assert client.get("/api/quiz/state").status_code == 401
    assert client.post("/api/quiz/submit", json=SUBMIT).status_code == 401
