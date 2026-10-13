"""Append-only audit writer.

The audit trail records who did what, when. Events are only ever inserted — there is no
update or delete path anywhere in the codebase. Writers participate in the caller's
transaction so an event is committed atomically with the change it describes.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from core.models.enums import ActorType, EventSeverity
from core.models.workflow import AuditEvent

# Canonical event types (free-form strings are still accepted, but these keep it consistent).
EVENT_ACCOUNT_CONNECTED = "account.connected"
EVENT_ACCOUNT_VERIFICATION_FAILED = "account.verification_failed"
EVENT_SCAN_STARTED = "scan.started"
EVENT_SCAN_COMPLETED = "scan.completed"
EVENT_SCAN_PARTIAL = "scan.partial"
EVENT_SCAN_FAILED = "scan.failed"


def record_event(
    session: Session,
    *,
    event_type: str,
    summary: str,
    organization_id: uuid.UUID | None = None,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_user_id: uuid.UUID | None = None,
    severity: EventSeverity = EventSeverity.INFO,
    entity_type: str | None = None,
    entity_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an audit event to the current transaction."""
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        event_type=event_type,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        data=data or {},
    )
    session.add(event)
    return event
