"""Enumerations shared across models and services.

Enums are persisted as validated strings (``native_enum=False``) to keep migrations and
future additions simple and to avoid PostgreSQL type churn.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    FINOPS_ANALYST = "finops_analyst"
    APPROVER = "approver"
    VIEWER = "viewer"


class ConnectionStatus(StrEnum):
    PENDING = "pending"
    CONNECTED = "connected"
    ERROR = "error"


class ScanType(StrEnum):
    DISCOVERY = "discovery"
    BILLING = "billing"
    METRICS = "metrics"
    ANALYSIS = "analysis"


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class ResourceType(StrEnum):
    EC2_INSTANCE = "ec2_instance"
    EBS_VOLUME = "ebs_volume"
    EBS_SNAPSHOT = "ebs_snapshot"
    ELASTIC_IP = "elastic_ip"
    RDS_INSTANCE = "rds_instance"
    RDS_CLUSTER = "rds_cluster"
    ELB = "elb"


class OptimizationStatus(StrEnum):
    UNKNOWN = "unknown"
    NOT_ANALYZED = "not_analyzed"
    IDLE = "idle"
    UNDERUTILIZED = "underutilized"
    OPTIMIZED = "optimized"
    EXCLUDED = "excluded"


class FindingType(StrEnum):
    IDLE_EC2 = "idle_ec2"
    RIGHTSIZING_EC2 = "rightsizing_ec2"
    UNATTACHED_EBS = "unattached_ebs"
    IDLE_ELASTIC_IP = "idle_elastic_ip"
    COST_ANOMALY = "cost_anomaly"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OperationalRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Reversibility(StrEnum):
    REVERSIBLE = "reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class RecommendationStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVED = "approved"
    EXECUTED = "executed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActionType(StrEnum):
    STOP_INSTANCE = "stop_instance"
    START_INSTANCE = "start_instance"


class ActionRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class JobType(StrEnum):
    DISCOVERY = "discovery"
    BILLING = "billing"
    METRICS = "metrics"
    ANALYSIS = "analysis"
    EXECUTION = "execution"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    WORKER = "worker"


class Attribution(StrEnum):
    SERVICE = "service"
    REGION = "region"
    ACCOUNT = "account"
    RESOURCE = "resource"


class Granularity(StrEnum):
    DAILY = "daily"
    MONTHLY = "monthly"
