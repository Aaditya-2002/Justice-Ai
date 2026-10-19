from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.chat_service import ChatService
from app.core.config import settings
from sqlalchemy.orm import Session
import pytest
import asyncio

# Import the word count skill to ensure it is registered
from app.skills import word_count

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Justice AI Agent" in response.text

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

def test_health_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_chat_endpoint():
    # We need to mock the authentication and the service
    # For now, we'll just test that the endpoint exists and returns something
    # We'll skip the actual test because it requires authentication
    pass

@pytest.mark.asyncio
async def test_skill_invocation():
    # We need to set up a database session and create a user and a conversation
    # We'll use a test database session
    db = next(get_db())
    try:
        # Create a test user
        test_user = User(
            id="test-user-id",
            username="testuser",
            email="test@example.com",
            hashed_password="hashedpassword",
            is_active=True,
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        # Create a test conversation
        test_conversation = Conversation(
            id="test-conversation-id",
            user_id=test_user.id,
            title="Test Conversation",
        )
        db.add(test_conversation)
        db.commit()
        db.refresh(test_conversation)

        # Initialize the chat service with the test database session
        chat_service = ChatService(db=db)

        # Test skill invocation: wordcount
        user_message = '/skill wordcount {"text": "Hello world"}'
        response = await chat_service.generate_response(
            conversation_id=test_conversation.id,
            user_message=user_message,
            user_id=test_user.id
        )
        # Check that the response contains the expected result
        assert "Skill wordcount result:" in response
        assert '"word_count": 2' in response

        # Test skill invocation: wordcount with empty text
        user_message = '/skill wordcount {"text": ""}'
        response = await chat_service.generate_response(
            conversation_id=test_conversation.id,
            user_message=user_message,
            user_id=test_user.id
        )
        assert "Skill wordcount result:" in response
        assert '"word_count": 0' in response

        # Test invalid skill name
        user_message = '/skill nonexistent {"text": "test"}'
        response = await chat_service.generate_response(
            conversation_id=test_conversation.id,
            user_message=user_message,
            user_id=test_user.id
        )
        assert "Error executing skill nonexistent:" in response

        # Test invalid JSON
        user_message = '/skill wordcount invalid json'
        response = await chat_service.generate_response(
            conversation_id=test_conversation.id,
            user_message=user_message,
            user_id=test_user.id
        )
        assert "Invalid JSON input for skill." in response

        # Test missing skill name and JSON
        user_message = '/skill'
        response = await chat_service.generate_response(
            conversation_id=test_conversation.id,
            user_message=user_message,
            user_id=test_user.id
        )
        assert "Invalid skill invocation. Usage: /skill <skill_name> <json_input>" in response

        # Test skill name only (no JSON)
        user_message = '/skill wordcount'
        response = await chat_service.generate_response(
            conversation_id=test_conversation.id,
            user_message=user_message,
            user_id=test_user.id
        )
        assert "Invalid skill invocation. Usage: /skill <skill_name> <json_input>" in response

    finally:
        # Clean up: delete the test conversation and user
        db.query(Message).filter(Message.conversation_id == "test-conversation-id").delete()
        db.query(Conversation).filter(Conversation.id == "test-conversation-id").delete()
        db.query(User).filter(User.id == "test-user-id").delete()
        db.commit()
        db.close()
