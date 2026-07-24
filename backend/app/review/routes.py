"""Authenticated review decisions with audit-backed completion gates."""

from __future__ import annotations

from datetime import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.audit.hash_chain import append_audit_event
from app.auth.jwt import CurrentUser
from app.db.models import (
    RedactionEntity,
    RedactionJob,
    ReviewDecision,
    ReviewStatus,
    utc_now,
)


router = APIRouter(prefix="/review", tags=["review"])


class ReviewEntityResponse(BaseModel):
    id: PydanticObjectId
    entity_type: str
    page_number: int | None
    confidence: float
    detector_source: list[str]
    explanation_text: str
    was_redacted: bool
    privileged_flag: bool
    review_decision: ReviewDecision
    review_note: str | None


class ReviewQueueResponse(BaseModel):
    job_id: PydanticObjectId
    document_id: PydanticObjectId
    status: ReviewStatus
    review_note: str | None
    reviewed_at: datetime | None
    entities: list[ReviewEntityResponse]
    pending_count: int
    flagged_count: int


class EntityDecisionRequest(BaseModel):
    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=1_000)


class FinalizeReviewRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2_000)


async def _owned_job(job_id: str, current_user: CurrentUser) -> RedactionJob:
    if current_user.id is None or not PydanticObjectId.is_valid(job_id):
        raise HTTPException(404, "Redaction job not found")
    job = await RedactionJob.find_one(RedactionJob.id == PydanticObjectId(job_id), RedactionJob.owner_id == current_user.id)
    if job is None:
        raise HTTPException(404, "Redaction job not found")
    return job


def _queue(job: RedactionJob, entities: list[RedactionEntity]) -> ReviewQueueResponse:
    response_entities = [ReviewEntityResponse.model_validate(entity, from_attributes=True) for entity in entities]
    return ReviewQueueResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=job.review_status,
        review_note=job.review_note,
        reviewed_at=job.reviewed_at,
        entities=response_entities,
        pending_count=sum(entity.review_decision == ReviewDecision.PENDING for entity in entities),
        flagged_count=sum(entity.review_decision == ReviewDecision.FLAGGED for entity in entities),
    )


@router.get("/{job_id}", response_model=ReviewQueueResponse)
async def review_queue(job_id: str, current_user: CurrentUser) -> ReviewQueueResponse:
    job = await _owned_job(job_id, current_user)
    entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
    return _queue(job, entities)


@router.post("/{job_id}/confirm-all", response_model=ReviewQueueResponse)
async def confirm_all_findings(job_id: str, current_user: CurrentUser) -> ReviewQueueResponse:
    """Confirm all unresolved findings without ever clearing a reviewer flag."""

    job = await _owned_job(job_id, current_user)
    if job.review_status == ReviewStatus.APPROVED:
        raise HTTPException(409, "Approved reviews are locked; request changes before editing findings")
    entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
    confirmed_count = 0
    for entity in entities:
        if entity.review_decision == ReviewDecision.PENDING:
            entity.review_decision = ReviewDecision.CONFIRMED
            await entity.save()
            confirmed_count += 1
    await append_audit_event(
        job.document_id,
        "review_findings_confirmed_bulk",
        {"confirmed_count": confirmed_count},
        job_id=job.id,
    )
    return _queue(job, entities)


@router.put("/{job_id}/entities/{entity_id}", response_model=ReviewEntityResponse)
async def decide_entity(
    job_id: str, entity_id: str, payload: EntityDecisionRequest, current_user: CurrentUser
) -> ReviewEntityResponse:
    job = await _owned_job(job_id, current_user)
    if not PydanticObjectId.is_valid(entity_id):
        raise HTTPException(404, "Review finding not found")
    entity = await RedactionEntity.find_one(RedactionEntity.id == PydanticObjectId(entity_id), RedactionEntity.job_id == job.id)
    if entity is None:
        raise HTTPException(404, "Review finding not found")
    if job.review_status == ReviewStatus.APPROVED:
        raise HTTPException(409, "Approved reviews are locked; request changes before editing findings")
    entity.review_decision = payload.decision
    entity.review_note = payload.note
    await entity.save()
    await append_audit_event(
        job.document_id,
        "review_finding_decided",
        {"entity_type": entity.entity_type, "decision": payload.decision.value, "has_note": bool(payload.note)},
        job_id=job.id,
    )
    return ReviewEntityResponse.model_validate(entity, from_attributes=True)


@router.post("/{job_id}/finalize", response_model=ReviewQueueResponse)
async def finalize_review(
    job_id: str, payload: FinalizeReviewRequest, current_user: CurrentUser
) -> ReviewQueueResponse:
    job = await _owned_job(job_id, current_user)
    entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
    flagged = sum(entity.review_decision == ReviewDecision.FLAGGED for entity in entities)
    pending = sum(entity.review_decision == ReviewDecision.PENDING for entity in entities)
    if payload.approve and (flagged or pending):
        raise HTTPException(409, "Confirm or resolve every finding before approving this output")
    job.review_status = ReviewStatus.APPROVED if payload.approve else ReviewStatus.CHANGES_REQUESTED
    job.review_note = payload.note
    job.reviewed_at = utc_now()
    await job.save()
    await append_audit_event(
        job.document_id,
        "review_finalized",
        {"status": job.review_status.value, "pending_count": pending, "flagged_count": flagged},
        job_id=job.id,
    )
    return _queue(job, entities)
