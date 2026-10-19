from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.services.auth_service import AuthService
from app.core.database import get_db
from app.models.user import User
from app.core.security import create_access_token, get_current_user
from datetime import timedelta

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

def get_auth_service(db: Session = Depends(get_db)):
    return AuthService(db)

@router.post("/register", response_model=dict)
async def register(
    username: str,
    email: str,
    password: str,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user = auth_service.register_user(username, email, password)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "message": "User registered successfully",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.post("/login", response_model=dict)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
):
    username = form_data.username
    password = form_data.password
    result = auth_service.login_user(username, password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
        "tenant_id": result["tenant_id"],
    }

@router.post("/logout", response_model=dict)
async def logout():
    # In a stateless JWT system, logout is handled by the client by discarding the token.
    # We can optionally implement a token blacklist in the future.
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=dict)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "tenant_id": current_user.tenant_id,
        "is_active": current_user.is_active,
    }

