import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, delete, select

from db import get_session
from models import Conversation, Message

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(session: Session = Depends(get_session)):
    return session.exec(select(Conversation).order_by(Conversation.created_at.desc())).all()


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, session: Session = Depends(get_session)):
    convo = session.get(Conversation, conversation_id)
    if convo is None:
        raise HTTPException(404, "Conversation not found")
    messages = session.exec(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    ).all()
    return {
        "id": convo.id,
        "title": convo.title,
        "created_at": convo.created_at,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json) if m.sources_json else [],
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, session: Session = Depends(get_session)):
    convo = session.get(Conversation, conversation_id)
    if convo is None:
        raise HTTPException(404, "Conversation not found")
    session.exec(delete(Message).where(Message.conversation_id == conversation_id))
    session.delete(convo)
    session.commit()
