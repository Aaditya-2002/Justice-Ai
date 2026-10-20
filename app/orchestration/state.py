"""Justice Agent State Definition for LangGraph Orchestration."""

from typing import List, Dict, Any, Optional, Annotated
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages


class Citation(BaseModel):
    """Citation metadata for retrieved chunks."""
    document_id: str
    filename: str
    chunk_index: int
    chunk_text: str
    similarity: float


class QueryClassification(BaseModel):
    """Result of query classification by ROUTER node."""
    query_type: str  # "information", "research", "skill", "unknown"
    confidence: float
    reasoning: str
    required_tools: List[str] = Field(default_factory=list)


class LegalResponse(BaseModel):
    """Structured legal response from Pydantic AI."""
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    disclaimer: str = "This is not legal advice. Consult a qualified attorney for legal matters."
    confidence: float = 1.0


class JusticeAgentState(BaseModel):
    """State for the Justice Agent LangGraph orchestration.

    This state is persisted via PostgresSaver with tenant-scoped checkpoints.
    The checkpoint namespace is derived from tenant_id to ensure isolation.
    """
    # Core identifiers
    conversation_id: str
    user_id: str
    tenant_id: str

    # Input
    user_message: str

    # Classification
    query_classification: Optional[QueryClassification] = None

    # Context retrieval
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    context_text: str = ""

    # Response generation
    legal_response: Optional[LegalResponse] = None

    # Skill invocation
    skill_result: Optional[Dict[str, Any]] = None

    # Consent workflow
    consent_required: bool = False
    consent_prompt: Optional[str] = None
    consent_given: bool = False

    # Messages for conversation history (using LangGraph's add_messages)
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


def create_initial_state(
    conversation_id: str,
    user_id: str,
    tenant_id: str,
    user_message: str,
    config: Optional[Dict[str, Any]] = None
) -> JusticeAgentState:
    """Create initial state for a new conversation turn."""
    return JusticeAgentState(
        conversation_id=conversation_id,
        user_id=user_id,
        tenant_id=tenant_id,
        user_message=user_message,
        config=config or {},
        messages=[HumanMessage(content=user_message)],
    )
