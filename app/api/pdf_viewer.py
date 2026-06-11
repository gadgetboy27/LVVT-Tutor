import os
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.quiz import Standard
from app.services.rag.pdf_indexer import download_pdf, ensure_cache_dir

router = APIRouter(prefix="/api/pdf", tags=["PDF Viewer"])

PDF_CACHE_DIR = "pdf_cache"

# PDFs are content-addressed by a hash of their source URL, so a cached file
# never changes underneath a given standard. That makes them safe to cache hard
# in the browser, which is what keeps the quiz "Read Document" flow snappy.
_CACHE_CONTROL = "public, max-age=86400, immutable"


def _url_hash_name(pdf_url: str) -> str:
    """Filename the indexer uses when it caches a PDF: md5(url)[:8].pdf."""
    return hashlib.md5(pdf_url.encode()).hexdigest()[:8] + ".pdf"


def _candidate_paths(standard: Standard):
    """All on-disk locations a standard's PDF might live at, best match first."""
    names = []
    if standard.pdf_url:
        names.append(_url_hash_name(standard.pdf_url))
    # Legacy / direct naming used by older caches and manual drops.
    safe = standard.standard_number.replace("/", "_").replace("\\", "_")
    names.append(f"{safe}.pdf")
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        yield os.path.join(PDF_CACHE_DIR, name)


def _resolve_cached_pdf(standard: Standard):
    """Return the path to an already-cached PDF for this standard, or None."""
    for path in _candidate_paths(standard):
        if os.path.isfile(path):
            return path
    return None


def _ensure_cached_pdf(standard: Standard):
    """Resolve the cached PDF, lazily downloading + caching it on a miss.

    Returns a local path on success, or None if the PDF could not be obtained
    (so the caller can fall back to redirecting at the source URL)."""
    path = _resolve_cached_pdf(standard)
    if path:
        return path

    if not standard.pdf_url:
        return None

    content = download_pdf(standard.pdf_url)
    if not content:
        return None

    ensure_cache_dir()
    path = os.path.join(PDF_CACHE_DIR, _url_hash_name(standard.pdf_url))
    try:
        with open(path, "wb") as f:
            f.write(content)
    except OSError:
        return None
    return path


def _serve(path: str, standard_number: str, disposition: str) -> FileResponse:
    """FileResponse with caching + range support for fast, resumable delivery.

    Starlette's FileResponse already streams the file, sets Content-Length /
    ETag / Last-Modified, and honours HTTP Range requests, so PDF viewers can
    fetch pages on demand instead of pulling the whole document up front."""
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{standard_number}.pdf"',
            "Cache-Control": _CACHE_CONTROL,
            "Accept-Ranges": "bytes",
        },
    )


def _get_standard(standard_number: str, db: Session) -> Standard:
    standard = db.query(Standard).filter(
        Standard.standard_number == standard_number
    ).first()
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@router.get("/view/{standard_number}")
async def get_pdf_for_viewing(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = _get_standard(standard_number, db)

    path = _ensure_cached_pdf(standard)
    if path:
        return _serve(path, standard_number, "inline")

    # Couldn't cache it locally; send the browser straight to the source so the
    # quiz flow still gets a viewable PDF rather than an unrenderable JSON blob.
    if standard.pdf_url:
        return RedirectResponse(url=standard.pdf_url)

    raise HTTPException(status_code=404, detail="PDF not available")


@router.get("/download/{standard_number}")
async def download_pdf_file(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = _get_standard(standard_number, db)

    path = _ensure_cached_pdf(standard)
    if path:
        return _serve(path, standard_number, "attachment")

    if standard.pdf_url:
        return RedirectResponse(url=standard.pdf_url)

    raise HTTPException(status_code=404, detail="PDF not available")


@router.get("/available")
async def list_available_pdfs(
    db: Session = Depends(get_db)
):
    standards = db.query(Standard).all()

    available = []
    for standard in standards:
        path = _resolve_cached_pdf(standard)
        if not path:
            continue
        available.append({
            "standard_number": standard.standard_number,
            "title": standard.title,
            "filename": os.path.basename(path),
            "size_kb": os.path.getsize(path) // 1024,
            "view_url": f"/api/pdf/view/{standard.standard_number}",
            "download_url": f"/api/pdf/download/{standard.standard_number}",
        })

    return {"pdfs": available, "total": len(available)}


@router.get("/info/{standard_number}")
async def get_pdf_info(
    standard_number: str,
    db: Session = Depends(get_db)
):
    standard = _get_standard(standard_number, db)

    path = _resolve_cached_pdf(standard)
    is_cached = path is not None
    file_size = os.path.getsize(path) if is_cached else 0
    # Even when not yet on disk, the PDF is still viewable (it will be fetched
    # and cached on first request) as long as we have a source URL.
    is_viewable = is_cached or bool(standard.pdf_url)

    return {
        "standard_number": standard_number,
        "title": standard.title,
        "pdf_url": standard.pdf_url,
        "is_cached_locally": is_cached,
        "file_size_kb": file_size // 1024 if is_cached else None,
        "view_url": f"/api/pdf/view/{standard_number}" if is_viewable else None,
        "download_url": f"/api/pdf/download/{standard_number}" if is_viewable else None,
    }
