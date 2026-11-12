from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_prefix="DOCCHAT_", extra="ignore"
    )

    data_dir: Path = PROJECT_DIR / "data"

    # LLM (local, via Ollama)
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "llama3.1:8b"
    llm_temperature: float = 0.1

    # Model runtime for embeddings + reranker:
    #   "onnx"  - onnxruntime + tokenizers (default; no PyTorch, works under Smart App Control)
    #   "torch" - sentence-transformers (pip install sentence-transformers)
    model_backend: str = "onnx"

    # Embeddings (local, CPU)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # bge models expect this prefix on queries (not on passages)
    query_instruction: str = "Represent this sentence for searching relevant passages: "

    # Reranking (optional cross-encoder)
    use_reranker: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"

    # Chunking
    chunk_tokens: int = 500
    chunk_overlap_tokens: int = 75

    # Retrieval
    candidate_k: int = 20  # candidates from each retriever before fusion
    top_k: int = 5  # chunks sent to the LLM
    min_similarity: float = 0.45  # below this → "not found" without calling the LLM
    low_confidence_threshold: float = 0.55  # citation support below this is flagged

    history_turns: int = 6  # prior messages used for follow-up question rewriting

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "docchat.db"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
