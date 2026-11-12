from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid4().hex


class DocumentBase(SQLModel):
    filename: str
    status: str = "processing"  # processing | ready | failed
    error: str | None = None
    page_count: int = 0
    chunk_count: int = 0
    size_bytes: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Document(DocumentBase, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    file_hash: str = Field(index=True)
    path: str


class DocumentRead(DocumentBase):
    id: str


class Conversation(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=utcnow)


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id", index=True)
    role: str  # user | assistant
    content: str
    sources_json: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
