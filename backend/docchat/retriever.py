"""Hybrid retrieval: dense vectors + BM25, fused with Reciprocal Rank Fusion,
optionally reranked with a cross-encoder."""

import threading

from . import vector_store
from .bm25_index import bm25_index
from .config import settings
from .embeddings import embed_query

_reranker = None
_reranker_lock = threading.Lock()


def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """score(d) = sum over lists of 1 / (k + rank). Robust to the two retrievers
    using incomparable score scales."""
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            scores[item["id"]] = scores.get(item["id"], 0.0) + 1.0 / (k + rank)
            items[item["id"]] = {**items.get(item["id"], {}), **item}
    fused = [{**items[i], "rrf": s} for i, s in scores.items()]
    fused.sort(key=lambda x: x["rrf"], reverse=True)
    return fused


def _rerank(question: str, candidates: list[dict]) -> list[dict]:
    global _reranker
    with _reranker_lock:
        if _reranker is None:
            if settings.model_backend == "torch":
                from sentence_transformers import CrossEncoder

                _reranker = CrossEncoder(settings.reranker_model)
            else:
                from .onnx_models import OnnxCrossEncoder

                _reranker = OnnxCrossEncoder(settings.reranker_model)
    scores = _reranker.predict([(question, c["text"]) for c in candidates])
    for c, s in zip(candidates, scores):
        c["rerank"] = float(s)
    return sorted(candidates, key=lambda c: c["rerank"], reverse=True)


def retrieve(
    question: str,
    doc_ids: list[str] | None = None,
    top_k: int | None = None,
    use_bm25: bool = True,
    use_reranker: bool | None = None,
) -> tuple[list[dict], float]:
    """Return (top chunks, best dense similarity). The similarity is used as a
    cheap "is anything relevant here at all?" signal."""
    top_k = top_k or settings.top_k
    use_reranker = settings.use_reranker if use_reranker is None else use_reranker

    dense = vector_store.query(embed_query(question), settings.candidate_k, doc_ids)
    best_similarity = max((d["similarity"] for d in dense), default=0.0)
    lists = [dense]
    if use_bm25:
        lists.append(bm25_index.query(question, settings.candidate_k, doc_ids))

    candidates = reciprocal_rank_fusion(lists)
    if use_reranker and candidates:
        candidates = _rerank(question, candidates[: settings.candidate_k])
    return candidates[:top_k], best_similarity
