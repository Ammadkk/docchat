"""The question-answering pipeline: rewrite → retrieve → generate (streamed) → cite."""

from collections.abc import Iterator

from . import citations
from .config import settings
from .llm import LLM, get_llm
from .prompts import NOT_FOUND_MESSAGE, NOT_FOUND_TOKEN, answer_messages, rewrite_messages
from .retriever import retrieve


def rewrite_question(llm: LLM, question: str, history: list[dict]) -> str:
    if not history:
        return question
    recent = history[-settings.history_turns :]
    rewritten = llm.complete(rewrite_messages(question, recent)).strip().strip('"')
    return rewritten or question


def build_sources(answer: str, chunks: list[dict]) -> list[dict]:
    cited = set(citations.cited_numbers(answer, len(chunks)))
    support = citations.support_scores(answer, chunks) if cited else {}
    sources = []
    for n, c in enumerate(chunks, start=1):
        score = support.get(n)
        sources.append(
            {
                "n": n,
                "doc_id": c["doc_id"],
                "filename": c["filename"],
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "text": c["text"],
                "similarity": c.get("similarity"),
                "cited": n in cited,
                "support": score,
                "low_confidence": score is not None
                and score < settings.low_confidence_threshold,
            }
        )
    return sources


def answer_stream(
    question: str,
    history: list[dict] | None = None,
    doc_ids: list[str] | None = None,
    llm: LLM | None = None,
) -> Iterator[dict]:
    """Yields events: {"type": "token", "data": str}, then
    {"type": "done", "data": {"answer", "sources", "standalone_question", "not_found"}}."""
    llm = llm or get_llm()
    standalone = rewrite_question(llm, question, history or [])
    chunks, best_similarity = retrieve(standalone, doc_ids)

    def not_found() -> Iterator[dict]:
        yield {"type": "token", "data": NOT_FOUND_MESSAGE}
        yield {
            "type": "done",
            "data": {
                "answer": NOT_FOUND_MESSAGE,
                "sources": [],
                "standalone_question": standalone,
                "not_found": True,
            },
        }

    # Guard 1: nothing remotely relevant was retrieved → don't even ask the LLM.
    if not chunks or best_similarity < settings.min_similarity:
        yield from not_found()
        return

    # Stream tokens, but hold back the first few characters until we know the
    # model isn't replying with the NOT_FOUND sentinel (guard 2).
    full = ""
    buffer = ""
    decided = False
    for piece in llm.stream(answer_messages(standalone, chunks)):
        full += piece
        if decided:
            yield {"type": "token", "data": piece}
            continue
        buffer += piece
        head = buffer.lstrip()
        if len(head) < len(NOT_FOUND_TOKEN) and NOT_FOUND_TOKEN.startswith(head):
            continue
        if head.startswith(NOT_FOUND_TOKEN):
            yield from not_found()
            return
        decided = True
        yield {"type": "token", "data": buffer}

    if not decided:
        head = buffer.strip()
        if not head or head.startswith(NOT_FOUND_TOKEN):
            yield from not_found()
            return
        yield {"type": "token", "data": buffer}

    answer = citations.strip_invalid(full.strip(), len(chunks))
    yield {
        "type": "done",
        "data": {
            "answer": answer,
            "sources": build_sources(answer, chunks),
            "standalone_question": standalone,
            "not_found": False,
        },
    }


def answer(question: str, history: list[dict] | None = None, doc_ids: list[str] | None = None,
           llm: LLM | None = None) -> dict:
    """Non-streaming convenience wrapper (used by the CLI and evals)."""
    result: dict = {}
    for event in answer_stream(question, history, doc_ids, llm):
        if event["type"] == "done":
            result = event["data"]
    return result
