import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings


# Building a PersistentClient opens the on-disk store and is too expensive to
# repeat per request, so cache the client and collections process-wide. Chroma's
# PersistentClient is safe to share across threads.
_client = None
_collections = {}


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _client


def get_or_create_collection(client, collection_name: str = "lvv_standards"):
    collection = _collections.get(collection_name)
    if collection is None:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        _collections[collection_name] = collection
    return collection


def add_documents(collection, documents: list, metadatas: list, ids: list):
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )


def query_documents(collection, query_text: str, n_results: int = 3, where: dict = None):
    # `where` scopes the search to matching metadata (e.g. a single
    # standard_number) so callers can pull content for one standard instead of
    # the whole corpus.
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
    )
    return results
