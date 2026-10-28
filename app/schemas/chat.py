from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatMessage(BaseModel):
    conversation_id: str
    message: str

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    response: str
    citations: List[Dict[str, Any]] = []
