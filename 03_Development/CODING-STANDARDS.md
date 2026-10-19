# CODING-STANDARDS.md — Coding Standards

## Python Style

### Formatting (Black)
- Line length: **100 chars**
- String quotes: **double** (`"`)
- Trailing commas: **always** in multiline

### Imports (isort)
```python
# Standard library
import json
import os
from typing import List, Optional

# Third-party
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

# Local
from app.core.config import settings
from app.models.user import User
```

### Type Hints
```python
# Required for all public functions
async def get_user(db: Session, user_id: str) -> Optional[User]:
    ...

# Use typing imports
from typing import List, Dict, Any, Optional, Union, Tuple

# Generics
def process(items: List[str]) -> Dict[str, int]:
    ...

# Async
async def fetch_data() -> List[Document]:
    ...
```

---

## FastAPI Patterns

### Router Structure
```python
# app/routers/documents.py
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_tenant_id
from app.services.document_service import DocumentService
from app.models.user import User

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant_id),
):
    service = DocumentService(db)
    return await service.upload_document(current_user.id, tenant_id, file)
```

### Dependency Injection
```python
# app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from contextvars import ContextVar

from app.core.database import get_db
from app.models.user import User
from app.core.config import settings
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="default")

def get_current_tenant_id() -> str:
    return tenant_id_var.get("default")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id", "default")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    tenant_id_var.set(tenant_id)
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if user is None:
        raise credentials_exception
    return user
```

---

## SQLAlchemy Patterns

### Model Definition
```python
# app/models/document.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=True)
    processing_status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
```

### Vector Column (pgvector)
```python
# app/models/document_chunk.py
from pgvector.sqlalchemy import Vector

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=True)  # pgvector type
    chunk_metadata = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
```

### Query with Tenant Scoping
```python
# Always scope by tenant_id
def get_user_documents(db: Session, user_id: str, tenant_id: str) -> List[Document]:
    return db.query(Document).filter(
        Document.user_id == user_id,
        Document.tenant_id == tenant_id
    ).all()

# RAG similarity search
def search_chunks(db: Session, query_vec: List[float], tenant_id: str, document_ids: List[str], limit: int = 5):
    return db.query(DocumentChunk, Document.filename).join(
        Document, DocumentChunk.document_id == Document.id
    ).filter(
        DocumentChunk.tenant_id == tenant_id,
        DocumentChunk.document_id.in_(document_ids)
    ).order_by(DocumentChunk.embedding.cosine_distance(query_vec)).limit(limit).all()
```

---

## Service Layer Patterns

### Service Class Structure
```python
# app/services/document_service.py
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.rag_service import RAGService

class DocumentService:
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
        self.rag_service = RAGService(self.db)

    async def upload_document(self, user_id: str, tenant_id: str, file: UploadFile) -> dict:
        # 1. Save file
        storage_path = self._save_upload_file(file)
        
        # 2. Extract text
        extracted_text = self._extract_text(file, storage_path)
        
        # 3. Create document record
        document = Document(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            filename=file.filename,
            content_type=file.content_type,
            size=os.path.getsize(storage_path),
            storage_path=storage_path,
            extracted_text=extracted_text,
            processing_status="completed" if extracted_text else "failed",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        # 4. Process with RAG
        await self.rag_service.process_document(document.id, extracted_text, tenant_id)
        
        return self._document_to_dict(document)

    async def delete_document(self, document_id: str, user_id: str, tenant_id: str) -> bool:
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.tenant_id == tenant_id
        ).first()
        if not document:
            return False
        
        # Cascade delete chunks
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        
        # Delete file
        if os.path.exists(document.storage_path):
            os.remove(document.storage_path)
        
        self.db.delete(document)
        self.db.commit()
        return True
```

---

## Error Handling

### Custom Exceptions
```python
# app/core/exceptions.py
class JusticeAIException(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

class NotFoundError(JusticeAIException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(f"{resource} not found: {identifier}", "NOT_FOUND")

class PermissionDeniedError(JusticeAIException):
    def __init__(self, action: str):
        super().__init__(f"Permission denied: {action}", "PERMISSION_DENIED")

class ValidationError(JusticeAIException):
    def __init__(self, field: str, message: str):
        super().__init__(f"Validation error on {field}: {message}", "VALIDATION_ERROR")
```

### Global Exception Handler
```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.exceptions import JusticeAIException

app = FastAPI(...)

@app.exception_handler(JusticeAIException)
async def justice_ai_exception_handler(request: Request, exc: JusticeAIException):
    return JSONResponse(
        status_code=400 if exc.code != "INTERNAL_ERROR" else 500,
        content={"error": exc.code, "message": exc.message},
    )
```

---

## Async Best Practices

### Database Sessions
```python
# Use dependency injection for session management
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# In services, accept session or create default
class Service:
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
```

### Async/Await
```python
# Use async for I/O-bound operations
async def generate_embedding(self, text: str) -> List[float]:
    return await self.embedding_provider.get_embedding(text)

# Don't block in async functions
# BAD: time.sleep(1)
# GOOD: await asyncio.sleep(1)
```

---

## Testing Patterns

### Fixture for Test Database
```python
# tests/conftest.py (optional)
import pytest
from sqlalchemy.orm import Session
from app.core.database import get_db, engine
from app.models.base import Base

@pytest.fixture(scope="function")
def db_session() -> Session:
    # Use test database or transaction rollback
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
```

### Test Structure
```python
# tests/test_rag_service.py
import pytest
from app.services.document_service import DocumentService
from app.services.rag_service import RAGService
from app.core.database import get_db
from app.models.user import User

@pytest.mark.asyncio
async def test_rag_service():
    db = next(get_db())
    
    # Setup: create test user
    user = User(id="test-user", tenant_id=TENANT_ID, ...)
    db.add(user)
    db.commit()
    
    try:
        # Test
        service = DocumentService(db)
        result = await service.upload_document(...)
        assert result["id"] is not None
        
        # Verify retrieval
        chunks = await rag_service.retrieve_relevant_chunks(...)
        assert len(chunks) > 0
    finally:
        # Cleanup
        db.query(User).filter(User.id == "test-user").delete()
        db.commit()
```

---

*Enforce with: `black . && isort . && flake8 . && mypy app/` in CI