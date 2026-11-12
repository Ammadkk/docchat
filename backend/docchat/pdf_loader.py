from pathlib import Path

import pymupdf


def extract_pages(path: str | Path) -> list[dict]:
    """Return [{"page": 1-based page number, "text": str}, ...] for every page."""
    pages: list[dict] = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            pages.append({"page": i + 1, "text": page.get_text("text") or ""})
    return pages


def has_text(pages: list[dict]) -> bool:
    return any(p["text"].strip() for p in pages)
