from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from passlib.context import CryptContext
import uuid
from app.models.base import Base

# CryptContext for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    permissions = Column(String, nullable=False, default="")  # Comma-separated list of permission names
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship to tenant
    tenant = relationship("Tenant", backref="users")

    def set_password(self, password: str) -> None:
        """Hash and set the password."""
        self.hashed_password = pwd_context.hash(password)

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the hashed password."""
        return pwd_context.verify(password, self.hashed_password)
