"""Generate the question bank from stored study-guide points, store it, and export
data/question_bank.json.gz (loaded on first boot by fresh deployments).

    python scripts/build_question_bank.py --all [--skip-existing] [--model MODEL]
    python scripts/build_question_bank.py ORS_Chapter_11 LVVTA_STD_Braking_Systems

Requires study points (scripts/build_study_guides.py) for the standard first.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("standards", nargs="*")
parser.add_argument("--all", action="store_true")
parser.add_argument("--model", default="")
parser.add_argument("--skip-existing", action="store_true")
parser.add_argument("--out", default="data/question_bank.json.gz")
args = parser.parse_args()
if args.model:
    settings.STUDY_GUIDE_MODEL = args.model

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import bank, quiz, study, user  # noqa: E402,F401
from app.models.quiz import Standard  # noqa: E402
from app.models.study import StudyPoint  # noqa: E402
from app.services.rag import question_bank, study_guide  # noqa: E402

Base.metadata.create_all(bind=engine)
db = SessionLocal()
q = db.query(Standard)
targets = q.all() if args.all else q.filter(Standard.standard_number.in_(args.standards)).all()
llm = study_guide.default_llm()
totals = {"kept": 0, "candidates": 0, "rejected": 0}
for std in sorted(targets, key=lambda s: s.standard_number):
    pts = db.query(StudyPoint).filter(StudyPoint.standard_id == std.id).all()
    if not pts:
        continue
    if args.skip_existing and question_bank.bank_size(db, std.id):
        print(f"skip   {std.standard_number} (has questions)", flush=True)
        continue
    t0 = time.time()
    res = question_bank.build_questions(
        [{"page": p.page, "quote": p.quote, "point": p.point, "section": p.section, "importance": p.importance}
         for p in pts], std.title, llm)
    st = res["stats"]
    if st["batches"] and st["failed_batches"] == st["batches"]:
        print(f"FAILED {std.standard_number}: AI unavailable", flush=True)
        continue
    question_bank.replace_bank(db, std.id, res["questions"], pts[0].source_hash)
    totals["kept"] += st["kept"]; totals["candidates"] += st["candidates"]; totals["rejected"] += st["rejected_by_check"]
    print(f"ok     {std.standard_number}: {len(pts)} passages -> {st['candidates']} candidates, "
          f"{st['rejected_by_check']} rejected by check, {st['unchecked']} unchecked, kept {st['kept']} ({time.time()-t0:.0f}s)", flush=True)

print("totals:", totals, flush=True)
print("exported", question_bank.export_bank(db, args.out), "questions to", args.out, flush=True)
