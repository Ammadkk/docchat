"""Local embeddings (free, runs on CPU).

bge models are asymmetric: queries get an instruction prefix, passages don't.
Vectors are L2-normalized, so dot product == cosine similarity.

Backend is chosen by `settings.model_backend`: "onnx" (default, no PyTorch) or
"torch" (sentence-transformers). Both produce the same vectors for bge models.
"""

import threading

import numpy as np

from .config import settings

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    with _lock:
        if _model is None:
            if settings.model_backend == "torch":
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(settings.embedding_model)
            else:
                from .onnx_models import OnnxEncoder

                _model = OnnxEncoder(settings.embedding_model)
    return _model


def _encode(texts: list[str]) -> np.ndarray:
    model = _get_model()
    if settings.model_backend == "torch":
        return model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    return model.encode(texts, batch_size=32)


def embed_passages(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _encode(texts).tolist()


def embed_query(question: str) -> list[float]:
    return _encode([settings.query_instruction + question])[0].tolist()


def cosine(a: list[float], b: list[float]) -> float:
    return float(np.dot(np.asarray(a), np.asarray(b)))
