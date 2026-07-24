"""Portable, privacy-safe PDF export for redaction reports."""

from __future__ import annotations

from collections import Counter
from datetime import UTC

import fitz

from app.db.models import RedactionEntity, RedactionJob


PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
MARGIN = 42.0
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN)


def _safe(value: object, limit: int = 500) -> str:
    """Keep report strings PDF-safe and bounded; no raw entity values are stored here."""

    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    return " ".join(text.split())[:limit].encode("latin-1", "replace").decode("latin-1")


def _timestamp(value: object) -> str:
    if not hasattr(value, "astimezone"):
        return "Not available"
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _new_page(pdf: fitz.Document, number: int) -> fitz.Page:
    page = pdf.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.draw_rect(fitz.Rect(0, 0, PAGE_WIDTH, 7), color=None, fill=(0.02, 0.55, 0.62))
    page.insert_text(
        (MARGIN, PAGE_HEIGHT - 24),
        f"MedVault redaction report | Page {number}",
        fontsize=8,
        color=(0.3, 0.36, 0.42),
    )
    return page


def _heading(page: fitz.Page, y: float, title: str, subtitle: str | None = None) -> float:
    page.insert_text((MARGIN, y), title, fontsize=19, fontname="hebo", color=(0.04, 0.12, 0.2))
    y += 19
    if subtitle:
        page.insert_text((MARGIN, y), subtitle, fontsize=9, color=(0.3, 0.36, 0.42))
        y += 18
    return y


def _stat_card(page: fitz.Page, x: float, y: float, label: str, value: str, color: tuple[float, float, float]) -> None:
    page.draw_rect(fitz.Rect(x, y, x + 122, y + 62), color=(0.82, 0.86, 0.9), fill=(0.97, 0.99, 1))
    page.draw_rect(fitz.Rect(x, y, x + 5, y + 62), color=None, fill=color)
    page.insert_text((x + 14, y + 21), label, fontsize=8, color=(0.3, 0.36, 0.42))
    page.insert_text((x + 14, y + 46), value, fontsize=19, fontname="hebo", color=(0.04, 0.12, 0.2))


def _bar_chart(page: fitz.Page, y: float, counts: Counter[str]) -> float:
    page.insert_text((MARGIN, y), "Top entity categories", fontsize=12, fontname="hebo", color=(0.04, 0.12, 0.2))
    y += 14
    if not counts:
        page.insert_text((MARGIN, y + 14), "No detected entities were available for charting.", fontsize=9)
        return y + 34
    top = counts.most_common(8)
    maximum = max(counts.values())
    for category, count in top:
        y += 20
        page.insert_text((MARGIN, y + 10), _safe(category, 25), fontsize=8, color=(0.18, 0.24, 0.3))
        bar_x = MARGIN + 145
        width = 270 * (count / maximum)
        page.draw_rect(fitz.Rect(bar_x, y, bar_x + width, y + 12), color=None, fill=(0.02, 0.55, 0.62))
        page.insert_text((bar_x + width + 8, y + 10), str(count), fontsize=8, color=(0.18, 0.24, 0.3))
    return y + 28


def build_report_pdf(job: RedactionJob, entities: list[RedactionEntity]) -> bytes:
    """Build a self-contained PDF summary with charts and every safe entity-report field."""

    pdf = fitz.open()
    redacted = [entity for entity in entities if entity.was_redacted]
    reviewed = [entity for entity in entities if not entity.was_redacted]
    categories = Counter(entity.entity_type for entity in entities)
    page = _new_page(pdf, 1)
    y = _heading(page, 48, "MedVault Redaction Report", "Privacy-safe export; original values are never included.")
    page.insert_text((MARGIN, y), f"Job ID: {_safe(job.id)}", fontsize=8, color=(0.3, 0.36, 0.42))
    y += 14
    page.insert_text((MARGIN, y), f"Mode: {_safe(job.privacy_mode.value)}", fontsize=9, fontname="hebo")
    page.insert_text((MARGIN + 180, y), f"Status: {_safe(job.status.value)}", fontsize=9, fontname="hebo")
    page.insert_text((MARGIN + 330, y), f"Created: {_timestamp(job.created_at)}", fontsize=8)
    y += 26

    _stat_card(page, MARGIN, y, "Entities detected", str(len(entities)), (0.02, 0.55, 0.62))
    _stat_card(page, MARGIN + 132, y, "Redacted", str(len(redacted)), (0.0, 0.47, 0.31))
    _stat_card(page, MARGIN + 264, y, "Reviewed, kept", str(len(reviewed)), (0.88, 0.48, 0.04))
    ratio = (len(redacted) / len(entities) * 100) if entities else 100.0
    _stat_card(page, MARGIN + 396, y, "Redaction ratio", f"{ratio:.0f}%", (0.42, 0.25, 0.72))
    y += 88

    page.insert_text((MARGIN, y), "Redaction ratio", fontsize=12, fontname="hebo", color=(0.04, 0.12, 0.2))
    y += 14
    page.draw_rect(fitz.Rect(MARGIN, y, MARGIN + CONTENT_WIDTH, y + 18), color=(0.78, 0.82, 0.86), fill=(0.93, 0.95, 0.97))
    page.draw_rect(
        fitz.Rect(MARGIN, y, MARGIN + (CONTENT_WIDTH * ratio / 100), y + 18),
        color=None,
        fill=(0.02, 0.55, 0.62),
    )
    page.insert_text((MARGIN + 8, y + 13), f"{ratio:.1f}% of detected entities redacted", fontsize=8, color=(1, 1, 1))
    y += 45
    y = _bar_chart(page, y, categories)

    if job.reidentification_risk:
        page.insert_text((MARGIN, y), "Research re-identification assessment", fontsize=12, fontname="hebo")
        y += 16
        page.insert_text((MARGIN, y), f"Risk: {_safe(job.reidentification_risk.value).upper()}", fontsize=9)
        y += 13
        factors = job.reidentification_factors or ["No additional safe factors were recorded."]
        for factor in factors[:8]:
            y += 12
            page.insert_text((MARGIN + 8, y), f"- {_safe(factor, 95)}", fontsize=8, color=(0.3, 0.36, 0.42))

    page_number = 2
    page = _new_page(pdf, page_number)
    y = _heading(page, 48, "Entity findings", "All report entries, without raw source values.")
    headers = [(MARGIN, "Category"), (145, "Status"), (215, "Page"), (252, "Confidence"), (315, "Sources"), (425, "Privilege")]
    for x, title in headers:
        page.insert_text((x, y), title, fontsize=7, fontname="hebo", color=(0.3, 0.36, 0.42))
    y += 8
    page.draw_line((MARGIN, y), (PAGE_WIDTH - MARGIN, y), color=(0.75, 0.8, 0.84))
    y += 16
    for entity in entities:
        if y > PAGE_HEIGHT - 72:
            page_number += 1
            page = _new_page(pdf, page_number)
            y = _heading(page, 48, "Entity findings (continued)")
            for x, title in headers:
                page.insert_text((x, y), title, fontsize=7, fontname="hebo", color=(0.3, 0.36, 0.42))
            y += 16
        status = "Redacted" if entity.was_redacted else "Reviewed"
        page.insert_text((MARGIN, y), _safe(entity.entity_type, 20), fontsize=7)
        page.insert_text((145, y), status, fontsize=7)
        page.insert_text((215, y), str(entity.page_number or "-"), fontsize=7)
        page.insert_text((252, y), f"{entity.confidence * 100:.0f}%", fontsize=7)
        page.insert_text((315, y), _safe(", ".join(entity.detector_source), 22), fontsize=7)
        page.insert_text((425, y), "Yes" if entity.privileged_flag else "No", fontsize=7)
        y += 10
        explanation = _safe(entity.explanation_text, 135)
        page.insert_textbox(
            fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 18),
            f"Why: {explanation}",
            fontsize=6.5,
            color=(0.32, 0.38, 0.44),
        )
        y += 24
        page.draw_line((MARGIN, y), (PAGE_WIDTH - MARGIN, y), color=(0.9, 0.92, 0.94))
        y += 10

    data = pdf.tobytes(garbage=4, deflate=True)
    pdf.close()
    return data
