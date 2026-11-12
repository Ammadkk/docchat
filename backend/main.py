import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db
from docchat import vector_store
from docchat.config import PROJECT_DIR, settings
from docchat.llm import get_llm
from ingest import resume_interrupted
from routers import chat, conversations, documents

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    threading.Thread(target=resume_interrupted, daemon=True).start()
    yield


app = FastAPI(title="DocChat API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(conversations.router)


@app.get("/api/health", tags=["health"])
def health():
    ok, message = get_llm().health()
    return {
        "llm_ok": ok,
        "llm_message": message,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "reranker": settings.reranker_model if settings.use_reranker else None,
        "chunks_indexed": vector_store.count(),
    }


# In production, serve the built React app from the same process.
_dist = PROJECT_DIR / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
