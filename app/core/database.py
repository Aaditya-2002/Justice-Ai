from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


def get_connect_args(database_url: str) -> dict:
    """Return connect_args based on database type."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, connect_args=get_connect_args(settings.DATABASE_URL)
)

# Create a session local class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for declarative models
Base = declarative_base()

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
