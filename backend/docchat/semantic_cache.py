"""Semantic answer cache: reuse an earlier answer when a new question means the same thing.

Keyed by the embedding of the *standalone* question (after follow-up rewriting), so
"what about the second one?" can't collide across chats. Entries are scoped to the
selected documents, and the whole cache is cleared whenever a document is added or
removed, because a new PDF can change the best answer.

Stored in its own Chroma collection next to the chunks, so it survives restarts.
"""

import json
import logging
import re
from datetime import UTC, datetime
from uuid import uuid4

from .config import settings
from .vector_store import get_client

log = logging.getLogger("docchat.cache")
_COLLECTION = "answer_cache"


def _collection():
    return get_client().get_or_create_collection(
        _COLLECTION, metadata={"hnsw:space": "cosine"}, embedding_function=None
    )


def scope_key(doc_ids: list[str] | None) -> str:
    """Which documents the answer was drawn from: '*' = all, else sorted ids."""
    return ",".join(sorted(set(doc_ids))) if doc_ids else "*"


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


def lookup(embedding: list[float], scope: str, question: str) -> dict | None:
    """Return the cached result for the most similar question in this scope, if it is
    similar enough (>= settings.semantic_cache_threshold) and mentions the same numbers."""
    col = _collection()
    if col.count() == 0:
        return None
    res = col.query(
        query_embeddings=[embedding],
        n_results=1,
        where={"scope": scope},
        include=["documents", "metadatas", "distances"],
    )
    if not res["ids"][0]:
        return None
    similarity = 1.0 - float(res["distances"][0][0])
    cached_question = res["documents"][0][0]
    if similarity < settings.semantic_cache_threshold:
        log.debug("Cache miss (best %.3f: %r)", similarity, cached_question)
        return None
    if _numbers(cached_question) != _numbers(question):
        # Embeddings barely separate "revenue in 2023" from "revenue in 2024" (~0.90),
        # so any difference in numbers is treated as a different question.
        log.debug("Cache miss (numbers differ): %r", cached_question)
        return None
    meta = res["metadatas"][0][0]
    log.info("Cache hit (similarity %.3f): %r", similarity, cached_question)
    return {
        "answer": meta["answer"],
        "sources": json.loads(meta["sources_json"]),
        "cached_question": cached_question,
        "cache_similarity": similarity,
    }


def store(embedding: list[float], question: str, scope: str, answer: str, sources: list[dict]) -> None:
    _collection().add(
        ids=[uuid4().hex],
        embeddings=[embedding],
        documents=[question],
        metadatas=[
            {
                "scope": scope,
                "answer": answer,
                "sources_json": json.dumps(sources),
                "created_at": datetime.now(UTC).isoformat(),
            }
        ],
    )


def clear() -> None:
    """Drop every cached answer (call whenever the document index changes)."""
    client = get_client()
    try:
        client.delete_collection(_COLLECTION)
    except Exception:  # collection doesn't exist yet
        pass


def count() -> int:
    return _collection().count()
