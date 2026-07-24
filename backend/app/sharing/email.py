"""Privacy-safe secure-share email delivery."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import Settings


def smtp_available(settings: Settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def send_share_link(recipient: str, share_url: str, expires_at: str, settings: Settings) -> None:
    """Send only the controlled link and its expiry; never document names or PHI."""

    message = EmailMessage()
    message["Subject"] = "MedVault secure document share"
    message["From"] = str(settings.smtp_from_email)
    message["To"] = recipient
    message.set_content(
        "A MedVault redacted document has been shared with you.\n\n"
        f"Open secure share: {share_url}\n"
        f"Expires: {expires_at}\n\n"
        "This link is access-controlled. The email does not contain document contents."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_pass:
            server.login(settings.smtp_user, settings.smtp_pass.get_secret_value())
        server.send_message(message)
