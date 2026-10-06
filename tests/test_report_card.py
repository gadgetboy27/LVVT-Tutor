"""Report card: eligibility gate, weak-subject detection (<=69%), missed-question hints."""
import os

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or "sqlite://"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.quiz import Standard, QuizResult
from app.models.user import User
from app.api.report import build_report_card


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed(db):
    user = User(email="a@b.co", hashed_password="x")
    brakes = Standard(standard_number="BRK", title="Braking Systems", category="Brakes")
    fuel = Standard(standard_number="FUEL", title="Fuel Systems", category="Fuel")
    db.add_all([user, brakes, fuel])
    db.commit()
    return user, brakes, fuel


def _result(db, user, std, score, answers=None):
    db.add(QuizResult(user_id=user.id, standard_id=std.id, score=score,
                      total_questions=5, correct_answers=round(score / 20), answers=answers))
    db.commit()


def test_locked_until_five_quizzes(db):
    user, brakes, _ = _seed(db)
    for _ in range(4):
        _result(db, user, brakes, 50)
    card = build_report_card(user, db)
    assert card == {"eligible": False, "quizzes_completed": 4, "quizzes_needed": 1, "min_quizzes": 5}


def test_weak_subject_flagged_with_missed_question_hints(db):
    user, brakes, fuel = _seed(db)
    missed = [{"question": "Dual circuit?", "userAnswer": "No", "correctAnswer": "Yes",
               "isCorrect": False, "explanation": "See section 3"},
              {"question": "Easy one", "userAnswer": "A", "correctAnswer": "A", "isCorrect": True}]
    _result(db, user, brakes, 40, missed)
    _result(db, user, brakes, 60)
    _result(db, user, brakes, 60)
    _result(db, user, fuel, 100)
    _result(db, user, fuel, 90)

    card = build_report_card(user, db)
    assert card["eligible"] and card["needs_support"] is False  # overall 70.0
    assert [f["standard_number"] for f in card["focus_areas"]] == ["BRK"]
    focus = card["focus_areas"][0]
    assert focus["average"] == 53.3 and focus["is_weak"]
    assert [m["question"] for m in focus["missed_questions"]] == ["Dual circuit?"]
    assert focus["missed_questions"][0]["hint"] == "See section 3"
    assert card["strengths"][0]["name"] == "Fuel Systems"


def test_69_is_weak_70_is_not(db):
    user, brakes, fuel = _seed(db)
    for _ in range(3):
        _result(db, user, brakes, 69)
    for _ in range(2):
        _result(db, user, fuel, 70)
    card = build_report_card(user, db)
    assert [f["standard_number"] for f in card["focus_areas"]] == ["BRK"]
    assert card["overall_average"] == 69.4 and card["needs_support"] is False
    # an overall average of exactly 69 or less triggers full support mode
    _result(db, user, brakes, 60)
    assert build_report_card(user, db)["needs_support"] is True
