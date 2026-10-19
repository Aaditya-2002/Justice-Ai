from datetime import datetime
from typing import List, Optional
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.user import User
import uuid

class ConversationService:
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())

    async def create_conversation(self, user_id: str, tenant_id: str, title: Optional[str] = None) -> dict:
        # Create a new conversation for the user
        conversation = Conversation(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            title=title or "New Conversation",
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        }

    async def list_conversations(self, user_id: str, tenant_id: str) -> List[dict]:
        conversations = self.db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.tenant_id == tenant_id
        ).all()
        return [
            {
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
            for conv in conversations
        ]

    async def get_conversation(self, conversation_id: str, user_id: str, tenant_id: str) -> Optional[dict]:
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.tenant_id == tenant_id
        ).first()
        if conversation:
            return {
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            }
        return None

    async def update_conversation(
        self, conversation_id: str, title: str, user_id: str, tenant_id: str
    ) -> dict:
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.tenant_id == tenant_id
        ).first()
        if not conversation:
            raise ValueError("Conversation not found or access denied")
        conversation.title = title
        self.db.commit()
        self.db.refresh(conversation)
        return {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        }

    async def delete_conversation(self, conversation_id: str, user_id: str, tenant_id: str) -> None:
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.tenant_id == tenant_id
        ).first()
        if conversation:
            self.db.delete(conversation)
            self.db.commit()

