"""Batch upload, status, and archive-download routes."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from zipfile import ZIP_DEFLATED, ZipFile

from beanie import PydanticObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from pymongo.errors import DuplicateKeyError
from starlette.background import BackgroundTask

from app.auth.jwt import CurrentUser
from app.batch.job_runner import process_batch
from app.config import Settings, get_settings
from app.db.models import (
    BatchItem,
    BatchJob,
    DocumentStatus,
    JobStatus,
    PrivacyMode,
    RedactionJob,
    UploadedDocument,
    utc_now,
)
from app.documents.file_types import classify_document
from app.redaction.pipeline import output_path_for
from app.storage.temp_manager import (
    create_document_directory,
    delete_document_directory,
    sanitize_filename,
    store_upload,
)
from app.audit.hash_chain import append_audit_event


router = APIRouter(prefix="/batch", tags=["batch"])


class BatchItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: PydanticObjectId
    redaction_job_id: PydanticObjectId | None
    status: JobStatus
    error_message: str | None


class BatchResponse(BaseModel):
    batch_job_id: PydanticObjectId
    status: JobStatus
    items: list[BatchItemResponse]


async def _owned(batch_id: str, user: CurrentUser) -> BatchJob:
    if user.id is None or not PydanticObjectId.is_valid(batch_id):
        raise HTTPException(404, "Batch job not found")
    batch = await BatchJob.find_one(BatchJob.id == PydanticObjectId(batch_id), BatchJob.owner_id == user.id)
    if batch is None:
        raise HTTPException(404, "Batch job not found")
    return batch


def _response(batch: BatchJob) -> BatchResponse:
    return BatchResponse(batch_job_id=batch.id, status=batch.status, items=[BatchItemResponse.model_validate(i) for i in batch.items])


@router.post("/upload", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    files: Annotated[list[UploadFile], File()],
    privacy_mode: Annotated[PrivacyMode, Form()],
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=128)
    ] = None,
) -> BatchResponse:
    if current_user.id is None:
        raise HTTPException(401, "Could not validate credentials")
    if idempotency_key:
        existing = await BatchJob.find_one(
            BatchJob.owner_id == current_user.id,
            BatchJob.idempotency_key == idempotency_key,
        )
        if existing is not None:
            return _response(existing)
    if not files or len(files) > settings.max_batch_files:
        raise HTTPException(422, f"Batch must contain 1 to {settings.max_batch_files} files")
    if privacy_mode == PrivacyMode.CUSTOM:
        raise HTTPException(422, "Custom mode is not supported for batch processing")
    items: list[BatchItem] = []
    for upload in files:
        document_id = PydanticObjectId()
        directory = create_document_directory(settings.temp_job_dir, str(document_id))
        safe_name = sanitize_filename(upload.filename)
        try:
            stored = await store_upload(upload, directory / safe_name, settings.max_upload_size_bytes)
            file_type = await asyncio.to_thread(classify_document, stored.path, safe_name)
            now = utc_now()
            document = UploadedDocument(
                id=document_id, owner_id=current_user.id, original_filename=safe_name,
                file_type=file_type.value, status=DocumentStatus.UPLOADED,
                temp_job_path=str(stored.path.resolve()),
                expires_at=now + timedelta(seconds=settings.temp_job_ttl_seconds),
            )
            await document.insert()
            await append_audit_event(
                document.id, "document_uploaded",
                {"file_type": document.file_type, "size_bytes": stored.size_bytes, "batch": True},
            )
            job = RedactionJob(document_id=document.id, owner_id=current_user.id, privacy_mode=privacy_mode)
            await job.insert()
            items.append(BatchItem(document_id=document.id, redaction_job_id=job.id))
        except Exception as exc:
            delete_document_directory(directory, settings.temp_job_dir)
            items.append(BatchItem(document_id=document_id, status=JobStatus.ERROR,
                                   error_message=f"Upload rejected ({type(exc).__name__})"))
    batch = BatchJob(owner_id=current_user.id, items=items, idempotency_key=idempotency_key)
    try:
        await batch.insert()
    except DuplicateKeyError:
        existing = await BatchJob.find_one(
            BatchJob.owner_id == current_user.id,
            BatchJob.idempotency_key == idempotency_key,
        )
        if existing is None:
            raise
        return _response(existing)
    background_tasks.add_task(process_batch, batch.id, settings)
    return _response(batch)


@router.get("/{batch_id}/status", response_model=BatchResponse)
async def batch_status(batch_id: str, current_user: CurrentUser) -> BatchResponse:
    return _response(await _owned(batch_id, current_user))


def _cleanup(paths: list[Path], root: Path) -> None:
    for path in paths:
        if path.exists():
            delete_document_directory(path, root)


@router.get("/{batch_id}/download")
async def batch_download(batch_id: str, current_user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]):
    batch = await _owned(batch_id, current_user)
    if batch.status != JobStatus.COMPLETE:
        raise HTTPException(409, "Batch output is not ready")
    claimed_at = utc_now()
    claim = await BatchJob.find_one(
        BatchJob.id == batch.id,
        BatchJob.owner_id == current_user.id,
        BatchJob.downloaded_at == None,  # noqa: E711
    ).update({"$set": {"downloaded_at": claimed_at}})
    if claim.modified_count != 1:
        raise HTTPException(410, "Batch output has expired or was already downloaded")
    archive_dir = settings.temp_job_dir / f"batch-{batch.id}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / "medvault_batch.zip"
    report = {"batch_job_id": str(batch.id), "items": []}
    cleanup_dirs: list[Path] = [archive_dir]
    try:
        with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
            for item in batch.items:
                document = await UploadedDocument.get(item.document_id)
                job = await RedactionJob.get(item.redaction_job_id) if item.redaction_job_id else None
                record = {"document_id": str(item.document_id), "status": item.status.value,
                          "error_message": item.error_message}
                report["items"].append(record)
                if document:
                    cleanup_dirs.append(Path(document.temp_job_path).parent)
                if document and job and job.status == JobStatus.COMPLETE:
                    output = output_path_for(document, job.id)
                    if output.is_file():
                        bundle.write(
                            output,
                            arcname=f"redacted/{str(document.id)[:8]}_{document.original_filename}",
                        )
            bundle.writestr("compliance_report.json", json.dumps(report, indent=2))
    except Exception:
        await BatchJob.find_one(
            BatchJob.id == batch.id,
            BatchJob.downloaded_at == claimed_at,
        ).update({"$set": {"downloaded_at": None}})
        _cleanup([archive_dir], settings.temp_job_dir)
        raise
    return FileResponse(archive, media_type="application/zip", filename="medvault_batch.zip",
                        headers={"Cache-Control": "no-store"},
                        background=BackgroundTask(_cleanup, cleanup_dirs, settings.temp_job_dir))
