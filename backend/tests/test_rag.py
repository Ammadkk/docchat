"""Pipeline tests with a fake LLM and fake retriever (no Ollama / model downloads needed)."""

import pytest

from docchat import rag
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


@pytest.fixture(autouse=True)
def fake_pipeline(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda q, doc_ids=None: (CHUNKS, 0.8))
    monkeypatch.setattr(rag.citations, "support_scores", lambda answer, chunks: {1: 0.9})


def run(llm, history=None):
    events = list(rag.answer_stream("How long is the warranty?", history, llm=llm))
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
    monkeypatch.setattr(rag, "retrieve", lambda q, doc_ids=None: (CHUNKS, 0.1))
    llm = FakeLLM(["should not be used"])
    text, done = run(llm)
    assert text == NOT_FOUND_MESSAGE and llm.calls == 0


def test_follow_up_question_is_rewritten():
    history = [{"role": "user", "content": "Tell me about the warranty"},
               {"role": "assistant", "content": "It lasts two years [1]."}]
    _, done = run(FakeLLM(["Yes [1]."], rewrite="Is the warranty extendable?"), history)
    assert done["standalone_question"] == "Is the warranty extendable?"
