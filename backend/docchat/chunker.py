"""Token-aware chunking that never loses track of which page(s) a chunk came from.

Strategy:
1. Split each page into "units": paragraphs, falling back to sentences, falling back
   to hard token windows for very long sentences. Every unit keeps its page number.
2. Greedily pack units into chunks of at most `chunk_tokens` tokens.
3. Start each new chunk with the trailing units of the previous one (up to
   `overlap_tokens`) so facts that straddle a boundary are retrievable from either side.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

import tiktoken

_ENCODER: tiktoken.Encoding | None = None
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _encoder() -> tiktoken.Encoding:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text))


@dataclass
class Chunk:
    index: int
    text: str
    page_start: int
    page_end: int
    token_count: int


def _clean(text: str) -> str:
    # Re-join words hyphenated across line breaks: "embed-\nding" -> "embedding"
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def _units(pages: list[dict], max_tokens: int) -> Iterator[tuple[str, int]]:
    for page in pages:
        page_no = page["page"]
        for para in _PARAGRAPH_SPLIT.split(_clean(page["text"])):
            para = " ".join(para.split())
            if not para:
                continue
            if count_tokens(para) <= max_tokens:
                yield para, page_no
                continue
            for sentence in _SENTENCE_SPLIT.split(para):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if count_tokens(sentence) <= max_tokens:
                    yield sentence, page_no
                    continue
                tokens = _encoder().encode(sentence)
                for i in range(0, len(tokens), max_tokens):
                    yield _encoder().decode(tokens[i : i + max_tokens]), page_no


def chunk_pages(
    pages: list[dict], chunk_tokens: int = 500, overlap_tokens: int = 75
) -> list[Chunk]:
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be smaller than chunk_tokens")

    units = [(text, page, count_tokens(text)) for text, page in _units(pages, chunk_tokens)]
    chunks: list[Chunk] = []
    current: list[tuple[str, int, int]] = []
    current_tokens = 0

    def flush() -> None:
        chunks.append(
            Chunk(
                index=len(chunks),
                text=" ".join(u[0] for u in current),
                page_start=current[0][1],
                page_end=current[-1][1],
                token_count=current_tokens,
            )
        )

    for unit in units:
        if current and current_tokens + unit[2] > chunk_tokens:
            flush()
            keep: list[tuple[str, int, int]] = []
            kept_tokens = 0
            for prev in reversed(current):
                if kept_tokens + prev[2] > overlap_tokens:
                    break
                keep.insert(0, prev)
                kept_tokens += prev[2]
            if kept_tokens + unit[2] > chunk_tokens:
                keep, kept_tokens = [], 0
            current, current_tokens = keep, kept_tokens
        current.append(unit)
        current_tokens += unit[2]

    if current:
        flush()
    return chunks
