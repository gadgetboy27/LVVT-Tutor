"""Build verified study guides for standards, store them in the DB, and export
data/study_guides.json.gz (which fresh deployments load on first boot).

    python scripts/build_study_guides.py LVVTA_STD_Braking_Systems ORS_Chapter_11
    python scripts/build_study_guides.py --all [--model claude-sonnet-5-5] [--skip-existing]

Uses DATABASE_URL (run-local.sh's SQLite DB by default is `sqlite:///./local_dev.db`)
and your Anthropic key; a typical document is ~5-11k input tokens.
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
parser.add_argument("--model", default="", help="override the model for this run")
parser.add_argument("--skip-existing", action="store_true", help="leave standards that already have notes")
parser.add_argument("--out", default="data/study_guides.json.gz")
args = parser.parse_args()
if args.model:
    settings.STUDY_GUIDE_MODEL = args.model

from app.api.pdf_viewer import _ensure_cached_pdf  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import quiz, study, user  # noqa: E402,F401
from app.models.quiz import Standard  # noqa: E402
from app.models.study import StudyPoint  # noqa: E402
from app.services.rag import study_guide  # noqa: E402

Base.metadata.create_all(bind=engine)
db = SessionLocal()
q = db.query(Standard).filter(Standard.pdf_url.isnot(None))
targets = q.all() if args.all else q.filter(Standard.standard_number.in_(args.standards)).all()
if not targets:
    sys.exit("nothing to do: pass standard numbers or --all")

llm = study_guide.default_llm()
for std in sorted(targets, key=lambda s: s.standard_number):
    if args.skip_existing and db.query(StudyPoint).filter_by(standard_id=std.id).count():
        print(f"skip   {std.standard_number} (has notes)")
        continue
    path = _ensure_cached_pdf(std)
    if not path:
        print(f"FAILED {std.standard_number}: no PDF")
        continue
    t0 = time.time()
    guide = study_guide.build_guide(open(path, "rb").read(), std.title, llm)
    st = guide["stats"]
    if st["windows"] and st["failed_windows"] == st["windows"]:
        print(f"FAILED {std.standard_number}: AI unavailable")
        continue
    study_guide.replace_points(db, std.id, guide)
    print(f"ok     {std.standard_number}: {st['pages']}p, proposed {st['proposed']} -> verified {st['verified']} "
          f"({st['failed_windows']} failed windows, {time.time() - t0:.0f}s)")

print("exported", study_guide.export_points(db, args.out), "points to", args.out)
