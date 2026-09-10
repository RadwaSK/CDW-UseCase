"""Mock ServiceNow change tool. Writes a synthetic ticket; calls nothing external."""

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ChangeTicket
from app.models.approval import TicketRecord, TicketRequest
from app.tools.base import timed_call

logger = logging.getLogger(__name__)

TICKET_PREFIX = "CHG-DEMO-"


class MockServiceNowChangeTool:
    """Creates one simulated change ticket per assessment.

    Idempotent by design: an assessment that already has a ticket gets that same
    ticket back rather than a second one, so a resumed or replayed run can never
    duplicate it. The DB also enforces this with a unique constraint on
    assessment_id — belt and braces, since "exactly one ticket" is a safety
    property, not just a nicety.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_assessment_ticket(self, request: TicketRequest) -> TicketRecord:
        with timed_call(
            "MockServiceNowChangeTool.create_assessment_ticket",
            request.assessment_id,
            severity=request.highest_severity,
        ):
            existing = self.db.scalar(
                select(ChangeTicket).where(ChangeTicket.assessment_id == request.assessment_id)
            )
            if existing is not None:
                logger.info(
                    "ticket_already_exists",
                    extra={
                        "assessment_id": request.assessment_id,
                        "ticket_number": existing.ticket_number,
                    },
                )
                return _to_record(existing, was_existing=True)

            ticket = ChangeTicket(
                assessment_id=request.assessment_id,
                ticket_number=self._next_ticket_number(),
                status="created",
                payload=request.model_dump(mode="json"),
            )
            self.db.add(ticket)
            try:
                self.db.commit()
            except IntegrityError:
                # Lost a race with a concurrent create — return the winner's ticket.
                self.db.rollback()
                existing = self.db.scalar(
                    select(ChangeTicket).where(
                        ChangeTicket.assessment_id == request.assessment_id
                    )
                )
                if existing is None:
                    raise
                return _to_record(existing, was_existing=True)

            self.db.refresh(ticket)
            return _to_record(ticket)

    def _next_ticket_number(self) -> str:
        count = self.db.scalar(select(func.count()).select_from(ChangeTicket)) or 0
        return f"{TICKET_PREFIX}{count + 1:04d}"


def _to_record(ticket: ChangeTicket, was_existing: bool = False) -> TicketRecord:
    return TicketRecord(
        ticket_number=ticket.ticket_number,
        assessment_id=ticket.assessment_id,
        status=ticket.status,
        created_at=ticket.created_at,
        summary=(ticket.payload or {}).get("summary", ""),
        was_existing=was_existing,
    )
