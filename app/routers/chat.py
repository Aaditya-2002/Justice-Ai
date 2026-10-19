from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.chat_service import ChatService
from app.core.security import get_current_user
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User

router = APIRouter()

class ChatMessage(BaseModel):
    conversation_id: str
    message: str

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    response: str
    citations: List[Dict[str, Any]] = []
def get_chat_service(db: Session = Depends(get_db)):
    return ChatService(db)

@router.post("", response_model=ChatResponse)
async def chat(
    chat_message: ChatMessage,
    chat_service: ChatService = Depends(get_chat_service),
    current_user: User = Depends(get_current_user),
):
    # Verify the conversation exists and belongs to the user
    # We'll do this in the chat service, but we can also do it here for efficiency.
    # For now, we'll rely on the chat service to check ownership.
    result = await chat_service.generate_response(
        conversation_id=chat_message.conversation_id,
        user_message=chat_message.message,
        user_id=str(current_user.id),
    )
    return ChatResponse(
        conversation_id=chat_message.conversation_id,
        message=chat_message.message,
        response=result["response"],
        citations=result["citations"]
    )

