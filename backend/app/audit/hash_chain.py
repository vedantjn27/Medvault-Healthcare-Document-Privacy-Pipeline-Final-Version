"""Canonical append-only audit hash-chain creation and verification."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from beanie import PydanticObjectId

from app.db.models import AuditLog
from pymongo.errors import DuplicateKeyError


_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _canonical(document_id, job_id, event_type: str, event_data: dict[str, Any], previous: str | None, sequence: int) -> str:
    payload = {
        "document_id": str(document_id), "job_id": str(job_id) if job_id else None,
        "event_type": event_type, "event_data": event_data, "sequence": sequence,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(((previous or "") + encoded).encode("utf-8")).hexdigest()


async def append_audit_event(
    document_id: PydanticObjectId,
    event_type: str,
    event_data: dict[str, Any],
    *,
    job_id: PydanticObjectId | None = None,
) -> AuditLog:
    async with _locks[str(document_id)]:
        for _ in range(8):
            previous = await AuditLog.find(AuditLog.document_id == document_id).sort(-AuditLog.sequence).first_or_none()
            previous_hash = previous.entry_hash if previous else None
            sequence = (previous.sequence + 1) if previous else 1
            entry = AuditLog(
                document_id=document_id, job_id=job_id, event_type=event_type,
                event_data=event_data, sequence=sequence,
                entry_hash=_canonical(document_id, job_id, event_type, event_data, previous_hash, sequence),
                previous_hash=previous_hash,
            )
            try:
                await entry.insert()
                return entry
            except DuplicateKeyError:
                continue
        raise RuntimeError("Could not append audit entry after concurrent writes")


@dataclass(frozen=True, slots=True)
class ChainVerification:
    valid: bool
    entries_checked: int
    broken_entry_id: str | None = None


async def verify_audit_chain(document_id: PydanticObjectId) -> ChainVerification:
    entries = await AuditLog.find(AuditLog.document_id == document_id).sort(AuditLog.sequence).to_list()
    previous: str | None = None
    for entry in entries:
        expected = _canonical(entry.document_id, entry.job_id, entry.event_type, entry.event_data, previous, entry.sequence)
        if entry.previous_hash != previous or entry.entry_hash != expected:
            return ChainVerification(False, len(entries), str(entry.id))
        previous = entry.entry_hash
    return ChainVerification(True, len(entries))
