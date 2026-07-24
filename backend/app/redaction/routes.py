"""Redaction submission, status, privacy-safe report, and session download routes."""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from pymongo.errors import DuplicateKeyError

from app.auth.jwt import CurrentUser
from app.config import Settings, get_settings
from app.db.models import (
    BoundingBox,
    Feedback,
    FeedbackVerdict,
    JobStatus,
    PrivacyMode,
    ReidentificationRisk,
    RedactionEntity,
    RedactionJob,
    UploadedDocument,
)
from app.documents.file_types import FileType
from app.documents.preview import PreviewError, PreviewResponse, build_preview, render_preview_page
from app.redaction.mode_configs import CustomRules, get_mode_config
from app.redaction.report_pdf import build_report_pdf
from app.redaction.pipeline import (
    SUPPORTED_PIPELINE_TYPES,
    output_path_for,
    process_redaction_job,
)
from app.storage.temp_manager import ensure_within_root
from app.audit.hash_chain import append_audit_event


router = APIRouter(prefix="/redaction", tags=["redaction"])


class Verbosity(StrEnum):
    STANDARD = "standard"
    ENTITY_TYPE = "entity_type"


class RedactionRunRequest(BaseModel):
    document_id: PydanticObjectId
    privacy_mode: PrivacyMode
    custom_rules: CustomRules | None = None
    verbosity: Verbosity = Verbosity.STANDARD
    subject_patient_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_mode_rules(self) -> "RedactionRunRequest":
        get_mode_config(self.privacy_mode, self.custom_rules)
        return self


class JobResponse(BaseModel):
    job_id: PydanticObjectId
    document_id: PydanticObjectId
    privacy_mode: PrivacyMode
    status: JobStatus
    qa_passed: bool
    reidentification_risk: ReidentificationRisk | None
    reidentification_factors: list[str]
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None


class EntityReport(BaseModel):
    id: PydanticObjectId
    entity_type: str
    page_number: int | None
    bbox: BoundingBox | None
    confidence: float
    detector_source: list[str]
    explanation_text: str
    was_redacted: bool
    privileged_flag: bool


class RedactionReport(BaseModel):
    job: JobResponse
    entity_count: int
    redacted_count: int
    reviewed_not_redacted_count: int
    entities: list[EntityReport]


class FeedbackRequest(BaseModel):
    job_id: PydanticObjectId
    entity_id: PydanticObjectId | None = None
    verdict: FeedbackVerdict
    note: str | None = Field(default=None, max_length=2_000)
    entity_type: str | None = Field(default=None, min_length=1, max_length=64)
    page_number: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None

    @model_validator(mode="after")
    def validate_missed_location(self):
        if self.verdict == FeedbackVerdict.MISSED:
            if self.entity_id is not None:
                raise ValueError("Missed feedback must describe a new location")
            if not self.entity_type or self.page_number is None:
                raise ValueError("Missed feedback requires entity_type and page_number")
        return self


class ModeComparisonRequest(BaseModel):
    document_id: PydanticObjectId
    modes: list[PrivacyMode] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def unique_modes(self):
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("Comparison modes must be unique")
        if PrivacyMode.CUSTOM in self.modes:
            raise ValueError("Custom mode comparison requires explicit rules and is not supported here")
        return self


def _job_response(job: RedactionJob) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        document_id=job.document_id,
        privacy_mode=job.privacy_mode,
        status=job.status,
        qa_passed=job.qa_passed,
        reidentification_risk=job.reidentification_risk,
        reidentification_factors=job.reidentification_factors,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


async def _owned_job(job_id: str, user_id: PydanticObjectId | None) -> RedactionJob:
    if user_id is None or not PydanticObjectId.is_valid(job_id):
        raise HTTPException(status_code=404, detail="Redaction job not found")
    job = await RedactionJob.find_one(
        RedactionJob.id == PydanticObjectId(job_id),
        RedactionJob.owner_id == user_id,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Redaction job not found")
    return job


@router.post("/run", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_redaction(
    payload: RedactionRunRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=128)
    ] = None,
) -> JobResponse:
    if idempotency_key:
        existing = await RedactionJob.find_one(
            RedactionJob.owner_id == current_user.id,
            RedactionJob.idempotency_key == idempotency_key,
        )
        if existing is not None:
            return _job_response(existing)
    document = await UploadedDocument.find_one(
        UploadedDocument.id == payload.document_id,
        UploadedDocument.owner_id == current_user.id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.file_type not in SUPPORTED_PIPELINE_TYPES:
        raise HTTPException(status_code=415, detail="This format is not enabled for redaction yet")
    source = ensure_within_root(Path(document.temp_job_path), settings.temp_job_dir)
    if not source.is_file():
        raise HTTPException(status_code=410, detail="Document temporary data has expired")
    job = RedactionJob(
        document_id=document.id,
        owner_id=current_user.id,
        privacy_mode=payload.privacy_mode,
        custom_rules=payload.custom_rules.model_dump(mode="json") if payload.custom_rules else None,
        idempotency_key=idempotency_key,
        status=JobStatus.QUEUED,
    )
    try:
        await job.insert()
    except DuplicateKeyError:
        existing = await RedactionJob.find_one(
            RedactionJob.owner_id == current_user.id,
            RedactionJob.idempotency_key == idempotency_key,
        )
        if existing is None:
            raise
        return _job_response(existing)
    background_tasks.add_task(
        process_redaction_job,
        job.id,
        settings,
        subject_patient_id=payload.subject_patient_id,
        verbose_labels=payload.verbosity == Verbosity.ENTITY_TYPE,
    )
    return _job_response(job)


@router.get("/{job_id}/status", response_model=JobResponse)
async def redaction_status(job_id: str, current_user: CurrentUser) -> JobResponse:
    return _job_response(await _owned_job(job_id, current_user.id))


@router.get("/{job_id}/report", response_model=RedactionReport)
async def redaction_report(job_id: str, current_user: CurrentUser) -> RedactionReport:
    job = await _owned_job(job_id, current_user.id)
    if job.status not in {JobStatus.COMPLETE, JobStatus.QA_FAILED, JobStatus.ERROR}:
        raise HTTPException(status_code=409, detail="Redaction report is not ready")
    entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
    reports = [EntityReport.model_validate(entity, from_attributes=True) for entity in entities]
    redacted_count = sum(entity.was_redacted for entity in reports)
    return RedactionReport(
        job=_job_response(job),
        entity_count=len(reports),
        redacted_count=redacted_count,
        reviewed_not_redacted_count=len(reports) - redacted_count,
        entities=reports,
    )


@router.get("/{job_id}/report/download")
async def download_redaction_report(job_id: str, current_user: CurrentUser) -> Response:
    """Export the report summary, charts, and safe entity findings as a PDF."""

    job = await _owned_job(job_id, current_user.id)
    if job.status not in {JobStatus.COMPLETE, JobStatus.QA_FAILED, JobStatus.ERROR}:
        raise HTTPException(status_code=409, detail="Redaction report is not ready")
    entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
    pdf = await asyncio.to_thread(build_report_pdf, job, entities)
    filename = f"medvault_redaction_report_{job.id}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{job_id}/heatmap")
async def redaction_heatmap(job_id: str, current_user: CurrentUser) -> Response:
    job = await _owned_job(job_id, current_user.id)
    if job.status not in {JobStatus.COMPLETE, JobStatus.QA_FAILED}:
        raise HTTPException(status_code=409, detail="Heatmap is not ready")
    entities = await RedactionEntity.find(
        RedactionEntity.job_id == job.id, RedactionEntity.was_redacted == True  # noqa: E712
    ).to_list()
    document = await UploadedDocument.get(job.document_id)
    page_sizes = _heatmap_page_sizes(document, job) if document else {1: (612.0, 792.0)}
    pages = sorted(page_sizes)
    rendered_heights = {page: 612.0 * page_sizes[page][1] / page_sizes[page][0] for page in pages}
    page_entities: dict[int, list[RedactionEntity]] = {page: [] for page in pages}
    unlocated: dict[int, int] = {page: 0 for page in pages}
    for entity in entities:
        page_number = entity.page_number or 1
        if page_number not in page_entities:
            page_entities[page_number] = []
            unlocated[page_number] = 0
        if entity.bbox:
            page_entities[page_number].append(entity)
        else:
            unlocated[page_number] += 1
    offsets: dict[int, float] = {}
    cursor = 0.0
    for page in pages:
        offsets[page] = cursor
        cursor += rendered_heights[page] + 58
    height = max(1, int(cursor + 58))
    shapes: list[str] = []
    for page_number, page_items in page_entities.items():
        for entity in page_items:
            box = entity.bbox
            if box is None:
                continue
            opacity = max(0.45, min(0.95, entity.confidence))
            color = (
                "#dc2626" if entity.confidence >= 0.85 else
                "#f97316" if entity.confidence >= 0.65 else "#eab308"
            )
            page_width, _ = page_sizes.get(page_number, (612.0, 792.0))
            scale = 612.0 / page_width
            shapes.append(
                f'<rect x="{box.x0*scale:.2f}" y="{offsets.get(page_number, 0)+34+box.y0*scale:.2f}" '
                f'width="{max(2, (box.x1-box.x0)*scale):.2f}" height="{max(2, (box.y1-box.y0)*scale):.2f}" '
                f'fill="{color}" fill-opacity="{opacity:.2f}" stroke="#7f1d1d" stroke-width="0.7"/>'
            )
    page_rects = "".join(
        f'<g>'
        f'<rect x="1" y="{offsets[page]+1:.2f}" width="610" height="{rendered_heights[page]+32:.2f}" rx="4" fill="#ffffff" stroke="#94a3b8"/>'
        f'<rect x="1" y="{offsets[page]+1:.2f}" width="610" height="32" rx="4" fill="#e2e8f0"/>'
        f'<text x="14" y="{offsets[page]+22:.2f}" font-family="Arial, sans-serif" font-size="13" fill="#0f172a">'
        f'Page {page} · {len(page_entities.get(page, []))} located redaction{("s" if len(page_entities.get(page, [])) != 1 else "")}'
        f'{(" · " + str(unlocated.get(page, 0)) + " without coordinates" if unlocated.get(page, 0) else "")}</text>'
        f'</g>'
        for page in pages
    )
    legend_y = height - 36
    legend = (
        f'<g font-family="Arial, sans-serif" font-size="12" fill="#0f172a">'
        f'<text x="10" y="{legend_y:.2f}">Confidence:</text>'
        f'<rect x="88" y="{legend_y-11:.2f}" width="20" height="12" fill="#eab308"/><text x="113" y="{legend_y:.2f}">40–64%</text>'
        f'<rect x="185" y="{legend_y-11:.2f}" width="20" height="12" fill="#f97316"/><text x="210" y="{legend_y:.2f}">65–84%</text>'
        f'<rect x="282" y="{legend_y-11:.2f}" width="20" height="12" fill="#dc2626"/><text x="307" y="{legend_y:.2f}">85–100%</text>'
        f'<text x="405" y="{legend_y:.2f}" fill="#475569">Blocks mark redacted locations</text></g>'
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="612" height="{height}" '
        f'viewBox="0 0 612 {height}">{page_rects}{"".join(shapes)}{legend}</svg>'
    )
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@router.get("/{job_id}/preview", response_model=PreviewResponse)
async def redaction_output_preview(
    job_id: str,
    response: Response,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreviewResponse:
    """Build a bounded preview from the actual generated redacted file."""

    job = await _owned_job(job_id, current_user.id)
    if job.status not in {JobStatus.COMPLETE, JobStatus.QA_FAILED}:
        raise HTTPException(status_code=409, detail="Redacted output preview is not ready")
    document = await UploadedDocument.get(job.document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    output = ensure_within_root(output_path_for(document, job.id), settings.temp_job_dir)
    if not output.is_file():
        raise HTTPException(status_code=410, detail="Redacted output has expired")
    try:
        preview = await asyncio.to_thread(build_preview, output, FileType(document.file_type))
    except PreviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return preview


@router.get("/{job_id}/preview/page/{page_number}")
async def redaction_output_preview_page(
    job_id: str,
    page_number: int,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Return a readable page/frame from the actual generated redacted output."""

    job = await _owned_job(job_id, current_user.id)
    if job.status not in {JobStatus.COMPLETE, JobStatus.QA_FAILED}:
        raise HTTPException(status_code=409, detail="Redacted output preview is not ready")
    document = await UploadedDocument.get(job.document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    output = ensure_within_root(output_path_for(document, job.id), settings.temp_job_dir)
    if not output.is_file():
        raise HTTPException(status_code=410, detail="Redacted output has expired")
    try:
        image = await asyncio.to_thread(
            render_preview_page, output, FileType(document.file_type), page_number
        )
    except PreviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        image,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{document_id}/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    document_id: str, payload: FeedbackRequest, current_user: CurrentUser
) -> dict[str, PydanticObjectId]:
    if current_user.id is None or not PydanticObjectId.is_valid(document_id):
        raise HTTPException(404, "Document not found")
    job = await RedactionJob.find_one(
        RedactionJob.id == payload.job_id,
        RedactionJob.document_id == PydanticObjectId(document_id),
        RedactionJob.owner_id == current_user.id,
    )
    if job is None:
        raise HTTPException(404, "Redaction job not found")
    entity = None
    if payload.entity_id is not None:
        entity = await RedactionEntity.find_one(
            RedactionEntity.id == payload.entity_id, RedactionEntity.job_id == job.id
        )
        if entity is None:
            raise HTTPException(404, "Redaction entity not found")
    elif payload.verdict != FeedbackVerdict.MISSED:
        raise HTTPException(422, "entity_id is required unless reporting a missed entity")
    feedback = Feedback(
        job_id=job.id, entity_id=payload.entity_id, user_id=current_user.id,
        verdict=payload.verdict, note=payload.note,
        entity_type=entity.entity_type if entity else payload.entity_type,
        page_number=entity.page_number if entity else payload.page_number,
        bbox=entity.bbox if entity else payload.bbox,
    )
    await feedback.insert()
    await append_audit_event(
        job.document_id, "feedback_recorded",
        {"verdict": payload.verdict.value, "has_entity_reference": payload.entity_id is not None},
        job_id=job.id,
    )
    return {"feedback_id": feedback.id}


@router.post("/compare-modes")
async def compare_modes(
    payload: ModeComparisonRequest,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    if current_user.id is None:
        raise HTTPException(401, "Could not validate credentials")
    document = await UploadedDocument.find_one(
        UploadedDocument.id == payload.document_id, UploadedDocument.owner_id == current_user.id
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    result: dict[str, dict[str, object]] = {}
    for mode in payload.modes:
        job = await RedactionJob.find(
            RedactionJob.document_id == document.id,
            RedactionJob.owner_id == current_user.id,
            RedactionJob.privacy_mode == mode,
            RedactionJob.status == JobStatus.COMPLETE,
        ).sort(-RedactionJob.completed_at).first_or_none()
        if job is None:
            job = RedactionJob(
                document_id=document.id, owner_id=current_user.id,
                privacy_mode=mode, status=JobStatus.QUEUED,
            )
            await job.insert()
            await process_redaction_job(job.id, settings)
            job = await RedactionJob.get(job.id)
            if job is None or job.status != JobStatus.COMPLETE:
                raise HTTPException(422, f"The {mode.value} comparison run did not pass processing and QA")
        entities = await RedactionEntity.find(RedactionEntity.job_id == job.id).to_list()
        counts: dict[str, int] = {}
        for entity in entities:
            if entity.was_redacted:
                counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
        result[mode.value] = {"job_id": str(job.id), "redacted_count": sum(counts.values()),
                              "entity_type_counts": counts}
    baseline = payload.modes[0].value
    diffs = {
        mode: int(data["redacted_count"]) - int(result[baseline]["redacted_count"])
        for mode, data in result.items() if mode != baseline
    }
    return {"document_id": str(document.id), "baseline_mode": baseline,
            "modes": result, "redacted_count_difference_from_baseline": diffs}


def _heatmap_page_sizes(document: UploadedDocument, job: RedactionJob) -> dict[int, tuple[float, float]]:
    path = output_path_for(document, job.id)
    if not path.is_file():
        path = Path(document.temp_job_path)
    try:
        if document.file_type == "pdf":
            import fitz
            with fitz.open(path) as pdf:
                return {index + 1: (page.rect.width, page.rect.height) for index, page in enumerate(pdf)}
        if document.file_type in {"jpeg", "png", "tiff"}:
            from PIL import Image
            with Image.open(path) as image:
                return {index + 1: tuple(map(float, image.size)) for index in range(getattr(image, "n_frames", 1))}
    except Exception:
        pass
    return {1: (612.0, 792.0)}


@router.get("/{job_id}/download")
async def download_redaction(
    job_id: str,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    job = await _owned_job(job_id, current_user.id)
    if job.status != JobStatus.COMPLETE:
        raise HTTPException(status_code=409, detail="Redacted output is not available")
    document = await UploadedDocument.get(job.document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    output = ensure_within_root(output_path_for(document, job.id), settings.temp_job_dir)
    if not output.is_file():
        raise HTTPException(status_code=410, detail="Redacted output has expired")
    await append_audit_event(
        document.id, "redacted_output_downloaded", {"session_export": True}, job_id=job.id
    )
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "tiff": "image/tiff",
        "dicom": "application/dicom",
        "eml": "message/rfc822",
        "mbox": "application/mbox",
    }
    return FileResponse(
        output,
        media_type=media_types[document.file_type],
        filename=f"redacted_{document.original_filename}",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
