from typing import Optional, List, Dict, Any
import json
from app.core.config import settings
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService
from app.core.model_provider import ModelProviderFactory
from app.models.user import User
from app.skills.registry import skill_registry
from app.orchestration.graph import run_graph, skill_invocation_node
from app.orchestration.state import create_initial_state


class ChatService:
    def __init__(self, db: Session = None):
        if db is None:
            db = next(get_db())
        self.db = db
        self.rag_service = RAGService(self.db)
        self.conversation_service = ConversationService(self.db)
        self.document_service = DocumentService(self.db)
        # Initialize the model provider
        self.model_provider = ModelProviderFactory.create_provider(
            settings.MODEL_PROVIDER,
            # We can pass additional kwargs if needed, like API keys, etc.
        )

    async def generate_response(
        self, conversation_id: str, user_message: str, user_id: str, tenant_id: str
    ) -> Dict[str, Any]:
        # Check for skill invocation
        stripped = user_message.strip()
        if stripped.startswith("/skill"):
            parts = stripped.split()
            if parts[0] != "/skill":
                return "Invalid skill invocation. Usage: /skill <skill_name> <json_input>"
            if len(parts) < 2:
                return "Invalid skill invocation. Usage: /skill <skill_name> <json_input>"
            skill_name = parts[1]
            json_str = " ".join(parts[2:])
            if not json_str:
                return "Invalid skill invocation. Usage: /skill <skill_name> <json_input>"
            try:
                input_data = json.loads(json_str)
            except json.JSONDecodeError:
                return "Invalid JSON input for skill."
            # Execute the skill
            user = self.db.query(User).filter(User.id == user_id).first()
            try:
                result = skill_registry.execute_skill(skill_name, input_data, user=user)
                return f"Skill {skill_name} result: {json.dumps(result, indent=2)}"
            except Exception as e:
                return f"Error executing skill {skill_name}: {str(e)}"

        # 1. Verify the conversation exists and belongs to the user and tenant
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.tenant_id == tenant_id
        ).first()
        if not conversation:
            # If conversation not found, we can create a new one or return an error.
            # For now, we'll create a new conversation.
            conversation = Conversation(
                id=conversation_id,
                tenant_id=tenant_id,
                user_id=user_id,
                title="New Conversation",
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        # 2. Save the user message
        user_msg_count = self.db.query(Message).filter(Message.conversation_id == conversation_id).count()
        user_msg = Message(
            id=f"msg-{conversation_id}-{user_msg_count}-user",
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            role="user",
            content=user_message
        )
        self.db.add(user_msg)
        self.db.commit()

        # 3. Use LangGraph orchestration for the rest
        try:
            # Run the LangGraph orchestration
            result = await run_graph(
                conversation_id=conversation_id,
                user_id=user_id,
                tenant_id=tenant_id,
                user_message=user_message,
                config={"db": self.db},
            )
            
            response_content = result.get("response", "No response generated")
            citations = result.get("citations", [])
            print(f"DEBUG: LangGraph result - response: {response_content[:100] if response_content else 'None'}, citations: {len(citations)}")
            
        except Exception as e:
            # Fallback to legacy implementation if LangGraph fails
            import traceback
            print(f"DEBUG: LangGraph exception caught: {type(e).__name__}: {e}")
            print(f"DEBUG: Exception args: {e.args}")
            traceback.print_exc()
            response_content = await self._legacy_generate_response(
                conversation_id, user_message, user_id, tenant_id
            )
            citations = []

        # 7. Save the assistant response
        assistant_msg_count = self.db.query(Message).filter(Message.conversation_id == conversation_id).count()
        assistant_msg = Message(
            id=f"msg-{conversation_id}-{assistant_msg_count}-assistant",
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            role="assistant",
            content=response_content
        )
        self.db.add(assistant_msg)
        self.db.commit()

        # 8. Return the response and citations
        return {
            "response": response_content,
            "citations": citations
        }

    async def _legacy_generate_response(
        self, conversation_id: str, user_message: str, user_id: str, tenant_id: str
    ) -> str:
        """Legacy response generation (fallback)."""
        # 3. Retrieve relevant context using RAG
        user_docs = await self.document_service.list_documents(user_id, tenant_id)
        document_ids = [doc["id"] for doc in user_docs]

        chunk_infos = []
        if document_ids:
            chunk_infos = await self.rag_service.retrieve_relevant_chunks(
                user_message, document_ids=document_ids
            )

        context_parts = []
        for chunk_info in chunk_infos:
            chunk = chunk_info["chunk"]
            similarity = chunk_info["similarity"]
            context_parts.append(f"[Relevant chunk (similarity: {similarity:.2f})]: {chunk.chunk_text}")
        context = "\n\n".join(context_parts) if context_parts else "No relevant context found."

        # 5. Prepare conversation history
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.tenant_id == tenant_id
        ).order_by(Message.created_at.desc()).limit(5).all()
        messages = list(reversed(messages))
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # 6. Generate response
        response_content = await self.model_provider.generate_response(
            prompt=user_message,
            conversation_history=conversation_history,
            context=context,
            skills=[]
        )

        return response_content
