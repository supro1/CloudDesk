from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.nodes.approval import create_human_approval_node
from agents.nodes.escalation import create_escalation_node
from agents.nodes.investigate import (
    create_customer_context_node,
    create_knowledge_retrieval_node,
    create_troubleshooting_node,
)
from agents.nodes.memory import create_memory_update_node
from agents.nodes.resolution import (
    create_execute_resolution_node,
    create_resolution_planning_node,
    create_risk_check_node,
    create_ticket_summary_node,
)
from agents.nodes.supervisor import classify_severity, understand_ticket
from agents.state import SupportState
from backend.app.tools.registry import ToolRegistry

GRAPH_NODES: tuple[str, ...] = (
    "understand_ticket",
    "classify_severity",
    "customer_context",
    "knowledge_retrieval",
    "troubleshooting",
    "resolution_planning",
    "risk_check",
    "human_approval",
    "execute_resolution",
    "escalation",
    "ticket_summary",
    "memory_update",
)

GRAPH_EDGES: tuple[tuple[str, str], ...] = (
    ("__start__", "understand_ticket"),
    ("understand_ticket", "classify_severity"),
    ("classify_severity", "customer_context"),
    ("customer_context", "knowledge_retrieval"),
    ("knowledge_retrieval", "troubleshooting"),
    ("troubleshooting", "resolution_planning"),
    ("resolution_planning", "risk_check"),
    ("risk_check", "human_approval"),
    ("risk_check", "execute_resolution"),
    ("risk_check", "escalation"),
    ("human_approval", "execute_resolution"),
    ("human_approval", "escalation"),
    ("execute_resolution", "ticket_summary"),
    ("escalation", "ticket_summary"),
    ("ticket_summary", "memory_update"),
    ("memory_update", "__end__"),
)


def _route_after_risk(state: SupportState) -> str:
    if state["escalation_decision"].escalation_required:
        return "escalation"
    if state.get("approval_action_indices"):
        return "human_approval"
    return "execute_resolution"


def _route_after_approval(state: SupportState) -> str:
    return (
        "escalation"
        if state.get("approval_decision") == "rejected"
        else "execute_resolution"
    )


def create_support_graph(
    tools: ToolRegistry,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the support workflow with durable approval pauses and policy routing."""
    graph = StateGraph(SupportState)
    graph.add_node("understand_ticket", understand_ticket)
    graph.add_node("classify_severity", classify_severity)
    graph.add_node("customer_context", create_customer_context_node(tools, session_factory))
    graph.add_node("knowledge_retrieval", create_knowledge_retrieval_node(tools))
    graph.add_node("troubleshooting", create_troubleshooting_node(tools))
    graph.add_node("resolution_planning", create_resolution_planning_node())
    graph.add_node("risk_check", create_risk_check_node(tools))
    graph.add_node("human_approval", create_human_approval_node())
    graph.add_node(
        "execute_resolution",
        create_execute_resolution_node(tools, session_factory),
    )
    graph.add_node("escalation", create_escalation_node(tools))
    graph.add_node("ticket_summary", create_ticket_summary_node(session_factory))
    graph.add_node("memory_update", create_memory_update_node(session_factory))
    graph.add_edge(START, "understand_ticket")
    for source, target in GRAPH_EDGES[1:7]:
        graph.add_edge(source, target)
    graph.add_conditional_edges(
        "risk_check",
        _route_after_risk,
        {
            "human_approval": "human_approval",
            "execute_resolution": "execute_resolution",
            "escalation": "escalation",
        },
    )
    graph.add_conditional_edges(
        "human_approval",
        _route_after_approval,
        {"execute_resolution": "execute_resolution", "escalation": "escalation"},
    )
    graph.add_edge("execute_resolution", "ticket_summary")
    graph.add_edge("escalation", "ticket_summary")
    graph.add_edge("ticket_summary", "memory_update")
    graph.add_edge("memory_update", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["GRAPH_EDGES", "GRAPH_NODES", "create_support_graph"]
