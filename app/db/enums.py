"""Domain enumerations used across ORM models."""

from __future__ import annotations

import enum


class AlertStatus(str, enum.Enum):
    NEW = "new"
    TRIAGED = "triaged"
    EVENT_LINKED = "event_linked"
    ARCHIVED = "archived"


class RouteDecision(str, enum.Enum):
    ARCHIVE_LOW_RISK = "archive_low_risk"
    ARCHIVE_WHITELIST = "archive_whitelist"
    ARCHIVE_DEDUP = "archive_dedup"
    QUEUE_DEEP_REVIEW = "queue_deep_review"
    QUEUE_UNCERTAIN = "queue_uncertain"
    SAMPLE_AUDIT = "sample_audit"


class WhitelistRuleType(str, enum.Enum):
    IP = "ip"
    USER = "user"
    HOST = "host"
    HASH = "hash"
    COMPOSITE = "composite"


class WhitelistRuleStatus(str, enum.Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class WhitelistCandidateStatus(str, enum.Enum):
    PENDING = "pending"
    PROMOTED = "promoted"
    REJECTED = "rejected"


class EntityType(str, enum.Enum):
    IP = "ip"
    HOST = "host"
    USER = "user"
    DOMAIN = "domain"


class AssetCriticality(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EntityMemoryType(str, enum.Enum):
    BEHAVIOR_NOTE = "behavior_note"
    PAST_VERDICT = "past_verdict"
    OPERATOR_COMMENT = "operator_comment"


class IocType(str, enum.Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"
    URL = "url"


class ThreatIntelVerdict(str, enum.Enum):
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    UNKNOWN = "unknown"


class EventStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    INVESTIGATING = "investigating"
    CONCLUDED = "concluded"
    HUMAN_PENDING = "human_pending"
    CLOSED = "closed"


class InvestigationStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"
    DEGRADED = "degraded"


class InvestigationVerdict(str, enum.Enum):
    ATTACK_CONFIRMED = "attack_confirmed"
    LIKELY_FALSE_POSITIVE = "likely_false_positive"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class RiskLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ImChannel(str, enum.Enum):
    WECOM = "wecom"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"


class HumanReviewStatus(str, enum.Enum):
    SENT = "sent"
    ANSWERED = "answered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AuditSampleReason(str, enum.Enum):
    LOW_RISK_RANDOM = "low_risk_random"
    QUALITY_AUDIT = "quality_audit"


class CandidateStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProfileUpdateStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"


class DispositionStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class DispositionSimulationApprovalStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class CacheType(str, enum.Enum):
    STRONG_CONCLUSION = "strong_conclusion"
    INTERMEDIATE_EVIDENCE = "intermediate_evidence"
    MUST_REJUDGE = "must_rejudge"


class ActorType(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


class HealthCheckStage(str, enum.Enum):
    INGESTION = "ingestion"
    TRIAGE = "triage"
    AGGREGATION = "aggregation"
    AGENT = "agent"
    CONCLUSION = "conclusion"
    FULL_CHAIN = "full_chain"
