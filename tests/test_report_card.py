"""Report card: eligibility gate, weak-subject detection (<75% real pass mark), hints, mock exams."""
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
    assert card["eligible"] and card["needs_support"] is True   # overall 70.0 < 75 pass mark
    assert [f["standard_number"] for f in card["focus_areas"]] == ["BRK"]
    focus = card["focus_areas"][0]
    assert focus["average"] == 53.3 and focus["is_weak"]
    assert [m["question"] for m in focus["missed_questions"]] == ["Dual circuit?"]
    assert focus["missed_questions"][0]["hint"] == "See section 3"
    assert card["strengths"][0]["name"] == "Fuel Systems"


def test_74_is_weak_75_is_not(db):
    """Real written test passes at 15/20 = 75%, so 74 is flagged and 75 is not."""
    user, brakes, fuel = _seed(db)
    for _ in range(3):
        _result(db, user, brakes, 74)
    for _ in range(2):
        _result(db, user, fuel, 75)
    card = build_report_card(user, db)
    assert [f["standard_number"] for f in card["focus_areas"]] == ["BRK"]
    assert card["overall_average"] == 74.4 and card["needs_support"] is False
    # an overall average at or under 74 triggers full support mode
    _result(db, user, brakes, 60)
    assert build_report_card(user, db)["needs_support"] is True


def _mcq(i, sn, correct="A"):
    return {"question_id": i, "question": f"Q{i}?", "options": ["A) one", "B) two", "C) three", "D) four"],
            "correct_answer": correct, "explanation": f"because {i}", "standard_number": sn}


def test_mock_exam_feeds_weak_standards_and_summary(db):
    from datetime import datetime
    from app.models.enhanced import PracticeExam
    user, brakes, fuel = _seed(db)
    for _ in range(5):
        _result(db, user, fuel, 90)          # strong on quizzes everywhere
    # exam: 4 brakes questions (1 right), 4 fuel (all right)
    qs = [_mcq(i, "BRK") for i in range(1, 5)] + [_mcq(i, "FUEL") for i in range(5, 9)]
    answers = {"1": "A", "2": "B", "3": "C", "4": "D", **{str(i): "A" for i in range(5, 9)}}
    db.add(PracticeExam(user_id=user.id, title="Mock Formal Assessment", description="formal-mock",
                        status="completed", total_questions=8, correct_answers=5, score=62.5,
                        questions=qs, answers=answers, completed_at=datetime.utcnow()))
    db.commit()

    card = build_report_card(user, db)
    assert [f["standard_number"] for f in card["focus_areas"]] == ["BRK"]   # 25% on the mock
    assert len(card["focus_areas"][0]["missed_questions"]) == 3
    mock = card["mock_exams"]
    assert mock["attempts"] == 1 and mock["best"] == 62.5
    assert mock["recent"][0]["passed"] is False      # 5/8 < 75%
    assert card["pass_mark"] == 75.0
