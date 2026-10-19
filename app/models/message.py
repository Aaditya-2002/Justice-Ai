from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    provider_metadata = Column(String, nullable=True)  # JSON string
    token_usage = Column(String, nullable=True)  # JSON string
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
