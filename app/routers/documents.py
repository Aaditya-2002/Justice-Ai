from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from app.services.document_service import DocumentService
from app.core.security import get_current_user, get_current_tenant_id
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User

router = APIRouter()

class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    created_at: str
    updated_at: str

def get_document_service(db: Session = Depends(get_db)):
    return DocumentService(db)

@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    return await doc_service.upload_document(
        user_id=str(current_user.id),
        tenant_id=tenant_id,
        file=file,
    )

@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    doc_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    return await doc_service.list_documents(user_id=str(current_user.id), tenant_id=tenant_id)

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    doc_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    document = await doc_service.get_document(
        document_id=document_id,
        user_id=str(current_user.id),
        tenant_id=tenant_id,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    doc_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    tenant_id = get_current_tenant_id()
    await doc_service.delete_document(
        document_id=document_id,
        user_id=str(current_user.id),
        tenant_id=tenant_id,
    )
    return None

