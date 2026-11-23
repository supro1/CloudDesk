from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from agents.checkpointer import open_checkpointer
from agents.state import SupportState


async def _write_checkpoint(state: SupportState) -> dict[str, object]:
    return {
        "current_node": "checkpoint_test",
        "completed_nodes": ["checkpoint_test"],
    }


async def test_sqlite_checkpointer_restores_completed_state(tmp_path: Path) -> None:
    database_path = str(tmp_path / "workflow-checkpoints.sqlite")
    config = {"configurable": {"thread_id": "workflow-test"}}
    initial_state: SupportState = {
        "workflow_id": "workflow-test",
        "completed_nodes": [],
        "errors": [],
        "token_usage": {"input_tokens": 0, "output_tokens": 0},
    }

    async with open_checkpointer(database_path) as checkpointer:
        graph = StateGraph(SupportState)
        graph.add_node("checkpoint_test", _write_checkpoint)
        graph.add_edge(START, "checkpoint_test")
        graph.add_edge("checkpoint_test", END)
        compiled_graph = graph.compile(checkpointer=checkpointer)
        await compiled_graph.ainvoke(initial_state, config=config)

    async with open_checkpointer(database_path) as checkpointer:
        graph = StateGraph(SupportState)
        graph.add_node("checkpoint_test", _write_checkpoint)
        graph.add_edge(START, "checkpoint_test")
        graph.add_edge("checkpoint_test", END)
        snapshot = await graph.compile(checkpointer=checkpointer).aget_state(config)

    assert snapshot.values["current_node"] == "checkpoint_test"
    assert snapshot.values["completed_nodes"] == ["checkpoint_test"]
