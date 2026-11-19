"""The question-answering pipeline: rewrite → retrieve → generate (streamed) → cite."""

from collections.abc import Iterator

from . import citations, semantic_cache
from .config import settings
from .embeddings import embed_query
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
    use_cache: bool | None = None,
) -> Iterator[dict]:
    """Yields events: {"type": "token", "data": str}, then
    {"type": "done", "data": {"answer", "sources", "standalone_question", "not_found", "cached"}}."""
    llm = llm or get_llm()
    use_cache = settings.semantic_cache_enabled if use_cache is None else use_cache
    standalone = rewrite_question(llm, question, history or [])
    query_embedding = embed_query(standalone)  # shared by the cache lookup and retrieval
    scope = semantic_cache.scope_key(doc_ids)

    # Semantic cache: a question that means the same as an earlier one gets the
    # earlier answer instantly, without retrieval or the LLM.
    if use_cache:
        hit = semantic_cache.lookup(query_embedding, scope, standalone)
        if hit:
            yield {"type": "token", "data": hit["answer"]}
            yield {
                "type": "done",
                "data": {
                    "answer": hit["answer"],
                    "sources": hit["sources"],
                    "standalone_question": standalone,
                    "not_found": False,
                    "cached": True,
                },
            }
            return

    chunks, best_similarity = retrieve(standalone, doc_ids, query_embedding=query_embedding)

    def not_found() -> Iterator[dict]:
        yield {"type": "token", "data": NOT_FOUND_MESSAGE}
        yield {
            "type": "done",
            "data": {
                "answer": NOT_FOUND_MESSAGE,
                "sources": [],
                "standalone_question": standalone,
                "not_found": True,
                "cached": False,
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
    sources = build_sources(answer, chunks)
    # Only complete, grounded answers are cached. Not-found answers are already instant,
    # and a stopped stream never gets here.
    if use_cache:
        semantic_cache.store(query_embedding, standalone, scope, answer, sources)
    yield {
        "type": "done",
        "data": {
            "answer": answer,
            "sources": sources,
            "standalone_question": standalone,
            "not_found": False,
            "cached": False,
        },
    }


def answer(question: str, history: list[dict] | None = None, doc_ids: list[str] | None = None,
           llm: LLM | None = None, use_cache: bool | None = None) -> dict:
    """Non-streaming convenience wrapper (used by the CLI and evals)."""
    result: dict = {}
    for event in answer_stream(question, history, doc_ids, llm, use_cache):
        if event["type"] == "done":
            result = event["data"]
    return result
