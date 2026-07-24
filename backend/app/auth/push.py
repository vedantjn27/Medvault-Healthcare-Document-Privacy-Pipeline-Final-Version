"""Web Push delivery with privacy-safe SMTP fallback."""

from __future__ import annotations

import asyncio
import json
import smtplib
from email.message import EmailMessage

from pywebpush import WebPushException, webpush

from app.config import Settings
from app.db.models import RedactionJob, User


async def notify_job_finished(user: User, job: RedactionJob, settings: Settings) -> bool:
    payload = json.dumps({
        "title": "MedVault job finished", "job_id": str(job.id),
        "status": job.status.value,
    })
    if user.push_subscription and _push_configured(settings):
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=user.push_subscription.model_dump(),
                data=payload,
                vapid_private_key=settings.vapid_private_key.get_secret_value(),
                vapid_claims={"sub": settings.vapid_subject},
            )
            return True
        except WebPushException:
            pass
    if _smtp_configured(settings):
        await asyncio.to_thread(_send_email, str(user.email), str(job.id), job.status.value, settings)
        return True
    return False


def _push_configured(settings: Settings) -> bool:
    return bool(settings.vapid_private_key and settings.vapid_subject)


def _smtp_configured(settings: Settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def _send_email(recipient: str, job_id: str, status: str, settings: Settings) -> None:
    message = EmailMessage()
    message["Subject"] = "MedVault redaction job finished"
    message["From"] = str(settings.smtp_from_email)
    message["To"] = recipient
    message.set_content(f"Your MedVault job {job_id} finished with status: {status}.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_pass:
            server.login(settings.smtp_user, settings.smtp_pass.get_secret_value())
        server.send_message(message)
