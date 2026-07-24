"""Irreversible PDF text/image redaction with visible replacement labels."""

from __future__ import annotations

from pathlib import Path

import fitz

from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.types import ExtractedDocument, LayoutToken


class PdfRedactionError(ValueError):
    pass


def _group_token_rectangles(tokens: list[LayoutToken]) -> list[fitz.Rect]:
    groups: dict[str, list[tuple[float, float, float, float]]] = {}
    for token in tokens:
        if token.bbox is not None:
            groups.setdefault(token.locator or f"token:{token.start}", []).append(token.bbox)
    return [
        fitz.Rect(
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        for boxes in groups.values()
    ]


def _insert_replacement(page: fitz.Page, rectangle: fitz.Rect, text: str) -> None:
    page.draw_rect(rectangle, color=(0, 0, 0), fill=(0, 0, 0), overlay=True)
    font_size = min(9.0, max(3.0, rectangle.height * 0.65))
    while font_size >= 3.0:
        result = page.insert_textbox(
            rectangle,
            text,
            fontsize=font_size,
            fontname="helv",
            color=(1, 1, 1),
            align=fitz.TEXT_ALIGN_CENTER,
            overlay=True,
        )
        if result >= 0:
            return
        font_size -= 0.5
    page.insert_text(
        (rectangle.x0, min(rectangle.y1, rectangle.y0 + 3.0)),
        "[REDACTED]",
        fontsize=3.0,
        color=(1, 1, 1),
        overlay=True,
    )


def redact_pdf(
    source: Path,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
    *,
    verbose_labels: bool = False,
) -> int:
    redactions = [item for item in candidates if item.decision == DetectionDecision.AUTO_REDACT]
    document = fitz.open(source)
    pending: list[tuple[int, fitz.Rect, str]] = []
    try:
        for candidate in redactions:
            candidate_tokens = extracted.tokens_for(candidate)
            if not any(token.page_number is not None and token.bbox is not None for token in candidate_tokens):
                raise PdfRedactionError("Detected span could not be mapped safely to PDF content")
            by_page: dict[int, list[LayoutToken]] = {}
            for token in candidate_tokens:
                if token.page_number is not None and token.bbox is not None:
                    by_page.setdefault(token.page_number, []).append(token)
            for page_number, tokens in by_page.items():
                rectangles = _group_token_rectangles(tokens)
                if not rectangles:
                    continue
                page = document.load_page(page_number - 1)
                for rectangle in rectangles:
                    page.add_redact_annot(rectangle, fill=(0, 0, 0), cross_out=False)
                union = fitz.Rect(
                    min(rect.x0 for rect in rectangles),
                    min(rect.y0 for rect in rectangles),
                    max(rect.x1 for rect in rectangles),
                    max(rect.y1 for rect in rectangles),
                )
                label = candidate.replacement_text or (
                    f"[REDACTED: {candidate.entity_type}]" if verbose_labels else "[REDACTED]"
                )
                pending.append((page_number, union, label))

        for page_number in sorted({item[0] for item in pending}):
            document.load_page(page_number - 1).apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_PIXELS,
                graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                text=fitz.PDF_REDACT_TEXT_REMOVE,
            )
        for page_number, rectangle, label in pending:
            _insert_replacement(document.load_page(page_number - 1), rectangle, label)
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(destination, garbage=4, deflate=True, clean=True)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise PdfRedactionError("PDF redaction failed") from exc
    finally:
        document.close()
    return len(redactions)
