"""MongoDB-backed in-process batch runner with per-file isolation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from beanie import PydanticObjectId

from app.config import Settings
from app.db.models import BatchJob, JobStatus, RedactionJob, utc_now
from app.redaction.pipeline import process_redaction_job


_batch_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def process_batch(batch_id: PydanticObjectId, settings: Settings) -> None:
    async with _batch_locks[str(batch_id)]:
        batch = await BatchJob.get(batch_id)
        if batch is None or batch.status == JobStatus.COMPLETE:
            return
        batch.status = JobStatus.PROCESSING
        await batch.save()
        for index, item in enumerate(batch.items):
            if item.status in {JobStatus.COMPLETE, JobStatus.QA_FAILED, JobStatus.ERROR}:
                continue
            if item.redaction_job_id is None:
                item.status = JobStatus.ERROR
                item.error_message = "Redaction job was not created"
            else:
                try:
                    existing = await RedactionJob.get(item.redaction_job_id)
                    if existing and existing.status not in {JobStatus.COMPLETE, JobStatus.QA_FAILED}:
                        await process_redaction_job(item.redaction_job_id, settings)
                    job = await RedactionJob.get(item.redaction_job_id)
                    item.status = job.status if job else JobStatus.ERROR
                    item.error_message = job.error_message if job else "Redaction job metadata is unavailable"
                except Exception as exc:
                    item.status = JobStatus.ERROR
                    item.error_message = f"Batch item failed ({type(exc).__name__})"
            batch.items[index] = item
            await batch.save()
        batch.status = JobStatus.COMPLETE
        batch.completed_at = utc_now()
        await batch.save()


async def batch_worker(settings: Settings, stop_event: asyncio.Event) -> None:
    """Resume queued or interrupted batches from MongoDB until shutdown."""

    while not stop_event.is_set():
        queued = await BatchJob.find(
            {"status": {"$in": [JobStatus.QUEUED.value, JobStatus.PROCESSING.value]}}
        ).to_list()
        for batch in queued:
            await process_batch(batch.id, settings)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2.0)
        except TimeoutError:
            continue
