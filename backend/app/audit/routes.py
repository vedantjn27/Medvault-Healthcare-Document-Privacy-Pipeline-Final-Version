"""Audit trail retrieval and integrity-verification routes."""

from __future__ import annotations

from datetime import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.audit.hash_chain import verify_audit_chain
from app.auth.jwt import CurrentUser
from app.db.models import AuditLog, UploadedDocument


router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEntryResponse(BaseModel):
    id: PydanticObjectId
    job_id: PydanticObjectId | None
    event_type: str
    event_data: dict[str, object]
    entry_hash: str
    previous_hash: str | None
    sequence: int
    created_at: datetime


async def _owned(document_id: str, user: CurrentUser) -> UploadedDocument:
    if user.id is None or not PydanticObjectId.is_valid(document_id):
        raise HTTPException(404, "Document not found")
    document = await UploadedDocument.find_one(
        UploadedDocument.id == PydanticObjectId(document_id), UploadedDocument.owner_id == user.id
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.get("/{document_id}", response_model=list[AuditEntryResponse])
async def audit_trail(document_id: str, current_user: CurrentUser):
    document = await _owned(document_id, current_user)
    return await AuditLog.find(AuditLog.document_id == document.id).sort(AuditLog.sequence).to_list()


@router.get("/verify/{document_id}")
async def verify(document_id: str, current_user: CurrentUser):
    document = await _owned(document_id, current_user)
    result = await verify_audit_chain(document.id)
    return {"valid": result.valid, "entries_checked": result.entries_checked,
            "broken_entry_id": result.broken_entry_id}
