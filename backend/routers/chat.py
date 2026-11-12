import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import engine
from docchat.config import settings
from docchat.rag import answer_stream
from models import Conversation, Message

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger("docchat.chat")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    doc_ids: list[str] | None = None


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _friendly_error(exc: Exception) -> str:
    """Turn the common failure modes into something a user can act on."""
    name, text = type(exc).__name__, str(exc)
    if "ConnectError" in name or "refused" in text or "Failed to connect" in text:
        return f"Can't reach Ollama at {settings.ollama_host}. Is it installed and running?"
    if getattr(exc, "status_code", None) == 404 or "not found, try pulling" in text:
        return f"Model '{settings.llm_model}' isn't available. Run: ollama pull {settings.llm_model}"
    return f"{name}: {text}"


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    question = req.question.strip()
    with Session(engine) as session:
        if req.conversation_id:
            convo = session.get(Conversation, req.conversation_id)
            if convo is None:
                raise HTTPException(404, "Conversation not found")
        else:
            convo = Conversation(title=question[:60])
            session.add(convo)
            session.commit()
            session.refresh(convo)
        conversation_id = convo.id

        prior = session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(settings.history_turns)
        ).all()
        history = [{"role": m.role, "content": m.content} for m in reversed(prior)]

        session.add(Message(conversation_id=conversation_id, role="user", content=question))
        session.commit()

    def events() -> Iterator[str]:
        yield sse("meta", {"conversation_id": conversation_id})
        try:
            for event in answer_stream(question, history, req.doc_ids or None):
                if event["type"] == "token":
                    yield sse("token", event["data"])
                elif event["type"] == "done":
                    result = event["data"]
                    with Session(engine) as session:
                        session.add(
                            Message(
                                conversation_id=conversation_id,
                                role="assistant",
                                content=result["answer"],
                                sources_json=json.dumps(result["sources"]),
                            )
                        )
                        session.commit()
                    yield sse("done", result)
        except Exception as exc:
            log.exception("Chat failed")
            yield sse("error", {"message": _friendly_error(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
