"""The real semantic_cache module against an in-memory Chroma (no model downloads)."""

import chromadb
import pytest

from docchat import semantic_cache as sc


@pytest.fixture(autouse=True)
def memory_chroma(monkeypatch):
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(sc, "get_client", lambda: client)
    sc.clear()
    yield
    sc.clear()


V = [1.0, 0.0, 0.0]
NEAR = [0.99, 0.14, 0.0]  # cosine ~0.99
FAR = [0.6, 0.8, 0.0]  # cosine 0.6


def test_hit_returns_answer_and_sources():
    sc.store(V, "How long is the warranty?", "*", "Two years [1].", [{"n": 1, "page_start": 3}])
    hit = sc.lookup(NEAR, "*", "How long is the warranty period?")
    assert hit["answer"] == "Two years [1]." and hit["sources"][0]["page_start"] == 3


def test_dissimilar_question_misses():
    sc.store(V, "How long is the warranty?", "*", "Two years [1].", [])
    assert sc.lookup(FAR, "*", "Can I return it?") is None


def test_scope_must_match():
    sc.store(V, "How long is the warranty?", sc.scope_key(["b", "a"]), "x", [])
    assert sc.lookup(V, "*", "How long is the warranty?") is None
    assert sc.lookup(V, sc.scope_key(["a", "b"]), "How long is the warranty?") is not None


def test_different_numbers_never_match():
    sc.store(V, "What was revenue in 2023?", "*", "$5M [1].", [])
    assert sc.lookup(V, "*", "What was revenue in 2024?") is None
    assert sc.lookup(V, "*", "what was revenue in 2023") is not None


def test_clear_empties_cache():
    sc.store(V, "q", "*", "a", [])
    sc.clear()
    assert sc.count() == 0 and sc.lookup(V, "*", "q") is None
