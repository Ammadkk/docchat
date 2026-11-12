"""Ingestion pipeline: PDF → pages → chunks → embeddings → Chroma (+ BM25 refresh)."""

import logging

from sqlmodel import Session, select

from db import engine
from docchat import vector_store
from docchat.bm25_index import bm25_index
from docchat.chunker import chunk_pages
from docchat.config import settings
from docchat.embeddings import embed_passages
from docchat.pdf_loader import extract_pages, has_text
from models import Document

log = logging.getLogger("docchat.ingest")


def ingest_document(doc_id: str) -> None:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            return
        try:
            pages = extract_pages(doc.path)
            doc.page_count = len(pages)
            if not has_text(pages):
                raise ValueError(
                    "No extractable text. This looks like a scanned PDF; OCR is not supported yet."
                )
            chunks = chunk_pages(pages, settings.chunk_tokens, settings.chunk_overlap_tokens)
            embeddings = embed_passages([c.text for c in chunks])
            vector_store.delete_document(doc.id)  # idempotent re-ingest
            vector_store.add_chunks(doc.id, doc.filename, chunks, embeddings)
            bm25_index.invalidate()
            doc.chunk_count = len(chunks)
            doc.status = "ready"
            doc.error = None
            log.info("Ingested %s: %d pages, %d chunks", doc.filename, len(pages), len(chunks))
        except Exception as exc:
            log.exception("Ingestion failed for %s", doc.filename)
            doc.status = "failed"
            doc.error = str(exc)
        session.add(doc)
        session.commit()


def resume_interrupted() -> None:
    """Re-ingest documents left in 'processing' when the server last stopped."""
    with Session(engine) as session:
        ids = session.exec(select(Document.id).where(Document.status == "processing")).all()
    for doc_id in ids:
        ingest_document(doc_id)
