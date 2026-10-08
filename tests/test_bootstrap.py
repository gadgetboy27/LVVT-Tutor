"""First-boot corpus loading and PDF cache seeding for fresh deployments."""
import gzip
import json
import os

from app.services.rag import bootstrap


class FakeCollection:
    def __init__(self, n=0):
        self.n, self.added = n, []

    def count(self):
        return self.n

    def add(self, ids, documents, metadatas):
        self.added.append((ids, documents, metadatas))
        self.n += len(ids)


def _corpus(tmp_path, n):
    path = tmp_path / "corpus.json.gz"
    rows = [{"id": f"s_{i}", "document": f"text {i}", "metadata": {"standard_number": "S"}} for i in range(n)]
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(rows, f)
    return str(path)


def _patch(monkeypatch, coll):
    monkeypatch.setattr(bootstrap, "get_chroma_client", lambda: None)
    monkeypatch.setattr(bootstrap, "get_or_create_collection", lambda c: coll)


def test_loads_into_empty_store_in_batches(monkeypatch, tmp_path):
    coll = FakeCollection()
    _patch(monkeypatch, coll)
    out = bootstrap.ensure_corpus(_corpus(tmp_path, 450))
    assert out == {"loaded": 450}
    assert [len(b[0]) for b in coll.added] == [200, 200, 50]


def test_populated_store_is_left_alone(monkeypatch, tmp_path):
    coll = FakeCollection(n=10)
    _patch(monkeypatch, coll)
    out = bootstrap.ensure_corpus(_corpus(tmp_path, 5))
    assert "already populated" in out["skipped"] and coll.added == []


def test_missing_corpus_file_is_not_an_error(monkeypatch, tmp_path):
    _patch(monkeypatch, FakeCollection())
    assert "not found" in bootstrap.ensure_corpus(str(tmp_path / "nope.json.gz"))["skipped"]


def test_pdf_cache_seed_copies_missing_but_never_overwrites(tmp_path):
    src, dst = tmp_path / "bundled", tmp_path / "volume"
    src.mkdir(); dst.mkdir()
    (src / "a.pdf").write_bytes(b"old-a")
    (src / "b.pdf").write_bytes(b"old-b")
    (src / "notes.txt").write_bytes(b"ignore")
    (dst / "a.pdf").write_bytes(b"newer-a")          # already refreshed on the volume
    assert bootstrap.seed_pdf_cache(str(dst), str(src)) == {"copied": 1}
    assert (dst / "a.pdf").read_bytes() == b"newer-a"
    assert (dst / "b.pdf").read_bytes() == b"old-b"
    assert not (dst / "notes.txt").exists()


def test_seed_is_noop_when_cache_is_the_bundled_dir(tmp_path):
    d = tmp_path / "same"; d.mkdir()
    assert "skipped" in bootstrap.seed_pdf_cache(str(d), str(d))


def test_model_cache_symlink(tmp_path):
    target, home = tmp_path / "volume" / "models", tmp_path / "home"
    out = bootstrap.link_model_cache(str(target), str(home))
    link = home / ".cache" / "chroma"
    assert out == {"linked": str(link)} and link.is_symlink()
    (target / "model.bin").write_bytes(b"x")
    assert (link / "model.bin").exists()                       # writes land on the volume
    assert bootstrap.link_model_cache(str(target), str(home))["already"] is True


def test_model_cache_keeps_existing_downloads(tmp_path):
    home = tmp_path / "home"; (home / ".cache" / "chroma").mkdir(parents=True)
    (home / ".cache" / "chroma" / "have.bin").write_bytes(b"x")
    target = tmp_path / "vol"
    bootstrap.link_model_cache(str(target), str(home))
    assert (target / "have.bin").exists()


def test_model_cache_disabled_without_setting():
    assert "skipped" in bootstrap.link_model_cache("")
