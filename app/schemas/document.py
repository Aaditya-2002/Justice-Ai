from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
