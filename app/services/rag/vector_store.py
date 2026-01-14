import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings


def get_chroma_client():
    client = chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    return client


def get_or_create_collection(client, collection_name: str = "lvv_standards"):
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def add_documents(collection, documents: list, metadatas: list, ids: list):
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )


def query_documents(collection, query_text: str, n_results: int = 3):
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    return results
