"""Build a verified study guide from an official PDF.

The AI is only allowed to *select* passages and restate them briefly. Every selected
passage must come with an exact quote, and the quote is machine-checked against the
text of the PDF: a point whose quote can't be found on a page is discarded, so nothing
in the guide can be something the document doesn't say. LVVTA doesn't publish what is
examined, so "importance" is the model's judgement of what a certifier must know, not
inside knowledge of the exam.
"""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Callable, Dict, List, Optional

from pypdf import PdfReader

CATEGORIES = ["Requirement", "Limit or figure", "Prohibition", "Procedure", "Definition",
              "Exception", "Responsibility"]
WINDOW_CHARS = 6500
MIN_QUOTE_CHARS = 30        # alphanumeric characters; shorter "quotes" prove nothing
MAX_POINTS_PER_WINDOW = 12

SYSTEM = """You are preparing study notes for people sitting the LVV (Low Volume Vehicle) Certifier written test in New Zealand.
The test is closed-book and asks them to apply the standards and procedures to real vehicles safely.
Select ONLY the passages worth memorising: specific requirements, limits and figures, things that must or must not be done,
procedures and who is responsible, key definitions, and exceptions. IGNORE background, history, purpose statements, disclaimers,
contact details, tables of contents, version notes, cross-references with no rule in them, and general explanation."""


def extract_pages(pdf_bytes: bytes) -> List[str]:
    reader = PdfReader(BytesIO(pdf_bytes))
    return [(p.extract_text() or "") for p in reader.pages]


def source_hash(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _squash(text: str) -> str:
    """Letters and digits only, lower-cased: immune to line breaks, hyphenation, smart
    quotes and spacing differences between the PDF's extracted text and the model's copy."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def locate_quote(quote: str, pages: List[str], near: Optional[int] = None) -> Optional[int]:
    """1-based page number whose text contains the quote, or None. Prefers `near` (the page
    the model claimed) and its neighbours, then falls back to the whole document."""
    q = _squash(quote)
    if len(q) < MIN_QUOTE_CHARS:
        return None
    squashed = [_squash(p) for p in pages]
    order = list(range(len(pages)))
    if near and 1 <= near <= len(pages):
        order.sort(key=lambda i: abs(i - (near - 1)))
    for i in order:
        if q in squashed[i]:
            return i + 1
    return None


def make_windows(pages: List[str], max_chars: int = WINDOW_CHARS) -> List[List[tuple]]:
    """Group consecutive pages into prompt-sized windows of (page_no, text)."""
    windows, current, size = [], [], 0
    for i, text in enumerate(pages, start=1):
        text = text.strip()
        if not text:
            continue
        if current and size + len(text) > max_chars:
            windows.append(current)
            current, size = [], 0
        current.append((i, text))
        size += len(text)
    if current:
        windows.append(current)
    return windows


def _prompt(window: List[tuple], title: str) -> str:
    body = "\n\n".join(f"[[PAGE {n}]]\n{t}" for n, t in window)
    return f"""Document: "{title}"

Return a JSON array (and nothing else) of at most {MAX_POINTS_PER_WINDOW} items. Return [] if these pages contain nothing worth memorising.
Each item:
{{"page": <page number from the [[PAGE n]] marker>,
  "category": one of {json.dumps(CATEGORIES)},
  "importance": 1 (must know) | 2 (should know) | 3 (useful),
  "point": a plain-English restatement in 30 words or fewer that adds NO facts not in the quote,
  "quote": an EXACT contiguous copy of 40-300 characters from the page text (no paraphrasing, no ellipses),
  "section": the clause number such as "2.2(3)(c)" if visible, else ""}}

PAGES:
{body}"""


def _parse(raw: str) -> List[dict]:
    start, end = raw.find("["), raw.rfind("]") + 1
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)]


def build_guide(pdf_bytes: bytes, title: str, llm: Callable[[str, str, int], str],
                workers: int = 4) -> Dict:
    """Run the pipeline. `llm(system, user, max_tokens) -> str` is injected so tests need no AI."""
    pages = extract_pages(pdf_bytes)
    windows = make_windows(pages)

    def run(window):
        try:
            return _parse(llm(SYSTEM, _prompt(window, title), 3500))
        except Exception as e:
            print(f"study guide window failed: {e}")
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run, windows))

    points, seen = [], set()
    proposed = failed_windows = 0
    for window_result in results:
        if window_result is None:
            failed_windows += 1
            continue
        for item in window_result:
            proposed += 1
            quote = str(item.get("quote") or "")
            page = locate_quote(quote, pages, near=item.get("page") if isinstance(item.get("page"), int) else None)
            key = _squash(quote)
            if page is None or key in seen or not str(item.get("point") or "").strip():
                continue
            seen.add(key)
            category = item.get("category") if item.get("category") in CATEGORIES else "Requirement"
            importance = item.get("importance") if item.get("importance") in (1, 2, 3) else 2
            points.append({"page": page, "category": category, "importance": importance,
                           "point": str(item["point"]).strip(), "quote": " ".join(quote.split()),
                           "section": str(item.get("section") or "").strip()})
    points.sort(key=lambda p: (p["page"], p["importance"]))
    return {
        "points": points,
        "stats": {"pages": len(pages), "windows": len(windows), "failed_windows": failed_windows,
                  "proposed": proposed, "verified": len(points),
                  "pages_with_points": sorted({p["page"] for p in points})},
        "source_hash": source_hash(pdf_bytes),
    }


# --------------------------------------------------------------------------- persistence
def default_llm() -> Callable[[str, str, int], str]:
    from app.core.config import settings
    from app.services.rag import ai_service
    model = settings.STUDY_GUIDE_MODEL or None
    return lambda system, user, max_tokens: ai_service._llm_chat(system, user, max_tokens, model)


def replace_points(db, standard_id: int, guide: Dict) -> int:
    from app.models.study import StudyPoint
    db.query(StudyPoint).filter(StudyPoint.standard_id == standard_id).delete()
    for p in guide["points"]:
        db.add(StudyPoint(standard_id=standard_id, source_hash=guide.get("source_hash"), **p))
    db.commit()
    return len(guide["points"])


def export_points(db, path: str) -> int:
    """Write every stored point, keyed by standard_number, so a fresh deployment can load them."""
    import gzip
    from app.models.quiz import Standard
    from app.models.study import StudyPoint
    numbers = {s.id: s.standard_number for s in db.query(Standard).all()}
    rows = [{"standard_number": numbers[p.standard_id], "page": p.page, "category": p.category,
             "importance": p.importance, "point": p.point, "quote": p.quote, "section": p.section,
             "source_hash": p.source_hash}
            for p in db.query(StudyPoint).order_by(StudyPoint.standard_id, StudyPoint.page, StudyPoint.id).all()
            if p.standard_id in numbers]
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(rows, f)
    return len(rows)


def load_points(db, path: str) -> Dict:
    """Insert shipped study points for any standard that has none yet. Idempotent."""
    import gzip
    import os
    from app.models.quiz import Standard
    from app.models.study import StudyPoint
    if not os.path.exists(path):
        return {"skipped": f"{path} not found"}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    ids = {s.standard_number: s.id for s in db.query(Standard).all()}
    have = {sid for (sid,) in db.query(StudyPoint.standard_id).distinct().all()}
    added, standards = 0, set()
    for r in rows:
        sid = ids.get(r["standard_number"])
        if sid is None or sid in have:
            continue
        db.add(StudyPoint(standard_id=sid, **{k: r[k] for k in ("page", "category", "importance", "point",
                                                                  "quote", "section", "source_hash")}))
        added += 1
        standards.add(r["standard_number"])
    db.commit()
    return {"added": added, "standards": len(standards)}
