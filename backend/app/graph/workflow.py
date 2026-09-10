"""Graph assembly and the entrypoints that run, pause, and resume an assessment.

    retrieve ──┬─> architecture ─┬─> planner ─> reviewer ─> approval_gate ─┬─> ticket ─> report
               └─> security ─────┘                 └── one bounded loop ──┘└─> report

approval_gate pauses via interrupt() when the deterministic policy requires a
human decision. Only an explicit approval routes to the ticket node.
"""

import logging
import uuid
from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.core.config import settings
from app.graph.checkpointer import get_checkpointer
from app.graph.nodes import (
    after_approval,
    approval_gate_node,
    architecture_analyst_node,
    planner_node,
    report_node,
    retrieve_evidence_node,
    reviewer_node,
    security_analyst_node,
    should_revise,
    ticket_node,
)
from app.graph.state import AssessmentState
from app.models.report import AssessmentReport

logger = logging.getLogger(__name__)


def build_graph(checkpointer=None):
    builder = StateGraph(AssessmentState)

    builder.add_node("retrieve", retrieve_evidence_node)
    builder.add_node("architecture", architecture_analyst_node)
    builder.add_node("security", security_analyst_node)
    builder.add_node("planner", planner_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("ticket", ticket_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "retrieve")
    # Fan out: both analysts run off the same retrieved evidence.
    builder.add_edge("retrieve", "architecture")
    builder.add_edge("retrieve", "security")
    # Fan in: planner waits for both.
    builder.add_edge("architecture", "planner")
    builder.add_edge("security", "planner")
    builder.add_edge("planner", "reviewer")
    builder.add_conditional_edges(
        "reviewer", should_revise, {"revise": "planner", "report": "approval_gate"}
    )
    builder.add_conditional_edges(
        "approval_gate", after_approval, {"ticket": "ticket", "report": "report"}
    )
    builder.add_edge("ticket", "report")
    builder.add_edge("report", END)

    return builder.compile(checkpointer=checkpointer)


@lru_cache
def get_compiled_graph():
    """Compiled graph with Postgres checkpointing, built once per process."""
    return build_graph(checkpointer=get_checkpointer())


def _config(assessment_id: str) -> dict:
    """The assessment id doubles as the checkpoint thread id."""
    return {"configurable": {"thread_id": assessment_id}}


def run_assessment(
    assessment_id: str,
    objective: str,
    sample_app_id: str,
    *,
    graph=None,
) -> AssessmentState:
    """Start a run. Returns when the graph completes or pauses for approval."""
    graph = graph or get_compiled_graph()
    initial: AssessmentState = {
        "assessment_id": assessment_id,
        "objective": objective,
        "sample_app_id": sample_app_id,
        "status": "retrieving",
        "trace_id": str(uuid.uuid4()),
        "revision_count": 0,
        "max_revisions": settings.max_revisions,
        "errors": [],
        "metrics": {},
    }
    graph.invoke(initial, config=_config(assessment_id))
    return get_assessment_state(assessment_id, graph=graph) or {}


def resume_with_decision(
    assessment_id: str,
    approved: bool,
    comment: str = "",
    *,
    graph=None,
) -> AssessmentState:
    """Resume a paused run with a human decision.

    Raises ValueError if the run isn't actually waiting on approval, so a stray
    call can't push a decision into a completed assessment.
    """
    graph = graph or get_compiled_graph()
    if not is_awaiting_approval(assessment_id, graph=graph):
        raise ValueError(f"Assessment {assessment_id} is not awaiting approval")

    graph.invoke(
        Command(resume={"approved": approved, "comment": comment}),
        config=_config(assessment_id),
    )
    return get_assessment_state(assessment_id, graph=graph) or {}


def is_awaiting_approval(assessment_id: str, *, graph=None) -> bool:
    graph = graph or get_compiled_graph()
    snapshot = graph.get_state(_config(assessment_id))
    return bool(snapshot and snapshot.interrupts)


def get_pending_approval(assessment_id: str, *, graph=None) -> dict | None:
    """The approval request payload the run is currently paused on, if any."""
    graph = graph or get_compiled_graph()
    snapshot = graph.get_state(_config(assessment_id))
    if not snapshot or not snapshot.interrupts:
        return None
    return snapshot.interrupts[0].value


def get_assessment_state(assessment_id: str, *, graph=None) -> AssessmentState | None:
    """Read current checkpointed state for an assessment, if any."""
    graph = graph or get_compiled_graph()
    snapshot = graph.get_state(_config(assessment_id))
    return snapshot.values if snapshot and snapshot.values else None


def extract_report(state: AssessmentState) -> AssessmentReport | None:
    return state.get("final_report")
