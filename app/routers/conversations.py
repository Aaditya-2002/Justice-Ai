from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from app.services.conversation_service import ConversationService
from app.core.security import get_current_user
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User

router = APIRouter()

class ConversationCreate(BaseModel):
    title: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str

class ConversationUpdate(BaseModel):
    title: str

def get_conversation_service(db: Session = Depends(get_db)):
    return ConversationService(db)

@router.post("", response_model=ConversationResponse)
async def create_conversation(
    conversation: ConversationCreate,
    conv_service: ConversationService = Depends(get_conversation_service),
    current_user: User = Depends(get_current_user),
):
    return await conv_service.create_conversation(
        user_id=str(current_user.id),
        title=conversation.title,
    )

@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    conv_service: ConversationService = Depends(get_conversation_service),
    current_user: User = Depends(get_current_user),
):
    return await conv_service.list_conversations(user_id=str(current_user.id))

@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    conv_service: ConversationService = Depends(get_conversation_service),
    current_user: User = Depends(get_current_user),
):
    conversation = await conv_service.get_conversation(
        conversation_id=conversation_id,
        user_id=str(current_user.id),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    conversation_update: ConversationUpdate,
    conv_service: ConversationService = Depends(get_conversation_service),
    current_user: User = Depends(get_current_user),
):
    return await conv_service.update_conversation(
        conversation_id=conversation_id,
        title=conversation_update.title,
        user_id=str(current_user.id),
    )

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    conv_service: ConversationService = Depends(get_conversation_service),
    current_user: User = Depends(get_current_user),
):
    await conv_service.delete_conversation(
        conversation_id=conversation_id,
        user_id=str(current_user.id),
    )
    return None
