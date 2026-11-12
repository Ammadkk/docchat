import hashlib
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from db import get_session
from docchat import vector_store
from docchat.bm25_index import bm25_index
from docchat.config import settings
from ingest import ingest_document
from models import Document, DocumentRead

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_BYTES = 50 * 1024 * 1024


@router.post("", response_model=list[DocumentRead])
async def upload_documents(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    results: list[Document] = []
    for upload in files:
        name = Path(upload.filename or "document.pdf").name
        data = await upload.read()
        if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
            raise HTTPException(400, f"'{name}' is not a PDF file")
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"'{name}' is larger than 50 MB")

        file_hash = hashlib.sha256(data).hexdigest()
        existing = session.exec(select(Document).where(Document.file_hash == file_hash)).first()
        if existing and existing.status != "failed":
            results.append(existing)  # duplicate upload: reuse
            continue
        if existing:  # previously failed: retry ingestion
            existing.status, existing.error = "processing", None
            session.add(existing)
            session.commit()
            session.refresh(existing)
            background.add_task(ingest_document, existing.id)
            results.append(existing)
            continue

        doc = Document(filename=name, file_hash=file_hash, path="", size_bytes=len(data))
        path = settings.uploads_dir / f"{doc.id}.pdf"
        path.write_bytes(data)
        doc.path = str(path)
        session.add(doc)
        session.commit()
        session.refresh(doc)
        background.add_task(ingest_document, doc.id)
        results.append(doc)
    return results


@router.get("", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)):
    return session.exec(select(Document).order_by(Document.created_at.desc())).all()


@router.get("/{doc_id}", response_model=DocumentRead)
def get_document(doc_id: str, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{doc_id}/file")
def get_document_file(doc_id: str, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None or not Path(doc.path).exists():
        raise HTTPException(404, "Document not found")
    return FileResponse(
        doc.path,
        media_type="application/pdf",
        filename=doc.filename,
        content_disposition_type="inline",
    )


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    vector_store.delete_document(doc_id)
    bm25_index.invalidate()
    Path(doc.path).unlink(missing_ok=True)
    session.delete(doc)
    session.commit()
