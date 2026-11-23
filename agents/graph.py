from __future__ import annotations

from itertools import pairwise

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.nodes.investigate import (
    create_customer_context_node,
    create_knowledge_retrieval_node,
    create_troubleshooting_node,
)
from agents.nodes.memory import create_memory_update_node
from agents.nodes.resolution import (
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
    "ticket_summary",
    "memory_update",
)

GRAPH_EDGES: tuple[tuple[str, str], ...] = tuple(pairwise(GRAPH_NODES))


def create_support_graph(
    tools: ToolRegistry,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the support workflow; consequential actions are deferred to Phase 11."""
    graph = StateGraph(SupportState)
    graph.add_node("understand_ticket", understand_ticket)
    graph.add_node("classify_severity", classify_severity)
    graph.add_node("customer_context", create_customer_context_node(tools, session_factory))
    graph.add_node("knowledge_retrieval", create_knowledge_retrieval_node(tools))
    graph.add_node("troubleshooting", create_troubleshooting_node(tools))
    graph.add_node("resolution_planning", create_resolution_planning_node())
    graph.add_node("risk_check", create_risk_check_node(tools))
    graph.add_node("ticket_summary", create_ticket_summary_node(session_factory))
    graph.add_node("memory_update", create_memory_update_node(session_factory))
    graph.add_edge(START, GRAPH_NODES[0])
    for source, target in GRAPH_EDGES:
        graph.add_edge(source, target)
    graph.add_edge(GRAPH_NODES[-1], END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["GRAPH_EDGES", "GRAPH_NODES", "create_support_graph"]
