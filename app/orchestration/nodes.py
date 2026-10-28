"""LangGraph Nodes for Justice Agent Orchestration."""

from typing import Dict, Any, List, Optional, Literal
from langgraph.types import Command, interrupt
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from app.orchestration.state import (
    JusticeAgentState,
    QueryClassification,
    Citation,
    LegalResponse,
    create_initial_state,
)
from app.services.rag_service import RAGService
from app.services.document_service import DocumentService
from app.core.model_provider import ModelProviderFactory
from app.core.config import settings
from app.skills.registry import skill_registry
from app.models.user import User


# ============================================================
# Node 1: ENTRY - Ingest, authenticate, initialize state
# ============================================================

async def entry_node(state: JusticeAgentState) -> JusticeAgentState:
    """Entry node: Validate input, initialize services, prepare state."""
    # State is already initialized by create_initial_state
    # This node can be used for additional validation or setup
    
    # Ensure config has required settings
    state.config.setdefault("rag_top_k", settings.RAG_TOP_K)
    state.config.setdefault("model_provider", settings.MODEL_PROVIDER)
    state.config.setdefault("embedding_provider", settings.EMBEDDING_PROVIDER)
    
    return state


# ============================================================
# Node 2: ROUTER - Classify query and route
# ============================================================

ROUTER_SYSTEM_PROMPT = """You are a legal query classifier. Analyze the user's message and classify it into one of these types:

1. "information" - Single factual question, simple lookup, definition, or straightforward legal question that can be answered with retrieved context
2. "research" - Complex multi-step research requiring analysis of multiple sources, case law, statutes, or synthesis
3. "skill" - Request to invoke a specific skill (starts with /skill)
4. "unknown" - Cannot determine, needs clarification

Return a JSON object with:
- query_type: one of ["information", "research", "skill", "unknown"]
- confidence: float between 0 and 1
- reasoning: brief explanation
- required_tools: list of tool names needed (e.g., ["rag_search", "skill_invocation"])
"""

async def router_node(state: JusticeAgentState) -> JusticeAgentState:
    """Router node: Classify the user's query and determine the execution path."""
    
    # Check for skill invocation first (explicit)
    if state.user_message.strip().startswith("/skill"):
        state.query_classification = QueryClassification(
            query_type="skill",
            confidence=1.0,
            reasoning="Explicit skill invocation detected",
            required_tools=["skill_invocation"]
        )
        return state
    
    # Use model provider for classification
    # (classification itself is currently heuristic; provider selected for parity)
    model_provider = ModelProviderFactory.create_default_provider()
    
    # For now, use a simple heuristic-based classification
    # In production, this would use the model provider
    message_lower = state.user_message.lower()
    
    # Initialize with defaults
    query_type = "information"
    confidence = 0.5
    reasoning = "Defaulting to information query"
    required_tools = ["rag_search"]
    
    if any(kw in message_lower for kw in ["research", "analyze", "compare", "case law", "statute", "precedent", "multi-step"]):
        query_type = "research"
        confidence = 0.8
        reasoning = "Complex research query detected"
        required_tools = ["rag_search", "multi_step_analysis"]
    elif any(kw in message_lower for kw in ["what is", "define", "explain", "how to", "can i", "is it legal"]):
        query_type = "information"
        confidence = 0.9
        reasoning = "Single factual question detected"
        required_tools = ["rag_search"]
    
    state.query_classification = QueryClassification(
        query_type=query_type,
        confidence=confidence,
        reasoning=reasoning,
        required_tools=required_tools
    )
    
    return state


# ============================================================
# Node 3: INFORMATION - Single-turn legal QA
# ============================================================

async def information_node(state: JusticeAgentState) -> JusticeAgentState:
    """Information node: Handle single-turn legal QA using RAG."""
    
    # Retrieve relevant chunks
    user_docs = await DocumentService(state.config.get("db")).list_documents(
        state.user_id, state.tenant_id
    )
    document_ids = [doc["id"] for doc in user_docs]
    
    chunk_infos = []
    if document_ids:
        rag_service = RAGService(state.config.get("db"))
        chunk_infos = await rag_service.retrieve_relevant_chunks(
            state.user_message,
            document_ids=document_ids,
            limit=state.config.get("rag_top_k", settings.RAG_TOP_K)
        )
    
    # Build citations
    citations = []
    context_parts = []
    for chunk_info in chunk_infos:
        chunk = chunk_info["chunk"]
        similarity = chunk_info["similarity"]
        document_id = chunk_info["document_id"]
        filename = chunk_info["filename"]
        
        citation = Citation(
            document_id=document_id,
            filename=filename,
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text,
            similarity=similarity
        )
        citations.append(citation)
        context_parts.append(f"[Relevant chunk (similarity: {similarity:.2f})]: {chunk.chunk_text}")
    
    state.retrieved_chunks = chunk_infos
    state.citations = citations
    state.context_text = "\n\n".join(context_parts) if context_parts else "No relevant context found."
    
    # Generate response using model provider (with automatic failover)
    model_provider = ModelProviderFactory.create_default_provider()
    
    # Get conversation history
    from app.core.database import get_db
    from app.models.message import Message
    db = state.config.get("db") or next(get_db())
    messages = db.query(Message).filter(
        Message.conversation_id == state.conversation_id,
        Message.tenant_id == state.tenant_id
    ).order_by(Message.created_at.desc()).limit(5).all()
    messages = list(reversed(messages))
    conversation_history = [{"role": msg.role, "content": msg.content} for msg in messages]
    
    response_content = await model_provider.generate_response(
        prompt=state.user_message,
        conversation_history=conversation_history,
        context=state.context_text,
        skills=[]
    )
    
    state.legal_response = LegalResponse(
        answer=response_content,
        citations=citations,
        confidence=0.8
    )
    
    return state


# ============================================================
# Node 4: RESEARCH - Multi-step research loop
# ============================================================

async def research_node(state: JusticeAgentState) -> JusticeAgentState:
    """Research node: Handle multi-step research with iterative retrieval."""
    
    # Delegate to information_node for now
    state = await information_node(state)
    
    # Add research-specific metadata
    if state.legal_response:
        state.legal_response.answer = f"[Research Mode] {state.legal_response.answer}"
        state.metadata["research_mode"] = True
    
    return state


# ============================================================
# Node 5: CITATION_VALIDATOR - Validate citations
# ============================================================

async def citation_validator_node(state: JusticeAgentState) -> JusticeAgentState:
    """Citation validator node: Verify citations match retrieved chunks."""
    
    if not state.legal_response or not state.citations:
        return state
    
    validated_citations = []
    for citation in state.legal_response.citations:
        # Check if citation matches a retrieved chunk
        matches = False
        for chunk in state.retrieved_chunks:
            chunk_obj = chunk["chunk"]
            if (chunk_obj.document_id == citation.document_id and 
                chunk_obj.chunk_index == citation.chunk_index):
                matches = True
                break
        
        if matches:
            validated_citations.append(citation)
        else:
            # Citation doesn't match - log warning
            state.metadata["citation_warnings"] = state.metadata.get("citation_warnings", [])
            state.metadata["citation_warnings"].append(
                f"Citation mismatch: doc_id={citation.document_id}, chunk_index={citation.chunk_index}"
            )
    
    state.legal_response.citations = validated_citations
    return state


# ============================================================
# Node 6: CONSENT - Handle lawyer referral consent (interrupt)
# ============================================================

CONSENT_PROMPT = """This query may require a lawyer referral. 

Based on your question about {topic}, I recommend consulting with a qualified attorney who can provide personalized legal advice.

Would you like me to:
1. Provide general legal information only
2. Initiate a lawyer referral (requires your consent)

Please respond with "consent" to proceed with referral, or "info" for general information only."""

async def consent_node(state: JusticeAgentState) -> JusticeAgentState:
    """Consent node: Handle lawyer referral consent workflow using interrupt."""
    
    # Check if consent is required based on query classification
    # In production, this would be based on specific legal topics
    requires_consent = state.query_classification and state.query_classification.query_type == "research"
    
    if not requires_consent:
        return state
    
    # Check if consent was already given in a previous turn
    if state.consent_given:
        return state
    
    # Generate consent prompt
    topic = "legal matter"  # Would be derived from classification
    state.consent_required = True
    state.consent_prompt = CONSENT_PROMPT.format(topic=topic)
    
    # Interrupt and wait for user response
    # This will pause the graph and wait for Command(resume=...)
    user_response = interrupt({
        "type": "consent_required",
        "prompt": state.consent_prompt,
        "conversation_id": state.conversation_id,
    })
    
    # Resume with user's choice
    if user_response.get("action") == "consent":
        state.consent_given = True
        state.metadata["lawyer_referral_initiated"] = True
    else:
        state.consent_given = False
        state.metadata["lawyer_referral_declined"] = True
    
    return state


# ============================================================
# Node 7: RESPONSE - Format final response
# ============================================================

async def response_node(state: JusticeAgentState) -> JusticeAgentState:
    """Response node: Format the final response with citations and metadata."""
    
    if not state.legal_response:
        # Fallback if no legal response generated
        state.legal_response = LegalResponse(
            answer="I apologize, but I couldn't generate a response at this time.",
            citations=state.citations,
            confidence=0.0
        )
    
    # Add skill result if present
    if state.skill_result:
        state.legal_response.answer = f"{state.legal_response.answer}\n\n{state.skill_result}"
    
    # Add consent prompt if required and not given
    if state.consent_required and not state.consent_given:
        state.legal_response.answer = f"{state.legal_response.answer}\n\n{state.consent_prompt}"
    
    return state


# ============================================================
# Node 8: CHECKPOINT - Save checkpoint (handled by PostgresSaver)
# ============================================================

async def checkpoint_node(state: JusticeAgentState) -> JusticeAgentState:
    """Checkpoint node: LangGraph/PostgresSaver handles this automatically.
    
    This node exists as a placeholder for any custom checkpoint logic.
    The actual checkpointing is handled by PostgresSaver during graph execution.
    """
    # Update metadata with checkpoint info
    state.metadata["last_checkpoint"] = {
        "conversation_id": state.conversation_id,
        "tenant_id": state.tenant_id,
        "timestamp": "auto"  # PostgresSaver handles timestamp
    }
    return state


# ============================================================
# Conditional edges for routing
# ============================================================

def route_after_router(state: JusticeAgentState) -> Literal["information", "research", "skill_invocation", "entry"]:
    """Route based on query classification."""
    if not state.query_classification:
        return "entry"
    
    query_type = state.query_classification.query_type
    
    if query_type == "skill":
        return "skill_invocation"
    elif query_type == "research":
        return "research"
    elif query_type == "information":
        return "information"
    else:
        return "entry"


def route_after_consent(state: JusticeAgentState) -> Literal["information", "research", "entry"]:
    """Route after consent based on user's choice."""
    if state.consent_given:
        # If consent given, proceed with research (which includes referral logic)
        return "research"
    else:
        # If consent declined, provide information only
        return "information"


def route_after_citation_validator(state: JusticeAgentState) -> Literal["consent", "response"]:
    """Route after citation validation."""
    # Check if consent is needed
    if (state.query_classification and 
        state.query_classification.query_type == "research" and
        not state.consent_given and
        not state.consent_required):
        return "consent"
    return "response"
