"""Cloud inventory, cost, metric, and pricing models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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
    Attribution,
    ConnectionStatus,
    Granularity,
    OptimizationStatus,
    ResourceType,
    ScanStatus,
    ScanType,
)

if TYPE_CHECKING:
    from core.models.identity import Organization

MONEY = Numeric(18, 6)


class CloudAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cloud_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "aws_account_id", name="uq_cloud_account"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    aws_account_id: Mapped[str] = mapped_column(String(12), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    role_arn: Mapped[str | None] = mapped_column(String(300))
    # Fernet-encrypted external ID. Never store or log plaintext.
    external_id_encrypted: Mapped[str | None] = mapped_column(Text)
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        SAEnum(ConnectionStatus, native_enum=False, validate_strings=True, length=16),
        default=ConnectionStatus.PENDING,
        nullable=False,
    )
    default_region: Mapped[str] = mapped_column(String(32), nullable=False, default="us-east-1")
    enabled_regions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[Organization] = relationship(back_populates="cloud_accounts")
    resources: Mapped[list[Resource]] = relationship(
        back_populates="cloud_account", cascade="all, delete-orphan"
    )


class ScanRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scan_runs"
    __table_args__ = (Index("ix_scan_runs_account_type", "cloud_account_id", "scan_type"),)

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_type: Mapped[ScanType] = mapped_column(
        SAEnum(ScanType, native_enum=False, validate_strings=True, length=16), nullable=False
    )
    status: Mapped[ScanStatus] = mapped_column(
        SAEnum(ScanStatus, native_enum=False, validate_strings=True, length=16),
        default=ScanStatus.QUEUED,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    region: Mapped[str | None] = mapped_column(String(32))
    resources_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Resource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint(
            "cloud_account_id",
            "resource_type",
            "resource_id",
            "region",
            name="uq_resource_identity",
        ),
        Index("ix_resources_org_type", "organization_id", "resource_type"),
        Index("ix_resources_org_region", "organization_id", "region"),
        Index("ix_resources_org_state", "organization_id", "state"),
        Index("ix_resources_org_opt_status", "organization_id", "optimization_status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[ResourceType] = mapped_column(
        SAEnum(ResourceType, native_enum=False, validate_strings=True, length=24), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    arn: Mapped[str | None] = mapped_column(String(512))
    name: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str | None] = mapped_column(String(64))
    environment: Mapped[str | None] = mapped_column(String(64))
    owner: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    monthly_cost_estimate: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    optimization_status: Mapped[OptimizationStatus] = mapped_column(
        SAEnum(OptimizationStatus, native_enum=False, validate_strings=True, length=16),
        default=OptimizationStatus.UNKNOWN,
        nullable=False,
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    cloud_account: Mapped[CloudAccount] = relationship(back_populates="resources")
    metrics: Mapped[list[ResourceMetricSummary]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceMetricSummary(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resource_metric_summaries"
    __table_args__ = (
        Index("ix_metric_resource_name_start", "resource_id", "metric_name", "period_start"),
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    statistic: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(MONEY)
    unit: Mapped[str | None] = mapped_column(String(32))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # 0-100; how much of the expected window had data. Low coverage != zero utilization.
    coverage_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="cloudwatch")
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    resource: Mapped[Resource] = relationship(back_populates="metrics")


class CostRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "cost_records"
    __table_args__ = (
        Index("ix_cost_org_period", "organization_id", "period_start"),
        Index("ix_cost_org_service", "organization_id", "service"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    granularity: Mapped[Granularity] = mapped_column(
        SAEnum(Granularity, native_enum=False, validate_strings=True, length=16), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    attribution: Mapped[Attribution] = mapped_column(
        SAEnum(Attribution, native_enum=False, validate_strings=True, length=16), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="cost_explorer")
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    collection_lag_days: Mapped[int | None] = mapped_column(Integer)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PricingCache(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pricing_cache"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "service_code",
            "instance_type",
            "region",
            "term",
            name="uq_pricing_lookup",
        ),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    service_code: Mapped[str] = mapped_column(String(64), nullable=False)
    instance_type: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    term: Mapped[str] = mapped_column(String(16), nullable=False, default="OnDemand")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="Hrs")
    price_per_unit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
