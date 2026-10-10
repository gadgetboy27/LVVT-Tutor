"""Re-review stored bank questions for circular wording and low relevance.

    python scripts/audit_question_bank.py            # report only
    python scripts/audit_question_bank.py --delete   # remove flagged questions and re-export the bank

Uses the AI (one call per 10 questions). Flags a question when its correct answer mostly restates
the question itself, or when it tests glossary/internal-admin trivia a certifier doesn't apply.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

parser = argparse.ArgumentParser()
parser.add_argument("--delete", action="store_true")
parser.add_argument("--out", default="data/question_bank.json.gz")
args = parser.parse_args()

from app.core.database import SessionLocal  # noqa: E402
from app.models import bank, quiz, study, user  # noqa: E402,F401
from app.models.bank import BankQuestion  # noqa: E402
from app.models.quiz import Standard  # noqa: E402
from app.services.rag import question_bank, study_guide  # noqa: E402

db = SessionLocal()
rows = db.query(BankQuestion).order_by(BankQuestion.id).all()
numbers = {s.id: s.standard_number for s in db.query(Standard).all()}
verdicts = question_bank.judge_questions(
    [{"question": r.question, "correct_answer": r.correct_answer} for r in rows], study_guide.default_llm())
flagged = [(r, v) for r, v in zip(rows, verdicts) if v["restates"] or not v["relevant"]]
for r, v in flagged:
    why = "restates the question" if v["restates"] else "low relevance"
    print(f"#{r.id} [{numbers.get(r.standard_id)}] ({why}) {r.question[:110]}")
print(f"\n{len(flagged)} of {len(rows)} flagged")
if args.delete and flagged:
    for r, _ in flagged:
        db.delete(r)
    db.commit()
    print("deleted; exported", question_bank.export_bank(db, args.out), "questions to", args.out)
