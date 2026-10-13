"""Optimization models: recommendations, exclusions, rule configuration."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from core.models.enums import (
    Confidence,
    FindingType,
    OperationalRisk,
    RecommendationStatus,
    Reversibility,
)

if TYPE_CHECKING:
    from core.models.cloud import Resource

MONEY = Numeric(18, 6)


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint(
            "cloud_account_id",
            "resource_id",
            "rule_id",
            "rule_version",
            "observation_fingerprint",
            name="uq_recommendation_evidence",
        ),
        Index("ix_reco_org_status", "organization_id", "status"),
        Index("ix_reco_org_finding", "organization_id", "finding_type"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL"), index=True
    )
    finding_type: Mapped[FindingType] = mapped_column(
        SAEnum(FindingType, native_enum=False, validate_strings=True, length=32), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False)
    config_version: Mapped[str | None] = mapped_column(String(32))
    # Stable hash of the evidence used, so identical evidence de-duplicates.
    observation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    confidence: Mapped[Confidence] = mapped_column(
        SAEnum(Confidence, native_enum=False, validate_strings=True, length=16), nullable=False
    )
    operational_risk: Mapped[OperationalRisk] = mapped_column(
        SAEnum(OperationalRisk, native_enum=False, validate_strings=True, length=16), nullable=False
    )
    reversibility: Mapped[Reversibility] = mapped_column(
        SAEnum(Reversibility, native_enum=False, validate_strings=True, length=24), nullable=False
    )
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    observation_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_coverage_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    current_monthly_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    projected_monthly_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    estimated_monthly_savings: Mapped[Decimal | None] = mapped_column(MONEY)
    estimated_annual_savings: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_estimate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[RecommendationStatus] = mapped_column(
        SAEnum(RecommendationStatus, native_enum=False, validate_strings=True, length=24),
        default=RecommendationStatus.OPEN,
        nullable=False,
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL")
    )

    resource: Mapped[Resource | None] = relationship()


class ResourceExclusion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resource_exclusions"
    __table_args__ = (Index("ix_exclusion_org_account", "organization_id", "cloud_account_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # match_type: resource (exact id/arn) | tag (key/value) | type (resource_type)
    match_type: Mapped[str] = mapped_column(String(16), nullable=False)
    match_key: Mapped[str | None] = mapped_column(String(120))
    match_value: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class RuleConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rule_configs"
    __table_args__ = (
        UniqueConstraint("organization_id", "rule_id", "version", name="uq_rule_config_version"),
    )

    # Null organization_id == platform default.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
