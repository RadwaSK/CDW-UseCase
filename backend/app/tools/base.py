"""Tool Protocols and the shared call-logging wrapper. Protocols let a real
ServiceNow/CMDB integration drop in without touching the graph."""

import logging
import time
from typing import Protocol

from app.models.approval import TicketRecord, TicketRequest

logger = logging.getLogger(__name__)


class ChangeManagementTool(Protocol):
    def create_assessment_ticket(self, request: TicketRequest) -> TicketRecord: ...


class AssetInventoryTool(Protocol):
    def get_service_context(self, sample_app_id: str) -> dict: ...


def log_tool_call(tool_name: str, correlation_id: str, **fields) -> None:
    """Structured log line for every tool invocation, keyed by correlation id."""
    logger.info(
        "tool_call",
        extra={"tool": tool_name, "correlation_id": correlation_id, **fields},
    )


class timed_call:
    """Times a tool call and logs it with its correlation id."""

    def __init__(self, tool_name: str, correlation_id: str, **fields):
        self.tool_name = tool_name
        self.correlation_id = correlation_id
        self.fields = fields
        self.duration_ms = 0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.duration_ms = int((time.perf_counter() - self._start) * 1000)
        log_tool_call(
            self.tool_name,
            self.correlation_id,
            duration_ms=self.duration_ms,
            error_class=exc_type.__name__ if exc_type else None,
            **self.fields,
        )
        return False
