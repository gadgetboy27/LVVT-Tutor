"""Export the local vector store's text chunks to data/corpus.json.gz.

The vector store (chroma_db/) is git-ignored, so a fresh deployment starts empty.
This file is what app.services.rag.bootstrap loads on first boot. Re-run after
indexing new standards locally:  python scripts/export_corpus.py
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag.bootstrap import CORPUS_PATH  # noqa: E402
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection  # noqa: E402


def main():
    coll = get_or_create_collection(get_chroma_client())
    data = coll.get(include=["documents", "metadatas"])
    rows = [{"id": i, "document": d, "metadata": m}
            for i, d, m in zip(data["ids"], data["documents"], data["metadatas"])]
    os.makedirs(os.path.dirname(CORPUS_PATH), exist_ok=True)
    with gzip.open(CORPUS_PATH, "wt", encoding="utf-8") as f:
        json.dump(rows, f)
    print(f"wrote {len(rows)} chunks to {CORPUS_PATH} ({os.path.getsize(CORPUS_PATH) // 1024} KB)")


if __name__ == "__main__":
    main()
