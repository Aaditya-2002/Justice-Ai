from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from app.routers import chat, conversations, documents, auth
from app.core.database import Base, engine
import app.models  # noqa: F401 - ensure models are imported

app = FastAPI(
    title="Justice AI",
    description="Phase 2: User Interface, Authentication, and Advanced Agent Foundation",
    version="0.2.0",
)

# Create tables on startup
@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])

@app.get("/health/live")
async def liveness():
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    # In a real app, we would check dependencies like database, etc.
    return {"status": "ready"}

@app.get("/test")
async def test():
    return {"message": "test endpoint"}

# Mount the frontend static files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
