"""Keyword (BM25) search over all chunks. Catches exact terms, names, numbers and IDs
that dense embeddings tend to miss. Built lazily from Chroma and rebuilt after changes."""

import re
import threading

from rank_bm25 import BM25Okapi

from . import vector_store

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bm25: BM25Okapi | None = None
        self._chunks: list[dict] = []
        self._dirty = True

    def invalidate(self) -> None:
        with self._lock:
            self._dirty = True

    def _ensure_built(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            self._chunks = vector_store.all_chunks()
            corpus = [tokenize(c["text"]) for c in self._chunks]
            self._bm25 = BM25Okapi(corpus) if corpus else None
            self._dirty = False

    def query(self, question: str, n: int, doc_ids: list[str] | None = None) -> list[dict]:
        self._ensure_built()
        terms = tokenize(question)
        if self._bm25 is None or not terms:
            return []
        scores = self._bm25.get_scores(terms)
        allowed = set(doc_ids) if doc_ids else None
        results: list[dict] = []
        for i in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True):
            if scores[i] <= 0:
                break
            chunk = self._chunks[i]
            if allowed is not None and chunk["doc_id"] not in allowed:
                continue
            results.append({**chunk, "bm25": float(scores[i])})
            if len(results) >= n:
                break
        return results


bm25_index = BM25Index()
