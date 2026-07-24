"""Beanie documents for metadata, jobs, redactions, feedback, and audit events."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pymongo import ASCENDING, IndexModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXPIRED = "expired"
    DONE = "done"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    QA_FAILED = "qa_failed"
    COMPLETE = "complete"
    ERROR = "error"


class PrivacyMode(StrEnum):
    PATIENT_PORTAL = "patient_portal"
    RESEARCH_SHARING = "research_sharing"
    INSURANCE_PROCESSING = "insurance_processing"
    LEGAL_DISCOVERY = "legal_discovery"
    CUSTOM = "custom"


class ReidentificationRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeedbackVerdict(StrEnum):
    CORRECT = "correct"
    FALSE_POSITIVE = "false_positive"
    MISSED = "missed"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class ReviewDecision(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FLAGGED = "flagged"


class ShareRole(StrEnum):
    REVIEWER = "reviewer"
    RECIPIENT = "recipient"


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class BatchItem(BaseModel):
    document_id: PydanticObjectId
    redaction_job_id: PydanticObjectId | None = None
    status: JobStatus = JobStatus.QUEUED
    error_message: str | None = None


class User(Document):
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=utc_now)
    push_subscription: PushSubscription | None = None
    is_active: bool = True

    class Settings:
        name = "users"
        indexes = [IndexModel([("email", ASCENDING)], unique=True, name="uq_users_email")]


class UploadedDocument(Document):
    owner_id: PydanticObjectId
    original_filename: str
    file_type: str
    uploaded_at: datetime = Field(default_factory=utc_now)
    status: DocumentStatus = DocumentStatus.UPLOADED
    temp_job_path: str
    expires_at: datetime

    class Settings:
        name = "documents"
        indexes = [
            IndexModel([("owner_id", ASCENDING)], name="ix_documents_owner_id"),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_documents_expires_at"),
        ]


class RedactionJob(Document):
    document_id: PydanticObjectId
    owner_id: PydanticObjectId
    privacy_mode: PrivacyMode
    custom_rules: dict[str, Any] | None = None
    idempotency_key: str | None = None
    status: JobStatus = JobStatus.QUEUED
    qa_passed: bool = False
    reidentification_risk: ReidentificationRisk | None = None
    reidentification_factors: list[str] = Field(default_factory=list)
    error_message: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_at: datetime | None = None
    review_note: str | None = Field(default=None, max_length=2_000)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    class Settings:
        name = "redaction_jobs"
        indexes = [
            IndexModel([("document_id", ASCENDING)], name="ix_redaction_jobs_document_id"),
            IndexModel([("owner_id", ASCENDING)], name="ix_redaction_jobs_owner_id"),
            IndexModel([("status", ASCENDING)], name="ix_redaction_jobs_status"),
            IndexModel(
                [("owner_id", ASCENDING), ("idempotency_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"idempotency_key": {"$type": "string"}},
                name="uq_redaction_owner_idempotency",
            ),
        ]


class RedactionEntity(Document):
    job_id: PydanticObjectId
    entity_type: str
    page_number: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    detector_source: list[str]
    explanation_text: str
    was_redacted: bool
    privileged_flag: bool = False
    review_decision: ReviewDecision = ReviewDecision.PENDING
    review_note: str | None = Field(default=None, max_length=1_000)

    class Settings:
        name = "redaction_entities"
        indexes = [IndexModel([("job_id", ASCENDING)], name="ix_redaction_entities_job_id")]


class AuditLog(Document):
    document_id: PydanticObjectId
    job_id: PydanticObjectId | None = None
    event_type: str
    event_data: dict[str, Any] = Field(default_factory=dict)
    entry_hash: str
    previous_hash: str | None = None
    sequence: int = Field(ge=1)
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "audit_log"
        indexes = [
            IndexModel([("document_id", ASCENDING), ("created_at", ASCENDING)], name="ix_audit_document_time"),
            IndexModel([("document_id", ASCENDING), ("sequence", ASCENDING)], unique=True, name="uq_audit_document_sequence"),
        ]


class Feedback(Document):
    job_id: PydanticObjectId
    entity_id: PydanticObjectId | None = None
    user_id: PydanticObjectId
    verdict: FeedbackVerdict
    note: str | None = Field(default=None, max_length=2_000)
    entity_type: str | None = Field(default=None, max_length=64)
    page_number: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "feedback"
        indexes = [IndexModel([("job_id", ASCENDING)], name="ix_feedback_job_id")]


class BatchJob(Document):
    owner_id: PydanticObjectId
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    downloaded_at: datetime | None = None
    idempotency_key: str | None = None
    items: list[BatchItem] = Field(default_factory=list)

    class Settings:
        name = "batch_jobs"
        indexes = [
            IndexModel([("owner_id", ASCENDING)], name="ix_batch_jobs_owner_id"),
            IndexModel([("status", ASCENDING)], name="ix_batch_jobs_status"),
            IndexModel(
                [("owner_id", ASCENDING), ("idempotency_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"idempotency_key": {"$type": "string"}},
                name="uq_batch_owner_idempotency",
            ),
        ]


class ShareLink(Document):
    job_id: PydanticObjectId
    document_id: PydanticObjectId
    owner_id: PydanticObjectId
    token_hash: str
    role: ShareRole = ShareRole.RECIPIENT
    recipient_email: EmailStr | None = None
    password_hash: str | None = None
    allow_download: bool = True
    max_accesses: int | None = Field(default=None, ge=1, le=100)
    access_count: int = Field(default=0, ge=0)
    revoked_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

    class Settings:
        name = "share_links"
        indexes = [
            IndexModel([("token_hash", ASCENDING)], unique=True, name="uq_share_token_hash"),
            IndexModel([("owner_id", ASCENDING), ("job_id", ASCENDING)], name="ix_share_owner_job"),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_share_expires_at"),
        ]


class ShareAccess(Document):
    share_link_id: PydanticObjectId
    action: str = Field(max_length=32)
    accessed_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "share_access"
        indexes = [IndexModel([("share_link_id", ASCENDING), ("accessed_at", ASCENDING)], name="ix_share_access_time")]


DOCUMENT_MODELS: tuple[type[Document], ...] = (
    User,
    UploadedDocument,
    RedactionJob,
    RedactionEntity,
    AuditLog,
    Feedback,
    BatchJob,
    ShareLink,
    ShareAccess,
)


class PublicModel(BaseModel):
    """Base for API models that serialize Beanie identifiers as strings."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
