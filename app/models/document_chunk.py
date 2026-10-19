from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func
from app.models.base import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    # We'll store the embedding as a string for now (comma-separated values)
    # In the future, we'll use a vector type with pgvector
    embedding = Column(String, nullable=True)
    # Additional metadata: page number, section, etc.
    chunk_metadata = Column(String, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
