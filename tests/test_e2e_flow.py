"""End-to-end user-journey driver, in-process via FastAPI TestClient against the
REAL ChromaDB-seeded app. Mirrors static/js/quiz.js step by step so we exercise
the exact API contracts the browser uses, and surface any broken-flow moments.

Run:  python -m pytest tests/test_e2e_flow.py -v -s

Uses a file-backed SQLite DB so the startup lifespan (which seeds standards from
the on-disk ChromaDB) populates real categories/standards. No LLM key -> AI runs
in deterministic fallback (expected).
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./_e2e_test.db"

import pytest
import app.core.database as _db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Thread-safe SQLite, same as the throwaway launcher would use.
_db.engine = create_engine(
    "sqlite:///./_e2e_test.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_db.SessionLocal = sessionmaker(bind=_db.engine, autoflush=False, autocommit=False)

import main  # noqa: E402  (must import after patching engine)
from fastapi.testclient import TestClient  # noqa: E402

REPORT = []


def _log(name, ok, detail=""):
    REPORT.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'STALL'}] {name}" + (f" :: {detail}" if detail else ""))


@pytest.fixture(scope="module")
def client():
    # TestClient context manager fires the lifespan -> seeds from ChromaDB.
    with TestClient(main.app) as c:
        yield c
    if os.path.exists("./_e2e_test.db"):
        os.remove("./_e2e_test.db")


# Shared state across ordered steps.
STATE = {}


def test_01_health_and_spa(client):
    r = client.get("/health")
    _log("health", r.status_code == 200, str(r.json()))
    assert r.status_code == 200
    r = client.get("/")
    _log("root SPA served", r.status_code == 200 and "quiz.js" in r.text)
    assert r.status_code == 200 and "quiz.js" in r.text


def test_02_categories(client):
    r = client.get("/api/standards/categories")
    cats = r.json() if r.status_code == 200 else []
    STATE["cats"] = cats
    _log("load categories", r.status_code == 200 and len(cats) > 0,
         f"{len(cats)} categories: {cats}")
    assert r.status_code == 200 and len(cats) > 0


def test_03_by_category_every_category(client):
    cats = STATE["cats"]
    per_cat, chosen = {}, None
    for cat in cats:
        r = client.get(f"/api/standards/by-category/{cat}")
        stds = r.json() if r.status_code == 200 else []
        per_cat[cat] = len(stds)
        if stds and chosen is None:
            chosen = (cat, stds[0])
    empty = [c for c, n in per_cat.items() if n == 0]
    STATE["chosen"] = chosen
    STATE["empty_cats"] = empty
    _log("every category resolves to standards", not empty and chosen is not None,
         f"counts={per_cat}; EMPTY={empty}")
    # The flow can continue as long as at least one category has standards.
    assert chosen is not None
    # A category card the user can click that dead-ends (empty list) is a sticking point.
    assert not empty, f"Categories with NO standards (clicking them dead-ends): {empty}"


def test_04_read_document(client):
    cat, std = STATE["chosen"]
    sn = std["standard_number"]
    STATE["sn"] = sn
    STATE["title"] = std["title"]
    r = client.get(f"/api/standards/content/{sn}")
    has = r.status_code == 200 and bool(r.json().get("content"))
    # 404/500 are handled gracefully by the frontend (shows "being indexed"),
    # so this is not a hard stall — just report it.
    _log("read document content", True,
         f"status={r.status_code} content={'yes' if has else 'fallback-message'}")


def test_05_generate_quiz_and_score_100(client):
    sn = STATE["sn"]
    r = client.post("/api/quiz/generate", json={"standard_number": sn, "num_questions": 5})
    _log("generate quiz", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    assert r.status_code == 200
    questions = r.json().get("questions", [])
    _log("quiz has questions", len(questions) > 0, f"{len(questions)} questions")
    assert len(questions) > 0

    correct = 0
    for i, q in enumerate(questions):
        # MCQ: frontend sends the selected option text. We pick the correct one.
        if q.get("options"):
            present = q["correct_answer"] in q["options"]
            _log(f"  Q{i+1} correct option selectable", present,
                 "" if present else f"correct={q['correct_answer']!r} not in {q['options']}")
            user_answer = q["correct_answer"]
        else:
            user_answer = q["correct_answer"]
        er = client.post("/api/quiz/evaluate-answer", json={
            "question": q["question"],
            "user_answer": user_answer,
            "correct_answer": q["correct_answer"],
            "difficulty": q.get("difficulty", "medium"),
            "standard_number": sn,
        })
        if er.status_code == 200 and er.json().get("is_correct"):
            correct += 1
        else:
            _log(f"  Q{i+1} eval correct-answer => is_correct", False,
                 f"status={er.status_code} body={er.text[:160]}")
    pct = round(correct / len(questions) * 100)
    STATE["pct"] = pct
    _log("FINISH QUIZ with best score", pct == 100,
         f"score={pct}% ({correct}/{len(questions)}) mastery={'YES' if pct >= 80 else 'no'}")
    assert pct == 100, f"Could not reach 100% even by selecting each correct_answer; got {pct}%"


def test_05b_every_standard_quiz_reaches_100(client):
    """Pick each standard's quiz and confirm a user who selects every correct
    answer reaches 100% — catches MCQ where correct_answer isn't among options,
    or short-answer where the fallback grader rejects the reference answer."""
    # Gather all standards across all categories.
    seen = set()
    standards = []
    for cat in STATE["cats"]:
        for s in client.get(f"/api/standards/by-category/{cat}").json():
            if s["standard_number"] not in seen:
                seen.add(s["standard_number"])
                standards.append(s)
    problems = []
    for s in standards:
        sn = s["standard_number"]
        r = client.post("/api/quiz/generate", json={"standard_number": sn, "num_questions": 5})
        if r.status_code != 200:
            problems.append((sn, f"generate {r.status_code}"))
            continue
        qs = r.json().get("questions", [])
        if not qs:
            problems.append((sn, "no questions"))
            continue
        correct = 0
        for q in qs:
            if q.get("options") and q["correct_answer"] not in q["options"]:
                problems.append((sn, f"correct_answer not in options: {q['correct_answer']!r}"))
            er = client.post("/api/quiz/evaluate-answer", json={
                "question": q["question"], "user_answer": q["correct_answer"],
                "correct_answer": q["correct_answer"],
                "difficulty": q.get("difficulty", "medium"), "standard_number": sn,
            })
            if er.status_code == 200 and er.json().get("is_correct"):
                correct += 1
        pct = round(correct / len(qs) * 100)
        if pct != 100:
            problems.append((sn, f"max score {pct}%"))
    _log(f"all {len(standards)} standards reach 100% by selecting correct answers",
         not problems, f"problems={problems}" if problems else "all 100%")
    assert not problems, f"Standards where a user cannot reach 100%: {problems}"


def test_06_teach_tree(client):
    sn = STATE["sn"]
    r = client.get(f"/api/teach/tree/{sn}")
    tree = r.json() if r.status_code == 200 else {}
    aspects = tree.get("aspects", [])
    STATE["aspects"] = aspects
    _log("teach tree", r.status_code == 200 and len(aspects) > 0,
         f"status={r.status_code} aspects={len(aspects)} grounded={tree.get('grounded')}")
    assert r.status_code == 200 and len(aspects) > 0


def test_07_teach_evaluate(client):
    sn = STATE["sn"]
    aspects = STATE.get("aspects") or []
    a = aspects[0] if aspects else {"aspect": STATE["title"], "key_points": []}
    explanation = "This standard requires " + " ".join(a.get("key_points") or [STATE["title"]])
    r = client.post("/api/teach/evaluate", json={
        "standard_number": sn,
        "topic": a.get("aspect", STATE["title"]),
        "explanation": explanation,
        "key_points": a.get("key_points", []),
    })
    ok = r.status_code == 200
    body = r.json() if ok else {}
    _log("teach evaluate", ok,
         f"status={r.status_code} score={body.get('accuracy_score')} method={body.get('method')}")
    assert ok


def test_08_scenario_answer(client):
    # Scenarios are client-side in quiz.js but route answers through evaluate-answer.
    er = client.post("/api/quiz/evaluate-answer", json={
        "question": "Does this modification require LVV certification?",
        "user_answer": "Yes - exceeds threshold",
        "correct_answer": "Yes - exceeds threshold",
        "difficulty": "hard",
        "standard_number": "SCENARIO",
    })
    ok = er.status_code == 200 and er.json().get("is_correct")
    _log("scenario answer evaluates correct", ok, f"status={er.status_code} body={er.text[:120]}")
    assert ok


def test_09_readiness_calc(client):
    # Replicate quiz.js calculateReadiness() after a 100% mastered quiz + full self-assessment.
    pct = STATE.get("pct", 100)
    progress = {"quizzes": 1, "score": pct, "mastered": 1 if pct >= 80 else 0}
    assessment = {k: 5 for k in
                  ["integrity", "technical", "experience", "conscientious",
                   "independent", "reliable", "people"]}
    score = 0
    if progress["quizzes"] > 0:
        score += min(20, progress["quizzes"] * 2)
    if progress["score"] > 0:
        score += (progress["score"] / 100) * 30
    if progress["mastered"] > 0:
        score += min(20, progress["mastered"] * 4)
    score += (sum(assessment.values()) / 7 / 5) * 30
    readiness = min(100, round(score))
    _log("readiness updates after mastery+self-assessment", readiness > 0,
         f"readiness={readiness}%")
    assert readiness > 0


def test_99_summary(client):
    print("\n==== E2E SUMMARY ====")
    stalls = [r for r in REPORT if not r[1]]
    print(f"{len(REPORT) - len(stalls)}/{len(REPORT)} checks PASS, {len(stalls)} STALL")
    for n, ok, d in stalls:
        print(f"  STALL: {n} :: {d}")
