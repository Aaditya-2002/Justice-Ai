"""Justice Agent LangGraph Graph Compilation."""

from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END

from app.orchestration.state import JusticeAgentState, create_initial_state
from app.orchestration.nodes import (
    entry_node,
    router_node,
    information_node,
    research_node,
    citation_validator_node,
    consent_node,
    response_node,
    checkpoint_node,
    route_after_router,
    route_after_consent,
    route_after_citation_validator,
)
from app.core.database import get_db
from app.core.config import settings


def create_graph(db_url: Optional[str] = None) -> StateGraph:
    """Create and compile the Justice Agent LangGraph.
    
    Args:
        db_url: PostgreSQL connection URL. If None, uses settings.DATABASE_URL
        
    Returns:
        Compiled StateGraph
    """
    if db_url is None:
        db_url = settings.DATABASE_URL
    
    # Define the graph
    graph = StateGraph(JusticeAgentState)
    
    # Add nodes
    graph.add_node("entry", entry_node)
    graph.add_node("router", router_node)
    graph.add_node("information", information_node)
    graph.add_node("research", research_node)
    graph.add_node("citation_validator", citation_validator_node)
    graph.add_node("consent", consent_node)
    graph.add_node("response", response_node)
    graph.add_node("skill_invocation", skill_invocation_node)
    
    # Define edges
    graph.set_entry_point("entry")
    
    # Entry -> Router
    graph.add_edge("entry", "router")
    
    # Router -> Conditional routing
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "information": "information",
            "research": "research",
            "skill_invocation": "skill_invocation",
            "entry": "entry",
        }
    )
    
    # Information -> Citation Validator
    graph.add_edge("information", "citation_validator")
    
    # Research -> Citation Validator
    graph.add_edge("research", "citation_validator")
    
    # Citation Validator -> Conditional (Consent or Response)
    graph.add_conditional_edges(
        "citation_validator",
        lambda state: "consent" if (
            state.query_classification and
            state.query_classification.query_type == "research" and
            not state.consent_given and
            not state.consent_required
        ) else "response",
        {
            "consent": "consent",
            "response": "response",
        }
    )
    
    # Consent -> Conditional (based on user choice)
    graph.add_conditional_edges(
        "consent",
        lambda state: "research" if state.consent_given else "information",
        {
            "research": "research",
            "information": "information",
        }
    )
    
    # Skill invocation -> Citation Validator
    graph.add_edge("skill_invocation", "citation_validator")
    
    # Response -> END
    graph.add_edge("response", END)
    
    # Compile without checkpointer for single-turn execution
    compiled_graph = graph.compile()
    
    return compiled_graph


async def run_graph(
    conversation_id: str,
    user_id: str,
    tenant_id: str,
    user_message: str,
    config: Optional[Dict[str, Any]] = None,
    db_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the Justice Agent graph for a single conversation turn.
    
    Args:
        conversation_id: Unique conversation identifier
        user_id: User identifier
        tenant_id: Tenant identifier (for isolation)
        user_message: User's input message
        config: Optional configuration overrides
        db_url: Optional database URL override
        
    Returns:
        Dictionary with response, citations, and metadata
    """
    # Create initial state
    initial_state = create_initial_state(
        conversation_id=conversation_id,
        user_id=user_id,
        tenant_id=tenant_id,
        user_message=user_message,
        config=config,
    )
    
    # Create and compile graph
    graph = create_graph(db_url)
    
    # Prepare config for checkpointing
    # checkpoint_ns = f"tenant_{tenant_id}" ensures tenant isolation
    # thread_id = conversation_id for conversation-scoped checkpoints
    run_config = {
        "configurable": {
            "thread_id": conversation_id,
            "checkpoint_ns": f"tenant_{tenant_id}",
        }
    }
    
    # Run the graph asynchronously (node functions are async)
    print(f"DEBUG: Running graph with thread_id={run_config['configurable']['thread_id']}, checkpoint_ns={run_config['configurable']['checkpoint_ns']}")
    final_state = await graph.ainvoke(initial_state, config=run_config)
    print(f"DEBUG: Graph completed - final_state type: {type(final_state)}, legal_response: {getattr(final_state, 'legal_response', 'N/A')}, citations: {len(final_state.get('citations', []) if isinstance(final_state, dict) else final_state.citations) if final_state else 0}")
    
    # Extract response - final_state is a dict from ainvoke()
    legal = final_state.get("legal_response") if isinstance(final_state, dict) else getattr(final_state, "legal_response", None)
    citations_list = final_state.get("citations") if isinstance(final_state, dict) else getattr(final_state, "citations", [])
    
    # Extract response
    result = {
        "conversation_id": conversation_id,
        "user_message": user_message,
        "response": legal.answer if legal else "No response generated",
        "citations": [c.dict() if hasattr(c, "dict") else c for c in (citations_list or [])],
        "metadata": final_state.get("metadata") if isinstance(final_state, dict) else final_state.metadata,
        "error": final_state.get("error") if isinstance(final_state, dict) else final_state.error,
    }
    print(f"DEBUG: Returning result with {len(result.get('citations', []))} citations")
    return result


# Skill invocation node (separate for explicit /skill commands)
async def skill_invocation_node(state: JusticeAgentState) -> JusticeAgentState:
    """Handle explicit /skill invocations."""
    from app.skills.registry import skill_registry
    from app.models.user import User
    from app.core.database import get_db
    
    # Parse skill command
    parts = state.user_message.strip().split()
    if len(parts) < 2:
        state.error = "Invalid skill invocation. Usage: /skill <skill_name> <json_input>"
        return state
    
    skill_name = parts[1]
    json_str = " ".join(parts[2:])
    
    import json
    try:
        input_data = json.loads(json_str) if json_str else {}
    except json.JSONDecodeError:
        state.error = "Invalid JSON input for skill."
        return state
    
    # Get user
    db = state.config.get("db") or next(get_db())
    user = db.query(User).filter(User.id == state.user_id).first()
    
    if not user:
        state.error = "User not found"
        return state
    
    try:
        result = skill_registry.execute_skill(skill_name, input_data, user=user)
        state.skill_result = json.dumps(result, indent=2)
    except Exception as e:
        state.error = f"Error executing skill {skill_name}: {str(e)}"
        return state
    
    return state


# Add skill_invocation node to graph
def add_skill_node(graph: StateGraph) -> StateGraph:
    """Add skill invocation node to the graph."""
    graph.add_node("skill_invocation", skill_invocation_node)
    graph.add_edge("skill_invocation", "citation_validator")
    return graph
