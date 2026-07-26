"""Secure document upload, metadata, and auth-gated preview routes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict

from app.auth.jwt import CurrentUser
from app.config import Settings, get_settings
from app.db.models import DocumentStatus, UploadedDocument, User, utc_now
from app.documents.file_types import FileType, InvalidDocumentError, classify_document
from app.documents.preview import PreviewError, PreviewResponse, build_preview, render_preview_page
from app.storage.temp_manager import (
    EmptyUploadError,
    StorageError,
    UploadTooLargeError,
    create_document_directory,
    delete_document_directory,
    ensure_within_root,
    sanitize_filename,
    store_upload,
)
from app.audit.hash_chain import append_audit_event


router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    original_filename: str
    file_type: FileType
    size_bytes: int | None = None
    uploaded_at: datetime
    status: DocumentStatus
    expires_at: datetime


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def _owned_document(document_id: str, current_user: User) -> UploadedDocument:
    if not PydanticObjectId.is_valid(document_id) or current_user.id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document = await UploadedDocument.find_one(
        UploadedDocument.id == PydanticObjectId(document_id),
        UploadedDocument.owner_id == current_user.id,
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


async def _ensure_available(document: UploadedDocument, settings: Settings) -> Path:
    expired = _aware_utc(document.expires_at) <= utc_now()
    try:
        path = ensure_within_root(Path(document.temp_job_path), settings.temp_job_dir)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail="Stored document path is invalid") from exc
    if expired or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Document temporary data has expired",
        )
    return path


def _resolved_document_path(document: UploadedDocument, settings: Settings) -> Path:
    try:
        return ensure_within_root(Path(document.temp_job_path), settings.temp_job_dir)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail="Stored document path is invalid") from exc


def _document_response(document: UploadedDocument, path: Path | None = None) -> DocumentResponse:
    size = path.stat().st_size if path is not None and path.is_file() else None
    return DocumentResponse(
        id=document.id,
        original_filename=document.original_filename,
        file_type=FileType(document.file_type),
        size_bytes=size,
        uploaded_at=document.uploaded_at,
        status=document.status,
        expires_at=document.expires_at,
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File(description="Supported healthcare document")],
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    if not file.filename:
        await file.close()
        raise HTTPException(status_code=400, detail="A filename is required")

    document_id = PydanticObjectId()
    safe_name = sanitize_filename(file.filename)
    directory = create_document_directory(settings.temp_job_dir, str(document_id))
    destination = directory / safe_name
    try:
        stored = await store_upload(file, destination, settings.effective_max_upload_size_bytes)
        file_type = await asyncio.to_thread(classify_document, stored.path, safe_name)
        now = utc_now()
        document = UploadedDocument(
            id=document_id,
            owner_id=current_user.id,
            original_filename=safe_name,
            file_type=file_type.value,
            uploaded_at=now,
            status=DocumentStatus.UPLOADED,
            temp_job_path=str(stored.path.resolve()),
            expires_at=now + timedelta(seconds=settings.temp_job_ttl_seconds),
        )
        await document.insert()
        await append_audit_event(
            document.id, "document_uploaded",
            {"file_type": document.file_type, "size_bytes": stored.size_bytes},
        )
    except UploadTooLargeError as exc:
        delete_document_directory(directory, settings.temp_job_dir)
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except EmptyUploadError as exc:
        delete_document_directory(directory, settings.temp_job_dir)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidDocumentError as exc:
        delete_document_directory(directory, settings.temp_job_dir)
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception:
        delete_document_directory(directory, settings.temp_job_dir)
        raise

    return _document_response(document, stored.path)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:
    document = await _owned_document(document_id, current_user)
    path = _resolved_document_path(document, settings)
    if _aware_utc(document.expires_at) <= utc_now() or not path.is_file():
        document.status = DocumentStatus.EXPIRED
        return _document_response(document)
    return _document_response(document, path)


@router.get("/{document_id}/preview", response_model=PreviewResponse)
async def preview_document(
    document_id: str,
    response: Response,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreviewResponse:
    document = await _owned_document(document_id, current_user)
    path = await _ensure_available(document, settings)
    try:
        preview = await asyncio.to_thread(build_preview, path, FileType(document.file_type))
    except PreviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return preview


@router.get("/{document_id}/preview/page/{page_number}")
async def preview_document_page(
    document_id: str,
    page_number: int,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Return an authenticated, readable PNG for one preview page or image frame."""

    document = await _owned_document(document_id, current_user)
    path = await _ensure_available(document, settings)
    try:
        image = await asyncio.to_thread(
            render_preview_page, path, FileType(document.file_type), page_number
        )
    except PreviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        image,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0", "X-Content-Type-Options": "nosniff"},
    )
