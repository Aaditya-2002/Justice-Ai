import asyncio
import io
import tempfile
import os
import pytest
from app.services.document_service import DocumentService
from app.services.rag_service import RAGService
from app.core.database import get_db, engine
from app.models.base import Base
from app.models.user import User
# Import all models to ensure they are registered with Base
from app.models import user, conversation, message, document, document_chunk
from sqlalchemy.orm import Session

# Create tables
Base.metadata.create_all(bind=engine)

TENANT_ID = "712dd85e-398d-4890-a030-07f811bc159f"  # default tenant

@pytest.mark.asyncio
async def test_rag_service():
    # Get a database session
    db: Session = next(get_db())
    doc_service = DocumentService(db)
    rag_service = RAGService(db)
    
    # Create a test user
    test_user = User(
        id="test-user",
        tenant_id=TENANT_ID,
        username="testuser",
        email="test@example.com",
        hashed_password="hashedpassword",
        is_active=True,
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    try:
        # Create a mock file
        file_content = b"This is a test document for RAG. It contains some text that we can chunk and search."
        file_name = "test.txt"
        file_obj = io.BytesIO(file_content)
        file_obj.filename = file_name
        file_obj.content_type = "text/plain"
        
        # Upload the document
        user_id = "test-user"
        doc_result = await doc_service.upload_document(user_id, TENANT_ID, file_obj)
        doc_id = doc_result["id"]
        print(f"Uploaded document: {doc_result}")
        
        # Wait a bit for processing (the upload_document already processes)
        # But we can also call process_document explicitly if needed
        # However, upload_document already calls process_document, so we can skip.
        
        # Now test retrieval
        query = "test document"
        chunks = await rag_service.retrieve_relevant_chunks(query, document_ids=[doc_id], limit=5)
        print(f"Retrieved chunks: {chunks}")
        assert len(chunks) > 0, "Should retrieve at least one chunk"
        # Check that the chunk text contains our content
        chunk_text = chunks[0]['chunk'].chunk_text
        assert "test document" in chunk_text.lower() or "rag" in chunk_text.lower(), "Chunk text should be relevant"
        
        # Clean up: delete the document
        await doc_service.delete_document(doc_id, user_id, TENANT_ID)
        print("Test passed!")
    finally:
        # Clean up test user
        db.query(User).filter(User.id == "test-user").delete()
        db.commit()

if __name__ == "__main__":
    asyncio.run(test_rag_service())
