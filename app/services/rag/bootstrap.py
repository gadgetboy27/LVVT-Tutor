"""First-boot setup for a fresh deployment.

chroma_db/ is git-ignored, so a new server (e.g. Railway) starts with an empty
vector store and every quiz would fall back to the weak built-in questions.
ensure_corpus() loads the exported chunks (data/corpus.json.gz) once; seed_pdf_cache()
puts the bundled source PDFs onto the persistent cache directory.
"""
import gzip
import json
import os
import shutil
from typing import Dict

from app.core.config import settings
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection

CORPUS_PATH = os.path.join("data", "corpus.json.gz")
BUNDLED_PDF_DIR = "pdf_cache"
_BATCH = 200


def link_model_cache(target: str = None, home: str = None) -> Dict:
    """Point ~/.cache/chroma (where Chroma stores its embedding model) at a persistent dir."""
    target = target if target is not None else settings.MODEL_CACHE_DIR
    if not target:
        return {"skipped": "MODEL_CACHE_DIR not set"}
    link = os.path.join(home or os.path.expanduser("~"), ".cache", "chroma")
    os.makedirs(target, exist_ok=True)
    os.makedirs(os.path.dirname(link), exist_ok=True)
    if os.path.islink(link):
        return {"linked": link, "already": True}
    if os.path.isdir(link):
        # Keep anything already downloaded rather than throwing it away.
        for name in os.listdir(link):
            shutil.move(os.path.join(link, name), os.path.join(target, name))
        os.rmdir(link)
    os.symlink(target, link)
    return {"linked": link}


def ensure_corpus(path: str = CORPUS_PATH) -> Dict:
    """Populate an empty vector store from the exported corpus. No-op if it already has data."""
    collection = get_or_create_collection(get_chroma_client())
    existing = collection.count()
    if existing > 0:
        return {"skipped": "vector store already populated", "chunks": existing}
    if not os.path.exists(path):
        return {"skipped": f"{path} not found", "chunks": 0}

    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        collection.add(ids=[r["id"] for r in batch],
                       documents=[r["document"] for r in batch],
                       metadatas=[r["metadata"] for r in batch])
    return {"loaded": len(rows)}


def seed_pdf_cache(target: str = None, source: str = BUNDLED_PDF_DIR) -> Dict:
    """Copy bundled PDFs into the (possibly volume-backed) cache dir, never overwriting
    newer copies the refresher has already downloaded."""
    target = target or settings.PDF_CACHE_DIR
    if os.path.abspath(target) == os.path.abspath(source) or not os.path.isdir(source):
        return {"skipped": "cache dir is the bundled dir"}
    os.makedirs(target, exist_ok=True)
    copied = 0
    for name in os.listdir(source):
        dest = os.path.join(target, name)
        if name.endswith(".pdf") and not os.path.exists(dest):
            shutil.copy2(os.path.join(source, name), dest)
            copied += 1
    return {"copied": copied}
