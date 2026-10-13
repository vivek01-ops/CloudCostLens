"""Workflow models: approvals, action runs, audit events, scheduled jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from core.models.enums import (
    ActionRunStatus,
    ActionType,
    ActorType,
    ApprovalStatus,
    EventSeverity,
    JobStatus,
    JobType,
    OperationalRisk,
)

if TYPE_CHECKING:
    from core.models.optimization import Recommendation

MONEY = Numeric(18, 6)


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_org_status", "organization_id", "status"),
        UniqueConstraint("idempotency_key", name="uq_approval_idempotency_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL")
    )
    action: Mapped[ActionType] = mapped_column(
        SAEnum(ActionType, native_enum=False, validate_strings=True, length=24), nullable=False
    )
    action_parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # sha256 over canonical (account, region, arn, action, params).
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    estimated_monthly_savings: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    operational_risk: Mapped[OperationalRisk] = mapped_column(
        SAEnum(OperationalRisk, native_enum=False, validate_strings=True, length=16),
        default=OperationalRisk.MEDIUM,
        nullable=False,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, native_enum=False, validate_strings=True, length=16),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recommendation: Mapped[Recommendation] = relationship()
    action_runs: Mapped[list[ActionRun]] = relationship(
        back_populates="approval", cascade="all, delete-orphan"
    )


class ActionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "action_runs"
    __table_args__ = (Index("ix_action_run_approval_attempt", "approval_request_id", "attempt_no"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ActionRunStatus] = mapped_column(
        SAEnum(ActionRunStatus, native_enum=False, validate_strings=True, length=16),
        default=ActionRunStatus.RUNNING,
        nullable=False,
    )
    aws_request_id: Mapped[str | None] = mapped_column(String(128))
    request_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    verified_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    approval: Mapped[ApprovalRequest] = relationship(back_populates="action_runs")


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail. There is intentionally no update/delete API."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_org_event", "organization_id", "event_type"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_type: Mapped[ActorType] = mapped_column(
        SAEnum(ActorType, native_enum=False, validate_strings=True, length=16),
        default=ActorType.SYSTEM,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(
        SAEnum(EventSeverity, native_enum=False, validate_strings=True, length=16),
        default=EventSeverity.INFO,
        nullable=False,
    )
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScheduledJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index("ix_job_status_run_after", "status", "run_after"),
        Index("ix_job_account_type", "cloud_account_id", "job_type"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cloud_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, native_enum=False, validate_strings=True, length=16), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False, validate_strings=True, length=16),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(120))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
