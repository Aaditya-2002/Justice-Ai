from datetime import timedelta
from typing import Optional, Dict, Any
from app.core.security import get_password_hash, authenticate_user, create_access_token
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.tenant import Tenant
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())

    def _get_or_create_default_tenant(self) -> Tenant:
        """Get or create the default tenant."""
        default_tenant_name = settings.DEFAULT_TENANT_ID
        tenant = self.db.query(Tenant).filter(Tenant.name == default_tenant_name).first()
        if not tenant:
            tenant = Tenant(
                name=default_tenant_name,
                display_name="Default Tenant",
                description="Default tenant for Justice AI",
                is_active=True,
            )
            self.db.add(tenant)
            self.db.commit()
            self.db.refresh(tenant)
            logger.info(f"Created default tenant: {tenant.id}")
        return tenant

    def register_user(self, username: str, email: str, password: str) -> User:
        """Register a new user."""
        # Check if user already exists
        existing_user = self.db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            if existing_user.username == username:
                raise ValueError("Username already exists")
            else:
                raise ValueError("Email already exists")

        # Get or create default tenant
        tenant = self._get_or_create_default_tenant()

        # Create new user
        hashed_password = get_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            tenant_id=tenant.id,
        )
        self.db.add(new_user)
        try:
            self.db.commit()
            self.db.refresh(new_user)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Exception during user registration: {type(e).__name__}: {e}")
            raise ValueError("User registration failed due to database error")
        return new_user

    def login_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Log in a user and return an access token with tenant_id."""
        user = authenticate_user(self.db, username, password)
        if not user:
            return None
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "tenant_id": user.tenant_id}, expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "tenant_id": user.tenant_id,
        }

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

