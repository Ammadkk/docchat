"""Pipeline tests with a fake LLM and fake retriever (no Ollama / model downloads needed)."""

import pytest

from docchat import rag
from docchat.embeddings import cosine
from docchat.prompts import NOT_FOUND_MESSAGE

CHUNKS = [
    {"id": "d:0", "doc_id": "d", "filename": "a.pdf", "page_start": 3, "page_end": 3,
     "text": "The warranty lasts two years.", "similarity": 0.8},
    {"id": "d:1", "doc_id": "d", "filename": "a.pdf", "page_start": 4, "page_end": 5,
     "text": "Returns are accepted within 30 days.", "similarity": 0.7},
]


class FakeLLM:
    def __init__(self, pieces, rewrite="rewritten question"):
        self.pieces, self.rewrite, self.calls = pieces, rewrite, 0

    def complete(self, messages):
        return self.rewrite

    def stream(self, messages):
        self.calls += 1
        yield from self.pieces

    def health(self):
        return True, "ok"


class FakeCache:
    """In-memory stand-in for docchat.semantic_cache (exact cosine, same threshold logic)."""

    def __init__(self):
        self.entries = []  # (vector, scope, question, answer, sources)

    scope_key = staticmethod(lambda doc_ids: ",".join(sorted(doc_ids)) if doc_ids else "*")

    def lookup(self, embedding, scope, question):
        best = max(
            ((cosine(embedding, v), a, s) for v, sc, _, a, s in self.entries if sc == scope),
            default=None,
        )
        if best and best[0] >= rag.settings.semantic_cache_threshold:
            return {"answer": best[1], "sources": best[2]}
        return None

    def store(self, embedding, question, scope, answer, sources):
        self.entries.append((embedding, scope, question, answer, sources))

    def clear(self):
        self.entries.clear()


# Fake embeddings: questions about the warranty point one way, everything else another.
def fake_embed(question):
    q = question.lower()
    if "warranty" in q:
        return [1.0, 0.0, 0.0]
    if "return" in q:
        return [0.0, 1.0, 0.0]
    return [0.0, 0.0, 1.0]


@pytest.fixture(autouse=True)
def fake_pipeline(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda q, doc_ids=None, **kw: (CHUNKS, 0.8))
    monkeypatch.setattr(rag.citations, "support_scores", lambda answer, chunks: {1: 0.9})
    monkeypatch.setattr(rag, "embed_query", fake_embed)
    cache = FakeCache()
    monkeypatch.setattr(rag, "semantic_cache", cache)
    return cache


def run(llm, history=None, question="How long is the warranty?", **kwargs):
    events = list(rag.answer_stream(question, history, llm=llm, **kwargs))
    text = "".join(e["data"] for e in events if e["type"] == "token")
    return text, events[-1]["data"]


def test_streams_answer_and_marks_cited_sources():
    text, done = run(FakeLLM(["The warranty ", "lasts two years [1]", "."]))
    assert text == "The warranty lasts two years [1]."
    assert done["not_found"] is False
    assert [s["cited"] for s in done["sources"]] == [True, False]
    assert done["sources"][0]["page_start"] == 3


def test_not_found_sentinel_is_never_streamed():
    text, done = run(FakeLLM(["NOT_", "FOUND"]))
    assert text == NOT_FOUND_MESSAGE
    assert done["not_found"] and done["sources"] == []


def test_short_answer_starting_like_sentinel_is_kept():
    text, _ = run(FakeLLM(["NO", "pe [1]."]))
    assert text == "NOpe [1]."


def test_low_similarity_skips_llm(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda q, doc_ids=None, **kw: (CHUNKS, 0.1))
    llm = FakeLLM(["should not be used"])
    text, done = run(llm)
    assert text == NOT_FOUND_MESSAGE and llm.calls == 0


def test_follow_up_question_is_rewritten():
    history = [{"role": "user", "content": "Tell me about the warranty"},
               {"role": "assistant", "content": "It lasts two years [1]."}]
    _, done = run(FakeLLM(["Yes [1]."], rewrite="Is the warranty extendable?"), history)
    assert done["standalone_question"] == "Is the warranty extendable?"


# --- Semantic cache ---------------------------------------------------------------

ANSWER = ["The warranty lasts two years [1]."]


def test_repeated_question_is_served_from_cache():
    llm = FakeLLM(ANSWER)
    _, first = run(llm)
    text, second = run(llm, question="What is the warranty period?")  # same meaning
    assert first["cached"] is False and second["cached"] is True
    assert text == first["answer"] and second["sources"] == first["sources"]
    assert llm.calls == 1  # the LLM ran only for the first question


def test_different_question_misses_cache():
    llm = FakeLLM(ANSWER)
    run(llm)
    _, done = run(llm, question="Can I return it?")
    assert done["cached"] is False and llm.calls == 2


def test_cache_is_scoped_to_selected_documents():
    llm = FakeLLM(ANSWER)
    run(llm)  # all documents
    _, done = run(llm, doc_ids=["d"])
    assert done["cached"] is False and llm.calls == 2


def test_not_found_answers_are_not_cached(fake_pipeline):
    run(FakeLLM(["NOT_FOUND"]))
    assert fake_pipeline.entries == []


def test_use_cache_false_bypasses_cache(fake_pipeline):
    llm = FakeLLM(ANSWER)
    run(llm, use_cache=False)
    _, done = run(llm, use_cache=False)
    assert done["cached"] is False and llm.calls == 2 and fake_pipeline.entries == []


def test_cleared_cache_misses(fake_pipeline):
    llm = FakeLLM(ANSWER)
    run(llm)
    fake_pipeline.clear()  # e.g. a document was uploaded or deleted
    _, done = run(llm)
    assert done["cached"] is False and llm.calls == 2
