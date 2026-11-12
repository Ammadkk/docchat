"""Quick terminal test of the RAG pipeline without the web app.

    python cli.py ingest path/to/file.pdf
    python cli.py ask "What is the main conclusion?"
"""

import sys
import textwrap

from db import init_db


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in {"ingest", "ask"}:
        print(__doc__)
        sys.exit(1)
    init_db()

    if sys.argv[1] == "ingest":
        import hashlib
        import shutil
        from pathlib import Path

        from sqlmodel import Session

        from db import engine
        from docchat.config import settings
        from ingest import ingest_document
        from models import Document

        src = Path(sys.argv[2])
        data = src.read_bytes()
        doc = Document(filename=src.name, file_hash=hashlib.sha256(data).hexdigest(), path="",
                       size_bytes=len(data))
        dest = settings.uploads_dir / f"{doc.id}.pdf"
        shutil.copyfile(src, dest)
        doc.path = str(dest)
        with Session(engine) as s:
            s.add(doc)
            s.commit()
        ingest_document(doc.id)
        with Session(engine) as s:
            d = s.get(Document, doc.id)
            print(f"{d.filename}: {d.status} ({d.page_count} pages, {d.chunk_count} chunks) {d.error or ''}")
        return

    from docchat.rag import answer_stream

    question = " ".join(sys.argv[2:])
    for event in answer_stream(question):
        if event["type"] == "token":
            print(event["data"], end="", flush=True)
        else:
            print("\n\nSources:")
            for s in event["data"]["sources"]:
                if s["cited"]:
                    flag = " (low confidence)" if s["low_confidence"] else ""
                    snippet = textwrap.shorten(s["text"], 120)
                    print(f"  [{s['n']}] {s['filename']} p.{s['page_start']}{flag}: {snippet}")


if __name__ == "__main__":
    main()
