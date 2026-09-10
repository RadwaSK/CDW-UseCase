"""Trace recording for graph nodes and tool calls. Payloads are sanitized to an
allow-list (counts, names, durations) before persistence; write failures are
logged and swallowed so tracing never breaks a run."""

import logging
import time
from contextlib import contextmanager

from app.db.models import TraceEvent
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Keys allowed into a persisted trace payload; anything else is dropped, so a
# node can't leak content into the trace.
ALLOWED_PAYLOAD_KEYS = {
    "evidence_count",
    "architecture_finding_count",
    "risk_finding_count",
    "removed_claim_count",
    "revision_count",
    "will_revise",
    "approval_required",
    "approval_reasons",
    "approved",
    "ticket_number",
    "was_existing",
    "option_count",
    "overall_risk_level",
    "model",
    "input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "retrieval_count",
    "detail",
}


def sanitize(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k in ALLOWED_PAYLOAD_KEYS}


def record_event(
    assessment_id: str,
    trace_id: str,
    node: str,
    event_type: str,
    *,
    duration_ms: int | None = None,
    payload: dict | None = None,
    error_class: str | None = None,
) -> None:
    safe_payload = sanitize(payload or {})
    logger.info(
        event_type,
        extra={
            "assessment_id": assessment_id,
            "trace_id": trace_id,
            "node": node,
            "duration_ms": duration_ms,
            "error_class": error_class,
            **safe_payload,
        },
    )
    try:
        with SessionLocal() as db:
            db.add(
                TraceEvent(
                    assessment_id=assessment_id,
                    trace_id=trace_id,
                    node=node,
                    event_type=event_type,
                    duration_ms=duration_ms,
                    payload=safe_payload,
                    error_class=error_class,
                )
            )
            db.commit()
    except Exception as exc:  # noqa: BLE001 - observability must not break the run
        logger.warning(
            "trace_write_failed",
            extra={"node": node, "error_class": type(exc).__name__},
        )


@contextmanager
def traced_node(state: dict, node: str):
    """Record one node execution (or its failure) with duration. Yields a metrics
    dict for the node to populate."""
    assessment_id = state.get("assessment_id", "")
    trace_id = state.get("trace_id", "")
    metrics: dict = {}
    start = time.perf_counter()
    try:
        yield metrics
    except Exception as exc:
        record_event(
            assessment_id,
            trace_id,
            node,
            "node_failed",
            duration_ms=int((time.perf_counter() - start) * 1000),
            payload=metrics,
            error_class=type(exc).__name__,
        )
        raise
    else:
        record_event(
            assessment_id,
            trace_id,
            node,
            "node_completed",
            duration_ms=int((time.perf_counter() - start) * 1000),
            payload=metrics,
        )
