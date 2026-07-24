"""Secure, revocable, password-capable redacted-file sharing routes."""

from __future__ import annotations

import hashlib
import secrets
import asyncio
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.audit.hash_chain import append_audit_event
from app.auth.jwt import CurrentUser, hash_password, verify_password
from app.config import Settings, get_settings
from app.db.models import JobStatus, RedactionJob, ReviewStatus, ShareAccess, ShareLink, ShareRole, UploadedDocument, utc_now
from app.redaction.pipeline import output_path_for
from app.sharing.email import send_share_link, smtp_available
from app.storage.temp_manager import ensure_within_root


router = APIRouter(prefix="/shares", tags=["secure sharing"])


class ShareCreateRequest(BaseModel):
    role: ShareRole = ShareRole.RECIPIENT
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    password: str | None = Field(default=None, min_length=10, max_length=128)
    recipient_email: EmailStr | None = None
    allow_download: bool = True
    max_accesses: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def reviewer_cannot_download(self) -> "ShareCreateRequest":
        if self.role == ShareRole.REVIEWER:
            self.allow_download = False
        return self


class ShareResponse(BaseModel):
    id: PydanticObjectId
    job_id: PydanticObjectId
    role: ShareRole
    recipient_email: EmailStr | None
    allow_download: bool
    max_accesses: int | None
    access_count: int
    revoked_at: datetime | None
    created_at: datetime
    expires_at: datetime
    share_url: str | None = None


class PublicShareRequest(BaseModel):
    password: str | None = Field(default=None, max_length=128)


class PublicShareResponse(BaseModel):
    filename: str
    file_type: str
    role: ShareRole
    allow_download: bool
    expires_at: datetime
    access_count: int
    max_accesses: int | None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _response(link: ShareLink, token: str | None = None) -> ShareResponse:
    return ShareResponse(
        id=link.id, job_id=link.job_id, role=link.role, recipient_email=link.recipient_email,
        allow_download=link.allow_download, max_accesses=link.max_accesses, access_count=link.access_count,
        revoked_at=link.revoked_at, created_at=link.created_at, expires_at=link.expires_at,
        share_url=f"/share/{token}" if token else None,
    )


async def _owned_job(job_id: str, current_user: CurrentUser) -> RedactionJob:
    if current_user.id is None or not PydanticObjectId.is_valid(job_id):
        raise HTTPException(404, "Redaction job not found")
    job = await RedactionJob.find_one(RedactionJob.id == PydanticObjectId(job_id), RedactionJob.owner_id == current_user.id)
    if job is None:
        raise HTTPException(404, "Redaction job not found")
    return job


@router.post("/{job_id}", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    job_id: str,
    payload: ShareCreateRequest,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ShareResponse:
    job = await _owned_job(job_id, current_user)
    if job.status != JobStatus.COMPLETE or not job.qa_passed:
        raise HTTPException(409, "Only QA-passed outputs can be shared")
    if job.review_status != ReviewStatus.APPROVED:
        raise HTTPException(409, "Approve the human review queue before creating a share link")
    token = secrets.token_urlsafe(32)
    link = ShareLink(
        job_id=job.id, document_id=job.document_id, owner_id=current_user.id,
        token_hash=_token_hash(token), role=payload.role, recipient_email=payload.recipient_email,
        password_hash=hash_password(payload.password) if payload.password else None,
        allow_download=payload.allow_download, max_accesses=payload.max_accesses,
        expires_at=utc_now() + timedelta(hours=payload.expires_in_hours),
    )
    await link.insert()
    if payload.recipient_email:
        if not smtp_available(settings):
            await link.delete()
            raise HTTPException(503, "Email delivery is unavailable because SMTP is not configured")
        share_url = f"{settings.frontend_public_url}/share/{token}"
        try:
            await asyncio.to_thread(
                send_share_link,
                str(payload.recipient_email),
                share_url,
                link.expires_at.isoformat(),
                settings,
            )
        except (OSError, smtplib.SMTPException) as exc:
            await link.delete()
            raise HTTPException(502, "Secure-share email could not be delivered; no link was created") from exc
    await append_audit_event(job.document_id, "secure_share_created", {"role": link.role.value, "password_protected": bool(link.password_hash), "allow_download": link.allow_download}, job_id=job.id)
    return _response(link, token)


@router.get("/{job_id}", response_model=list[ShareResponse])
async def list_shares(job_id: str, current_user: CurrentUser) -> list[ShareResponse]:
    job = await _owned_job(job_id, current_user)
    links = await ShareLink.find(ShareLink.job_id == job.id).sort(-ShareLink.created_at).to_list()
    return [_response(link) for link in links]


@router.post("/{share_id}/revoke", response_model=ShareResponse)
async def revoke_share(share_id: str, current_user: CurrentUser) -> ShareResponse:
    if current_user.id is None or not PydanticObjectId.is_valid(share_id):
        raise HTTPException(404, "Share link not found")
    link = await ShareLink.find_one(ShareLink.id == PydanticObjectId(share_id), ShareLink.owner_id == current_user.id)
    if link is None:
        raise HTTPException(404, "Share link not found")
    link.revoked_at = utc_now()
    await link.save()
    await append_audit_event(link.document_id, "secure_share_revoked", {"share_id": str(link.id)}, job_id=link.job_id)
    return _response(link)


async def _public_link(token: str, password: str | None) -> tuple[ShareLink, RedactionJob, UploadedDocument]:
    link = await ShareLink.find_one(ShareLink.token_hash == _token_hash(token))
    now = utc_now()
    if link is None or link.revoked_at is not None or link.expires_at <= now:
        raise HTTPException(404, "Share link is unavailable")
    if link.max_accesses is not None and link.access_count >= link.max_accesses:
        raise HTTPException(410, "Share link access limit reached")
    if link.password_hash and not verify_password(password or "", link.password_hash):
        raise HTTPException(401, "Invalid share password")
    job = await RedactionJob.get(link.job_id)
    document = await UploadedDocument.get(link.document_id)
    if job is None or document is None or job.status != JobStatus.COMPLETE or not job.qa_passed:
        raise HTTPException(410, "Shared output is no longer available")
    return link, job, document


@router.post("/public/{token}", response_model=PublicShareResponse)
async def read_public_share(token: str, payload: PublicShareRequest) -> PublicShareResponse:
    link, _, document = await _public_link(token, payload.password)
    return PublicShareResponse(filename=document.original_filename, file_type=document.file_type, role=link.role, allow_download=link.allow_download, expires_at=link.expires_at, access_count=link.access_count, max_accesses=link.max_accesses)


@router.post("/public/{token}/download")
async def download_public_share(
    token: str,
    payload: PublicShareRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    link, job, document = await _public_link(token, payload.password)
    if not link.allow_download:
        raise HTTPException(403, "This share is review-only")
    path = ensure_within_root(output_path_for(document, job.id), settings.temp_job_dir)
    if not path.is_file():
        raise HTTPException(410, "Shared output has expired")
    link.access_count += 1
    await link.save()
    await ShareAccess(share_link_id=link.id, action="download").insert()
    await append_audit_event(link.document_id, "secure_share_downloaded", {"share_id": str(link.id), "role": link.role.value, "access_count": link.access_count}, job_id=job.id)
    return FileResponse(path, media_type="application/octet-stream", filename=f"redacted_{document.original_filename}", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
