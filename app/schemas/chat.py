from pydantic import BaseModel
from typing import Optional

class ChatMessage(BaseModel):
    conversation_id: str
    message: str

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    response: str
