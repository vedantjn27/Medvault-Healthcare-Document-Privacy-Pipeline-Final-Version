"""Derived, PHI-free insights for individual jobs and the authenticated workspace."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.auth.jwt import CurrentUser
from app.db.models import JobStatus, RedactionEntity, RedactionJob, ReviewStatus, UploadedDocument, utc_now


router = APIRouter(prefix="/intelligence", tags=["document intelligence"])


class JobInsight(BaseModel):
    job_id: PydanticObjectId
    status: JobStatus
    document_type: str
    privacy_mode: str
    qa_passed: bool
    review_status: ReviewStatus
    risk_level: str
    risk_factors: list[str]
    entity_count: int
    redacted_count: int
    coverage_percent: float
    category_counts: dict[str, int]
    detector_counts: dict[str, int]
    recommendations: list[str]


class WorkspaceAnalytics(BaseModel):
    completed_jobs: int
    qa_pass_rate: float
    review_approval_rate: float
    average_redactions: float
    privacy_mode_counts: dict[str, int]
    category_counts: dict[str, int]
    generated_at: datetime


async def _owned(job_id: str, user: CurrentUser) -> RedactionJob:
    if user.id is None or not PydanticObjectId.is_valid(job_id):
        raise HTTPException(404, "Redaction job not found")
    job = await RedactionJob.find_one(RedactionJob.id == PydanticObjectId(job_id), RedactionJob.owner_id == user.id)
    if job is None:
        raise HTTPException(404, "Redaction job not found")
    return job


def _recommendations(job: RedactionJob, entities: list[RedactionEntity]) -> list[str]:
    recommendations: list[str] = []
    if not job.qa_passed:
        recommendations.append("QA identified residual sensitive data; do not distribute this output.")
    if job.review_status != ReviewStatus.APPROVED:
        recommendations.append("Complete the human review queue before creating a secure share link.")
    if job.reidentification_risk and job.reidentification_risk.value != "low":
        recommendations.append("Use a more restrictive privacy mode or remove quasi-identifiers before research sharing.")
    if any(entity.privileged_flag for entity in entities):
        recommendations.append("Legal-context findings were detected; route this document through privileged review.")
    if not recommendations:
        recommendations.append("QA and review requirements are satisfied; the output is ready for controlled distribution.")
    return recommendations


@router.get("/jobs/{job_id}", response_model=JobInsight)
async def job_intelligence(job_id: str, current_user: CurrentUser) -> JobInsight:
    job = await _owned(job_id, current_user)
    entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
    redacted = [entity for entity in entities if entity.was_redacted]
    document_type = "unknown"
    document = await UploadedDocument.get(job.document_id)
    if document:
        document_type = document.file_type
    category_counts = dict(Counter(entity.entity_type for entity in redacted))
    detector_counts = dict(Counter(source for entity in entities for source in entity.detector_source))
    return JobInsight(
        job_id=job.id, status=job.status, document_type=document_type, privacy_mode=job.privacy_mode.value,
        qa_passed=job.qa_passed, review_status=job.review_status,
        risk_level=job.reidentification_risk.value if job.reidentification_risk else "not_assessed",
        risk_factors=list(job.reidentification_factors), entity_count=len(entities),
        redacted_count=len(redacted), coverage_percent=round((len(redacted) / len(entities) * 100) if entities else 100, 1),
        category_counts=category_counts, detector_counts=detector_counts,
        recommendations=_recommendations(job, entities),
    )


@router.get("/workspace", response_model=WorkspaceAnalytics)
async def workspace_analytics(
    current_user: CurrentUser,
    job_id: list[str] = Query(default=[]),
) -> WorkspaceAnalytics:
    if current_user.id is None:
        raise HTTPException(401, "Could not validate credentials")
    requested_ids = [PydanticObjectId(value) for value in job_id if PydanticObjectId.is_valid(value)]
    if job_id and not requested_ids:
        jobs = []
    elif requested_ids:
        jobs = await RedactionJob.find(
            RedactionJob.owner_id == current_user.id,
            RedactionJob.id.in_(requested_ids),
        ).to_list()
    else:
        jobs = await RedactionJob.find(RedactionJob.owner_id == current_user.id).to_list()
    completed = [job for job in jobs if job.status in {JobStatus.COMPLETE, JobStatus.QA_FAILED}]
    job_ids = [job.id for job in completed]
    entities = await RedactionEntity.find({"job_id": {"$in": job_ids}}).to_list() if job_ids else []
    redacted_by_job = Counter(str(entity.job_id) for entity in entities if entity.was_redacted)
    qa_rate = (sum(job.qa_passed for job in completed) / len(completed) * 100) if completed else 0
    approval_rate = (sum(job.review_status == ReviewStatus.APPROVED for job in completed) / len(completed) * 100) if completed else 0
    return WorkspaceAnalytics(
        completed_jobs=len(completed), qa_pass_rate=round(qa_rate, 1), review_approval_rate=round(approval_rate, 1),
        average_redactions=round(sum(redacted_by_job.values()) / len(completed), 1) if completed else 0,
        privacy_mode_counts=dict(Counter(job.privacy_mode.value for job in completed)),
        category_counts=dict(Counter(entity.entity_type for entity in entities if entity.was_redacted)),
        generated_at=utc_now(),
    )
