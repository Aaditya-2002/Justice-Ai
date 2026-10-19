from typing import List, Optional, Tuple, Union, Dict, Any
import json
import math
import re
from app.core.config import settings
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
import logging
from app.core.embedding_provider import EmbeddingProvider, MockEmbeddingProvider, SentenceTransformerEmbeddingProvider

class RAGService:
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
        self.embedding_dimensions = settings.EMBEDDING_DIMENSIONS or 1536  # default to OpenAI's embedding size
        # Initialize embedding provider
        self.embedding_provider = self._initialize_embedding_provider()

    def _initialize_embedding_provider(self) -> EmbeddingProvider:
        """Initialize the embedding provider based on configuration."""
        if settings.EMBEDDING_PROVIDER == "sentence-transformers":
            try:
                return SentenceTransformerEmbeddingProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize SentenceTransformerEmbeddingProvider: {e}. Falling back to mock.")
                return MockEmbeddingProvider()
        else:
            return MockEmbeddingProvider()

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using the configured embedding provider."""
        return await self.embedding_provider.get_embedding(text)

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks of chunk_size with overlap."""
        # Simple chunking by characters, respecting sentence boundaries as much as possible
        if not text:
            return []
        
        # First, split by paragraphs (double newline)
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # If adding this paragraph would exceed chunk_size, save current chunk and start new
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap from the end of current chunk
                # We take the last chunk_overlap characters as the start of the next chunk
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + " " + para
            else:
                if current_chunk:
                    current_chunk += " " + para
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # If we have no chunks (e.g., text was empty or only whitespace), return empty list
        if not chunks and text.strip():
            # Fallback: split by chunk_size
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunk = text[i:i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())
        
        return chunks


    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    async def process_document(self, document_id: str, extracted_text: str) -> bool:
        """Process a document: chunk it, generate embeddings, and store chunks."""
        # Delete any existing chunks for this document
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        
        # Chunk the text
        chunks = self._chunk_text(extracted_text)
        if not chunks:
            # If no chunks, we still want to store something? We'll store one chunk with the whole text
            chunks = [extracted_text]
        
        # Store each chunk with its embedding
        for idx, chunk_text in enumerate(chunks):
            embedding = await self._get_embedding(chunk_text)
            # Store embedding as JSON string
            embedding_json = json.dumps(embedding)
            
            chunk = DocumentChunk(
                id=f"{document_id}-chunk-{idx}",  # Simple ID, in real app use UUID
                document_id=document_id,
                chunk_index=idx,
                chunk_text=chunk_text,
                embedding=embedding_json,
                chunk_metadata=json.dumps({})  # Empty metadata for now
            )
            self.db.add(chunk)
        
        self.db.commit()
        return True

    async def retrieve_relevant_chunks(
        self, query: str, document_ids: Optional[List[str]] = None, limit: int = None
) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query.
        
        Returns a list of dictionaries containing the chunk, similarity score, 
        document ID, and filename, sorted by similarity descending.
        """
        if limit is None:
            limit = settings.RAG_TOP_K
        # Generate embedding for the query
        query_embedding = await self._get_embedding(query)
        
        # Build query with join to Document to get filename
        db_query = self.db.query(DocumentChunk, Document.filename).join(
            Document, DocumentChunk.document_id == Document.id
        )
        if document_ids is not None:
            if len(document_ids) == 0:
                return []  # No documents to search
            db_query = db_query.filter(DocumentChunk.document_id.in_(document_ids))
        
        # Get all chunks with their document filename
        chunk_results = db_query.all()  # List of tuples (DocumentChunk, filename)
        
        # Compute similarity for each chunk
        chunk_similarities = []  # Will be list of dicts
        for chunk, filename in chunk_results:
            if chunk.embedding:
                try:
                    chunk_embedding = json.loads(chunk.embedding)
                    similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                    chunk_similarities.append({
                        "chunk": chunk,
                        "similarity": similarity,
                        "document_id": chunk.document_id,
                        "filename": filename
                    })
                except (json.JSONDecodeError, TypeError):
                    # If embedding is invalid, skip
                    continue
        
        # Sort by similarity descending
        chunk_similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top limit
        return chunk_similarities[:limit]

    async def delete_document_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        self.db.commit()
        return True
