from langgraph.graph import StateGraph, START, END
from graph.state import CaseState
from graph.nodes import (
    medical_agent_node,
    icd_agent_node,
    damages_agent_node,
    legal_agent_node,
)


def _should_retry_medical(state: CaseState) -> str:
    """Retry medical extraction up to 2 times if no injuries were extracted."""
    if not state.get("injuries") and state.get("retry_count", 0) < 2:
        return "retry"
    return "continue"


def build_graph():
    g = StateGraph(CaseState)

    g.add_node("medical_agent", medical_agent_node)
    g.add_node("icd_agent", icd_agent_node)
    g.add_node("damages_agent", damages_agent_node)
    g.add_node("legal_agent", legal_agent_node)

    g.add_edge(START, "medical_agent")

    g.add_conditional_edges(
        "medical_agent",
        _should_retry_medical,
        {"retry": "medical_agent", "continue": "icd_agent"},
    )

    g.add_edge("icd_agent", "damages_agent")
    g.add_edge("damages_agent", "legal_agent")
    g.add_edge("legal_agent", END)

    return g.compile()


# Singleton — compiled once at import time
pipeline = build_graph()
