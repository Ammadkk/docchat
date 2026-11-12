"""Parse [n] citation markers from an answer, validate them against the sources that were
actually provided, and score how well each cited source supports the sentences citing it."""

import re

from .embeddings import cosine, embed_passages

CITATION = re.compile(r"\[(\d+)\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def cited_numbers(answer: str, n_sources: int) -> list[int]:
    """Valid source numbers in order of first appearance."""
    seen: list[int] = []
    for m in CITATION.finditer(answer):
        n = int(m.group(1))
        if 1 <= n <= n_sources and n not in seen:
            seen.append(n)
    return seen


def strip_invalid(answer: str, n_sources: int) -> str:
    return CITATION.sub(
        lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", answer
    )


def sentences_by_source(answer: str, n_sources: int) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for sentence in _SENTENCE.split(answer):
        numbers = {int(n) for n in CITATION.findall(sentence)}
        claim = CITATION.sub("", sentence).strip()
        if not claim:
            continue
        for n in numbers:
            if 1 <= n <= n_sources:
                result.setdefault(n, []).append(claim)
    return result


def support_scores(answer: str, chunks: list[dict]) -> dict[int, float]:
    """For each cited source n: the weakest similarity between a sentence citing it
    and the source text. Low values suggest the citation may not support the claim."""
    grouped = sentences_by_source(answer, len(chunks))
    if not grouped:
        return {}
    numbers = sorted(grouped)
    claims = [c for n in numbers for c in grouped[n]]
    vectors = embed_passages(claims + [chunks[n - 1]["text"] for n in numbers])
    claim_vecs, source_vecs = vectors[: len(claims)], vectors[len(claims) :]
    scores: dict[int, float] = {}
    i = 0
    for n, source_vec in zip(numbers, source_vecs):
        sims = [cosine(claim_vecs[i + j], source_vec) for j in range(len(grouped[n]))]
        i += len(grouped[n])
        scores[n] = min(sims)
    return scores
