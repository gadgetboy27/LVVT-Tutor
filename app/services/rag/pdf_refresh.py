"""Keep the indexed LVVTA PDFs in step with the source documents.

For every standard with a pdf_url: a cheap HEAD request compares the server's
Last-Modified with what we stored; only when the source is newer (or we have no
record) do we re-download, and only when the bytes actually differ (sha256) do we
re-index. Run at startup, then on an interval (see main.lifespan), or on demand
via POST /api/standards/refresh-pdfs.
"""
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Optional

import requests

from app.core.database import SessionLocal
from app.models.quiz import Standard
from app.services.rag.pdf_indexer import index_pdf_to_vectordb

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_lock = threading.Lock()
_last_run: Dict = {}


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def remote_last_modified(url: str) -> Optional[datetime]:
    """The source PDF's Last-Modified (naive UTC), or None if unavailable."""
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        header = resp.headers.get("Last-Modified")
        if resp.ok and header:
            return _naive_utc(parsedate_to_datetime(header))
    except Exception:
        pass
    return None


def refresh_stale_pdfs(force: bool = False) -> Dict:
    """Re-index any standard whose source PDF changed. force=True re-downloads all
    (unchanged content is still detected by hash and not re-indexed)."""
    global _last_run
    if not _lock.acquire(blocking=False):
        return {"skipped": "a refresh is already running"}

    summary = {"started_at": datetime.utcnow().isoformat(), "checked": 0, "fresh": 0,
               "reindexed": [], "unchanged": 0, "failed": []}
    db = SessionLocal()
    try:
        for std in db.query(Standard).filter(Standard.pdf_url.isnot(None)).all():
            summary["checked"] += 1
            remote_lm = remote_last_modified(std.pdf_url)
            stored = _naive_utc(std.last_modified)
            if not force and remote_lm and stored and remote_lm <= stored:
                summary["fresh"] += 1
                continue

            result = index_pdf_to_vectordb(
                std.standard_number, std.title, std.pdf_url, std.category or "General",
                refresh=True, expected_hash=std.content_hash,
            )
            if not result.get("success"):
                summary["failed"].append({"standard": std.standard_number, "error": result.get("error")})
                continue

            std.content_hash = result["content_hash"]
            if remote_lm:
                std.last_modified = remote_lm
            std.is_processed = True
            db.commit()
            if result.get("unchanged"):
                summary["unchanged"] += 1
            else:
                summary["reindexed"].append(std.standard_number)
    except Exception as e:
        db.rollback()
        summary["error"] = str(e)
    finally:
        db.close()
        summary["finished_at"] = datetime.utcnow().isoformat()
        _last_run = summary
        _lock.release()
    return summary


def last_refresh() -> Dict:
    return _last_run or {"message": "no refresh has run yet"}
