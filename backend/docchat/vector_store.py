"""ChromaDB (persistent, local) wrapper. One collection holds every chunk;
metadata carries doc_id / filename / pages so results can be filtered and cited."""

import threading

import chromadb

from .chunker import Chunk
from .config import settings

_client = None
_lock = threading.Lock()
_COLLECTION = "chunks"
_ADD_BATCH = 1000


def _collection():
    global _client
    with _lock:
        if _client is None:
            settings.ensure_dirs()
            _client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return _client.get_or_create_collection(
        _COLLECTION, metadata={"hnsw:space": "cosine"}, embedding_function=None
    )


def _where(doc_ids: list[str] | None):
    return {"doc_id": {"$in": doc_ids}} if doc_ids else None


def _row(chunk_id: str, text: str, meta: dict) -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "doc_id": meta["doc_id"],
        "filename": meta["filename"],
        "page_start": int(meta["page_start"]),
        "page_end": int(meta["page_end"]),
        "chunk_index": int(meta["chunk_index"]),
    }


def add_chunks(
    doc_id: str, filename: str, chunks: list[Chunk], embeddings: list[list[float]]
) -> None:
    col = _collection()
    for start in range(0, len(chunks), _ADD_BATCH):
        batch = chunks[start : start + _ADD_BATCH]
        col.add(
            ids=[f"{doc_id}:{c.index}" for c in batch],
            embeddings=embeddings[start : start + _ADD_BATCH],
            documents=[c.text for c in batch],
            metadatas=[
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "chunk_index": c.index,
                }
                for c in batch
            ],
        )


def query(embedding: list[float], n: int, doc_ids: list[str] | None = None) -> list[dict]:
    col = _collection()
    total = col.count()
    if total == 0:
        return []
    res = col.query(
        query_embeddings=[embedding],
        n_results=min(n, total),
        where=_where(doc_ids),
        include=["documents", "metadatas", "distances"],
    )
    rows = []
    for chunk_id, text, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        row = _row(chunk_id, text, meta)
        row["similarity"] = 1.0 - float(dist)  # cosine distance -> similarity
        rows.append(row)
    return rows


def all_chunks(doc_ids: list[str] | None = None) -> list[dict]:
    res = _collection().get(where=_where(doc_ids), include=["documents", "metadatas"])
    return [_row(i, t, m) for i, t, m in zip(res["ids"], res["documents"], res["metadatas"])]


def delete_document(doc_id: str) -> None:
    _collection().delete(where={"doc_id": doc_id})


def count() -> int:
    return _collection().count()
