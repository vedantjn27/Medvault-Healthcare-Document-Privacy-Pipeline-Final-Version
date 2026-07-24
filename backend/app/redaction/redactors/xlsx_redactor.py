"""Exact Excel cell substring replacement while preserving workbook formatting."""

from __future__ import annotations

import copy
import io
from dataclasses import replace
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from PIL import Image, ImageSequence

from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.types import ExtractedDocument, LayoutToken
from app.redaction.redactors.image_redactor import redact_pil_frames


class XlsxRedactionError(ValueError):
    pass


def redact_xlsx(
    source: Path,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
    *,
    verbose_labels: bool = False,
) -> int:
    redactions = [item for item in candidates if item.decision == DetectionDecision.AUTO_REDACT]
    operations: dict[str, list[tuple[int, int, str]]] = {}
    for candidate in sorted(redactions, key=lambda item: item.start, reverse=True):
        candidate_tokens = [
            token
            for token in extracted.tokens_for(candidate)
            if token.source == "xlsx_cell" and token.locator is not None
        ]
        if not candidate_tokens:
            image_tokens = [
                token for token in extracted.tokens_for(candidate)
                if token.source in {"image_ocr", "visual_region"}
                and token.locator and token.locator.startswith("xlsx_image|")
            ]
            if image_tokens:
                continue
            raise XlsxRedactionError("Detected span could not be mapped safely to an Excel cell or image")
        grouped: dict[str, list[LayoutToken]] = {}
        for token in candidate_tokens:
            grouped.setdefault(token.locator, []).append(token)
        first_locator = min(grouped, key=lambda key: min(token.start for token in grouped[key]))
        label = candidate.replacement_text or (
            f"[REDACTED: {candidate.entity_type}]" if verbose_labels else "[REDACTED]"
        )
        for locator, tokens in grouped.items():
            start = min(token.local_start for token in tokens)
            end = max(token.local_end or token.local_start + 1 for token in tokens)
            operations.setdefault(locator, []).append(
                (start, end, label if locator == first_locator else "")
            )

    try:
        workbook = load_workbook(source, read_only=False, data_only=False, keep_links=False)
        for locator, cell_operations in operations.items():
            sheet_name, coordinate = locator.split("|", 1)
            cell = workbook[sheet_name][coordinate]
            if cell.data_type == "f":
                raise XlsxRedactionError("Formula cells cannot be modified by the redaction engine")
            value = str(cell.value)
            for start, end, replacement in sorted(cell_operations, reverse=True):
                value = value[:start] + replacement + value[end:]
            cell.value = value
        for embedded in extracted.metadata.get("embedded_images", []):
            start, end = int(embedded["start"]), int(embedded["end"])
            image_candidates = [
                replace(candidate, start=candidate.start - start, end=candidate.end - start)
                for candidate in redactions
                if candidate.start < end and candidate.end > start
                and any(
                    token.locator and token.locator.startswith(str(embedded["locator"]))
                    for token in extracted.tokens_for(candidate)
                )
            ]
            if not image_candidates:
                continue
            worksheet = workbook[str(embedded["sheet_name"])]
            image_index = int(embedded["image_index"])
            if image_index >= len(worksheet._images):
                raise XlsxRedactionError("Embedded image mapping changed during workbook processing")
            drawing_image = worksheet._images[image_index]
            try:
                image_bytes = drawing_image._data()
                with Image.open(io.BytesIO(image_bytes)) as source_image:
                    frames = [frame.copy() for frame in ImageSequence.Iterator(source_image)]
                redacted_frames = redact_pil_frames(
                    frames, embedded["extracted"], image_candidates
                )
                if len(redacted_frames) != 1:
                    raise XlsxRedactionError("Animated embedded workbook images are not supported")
                buffer = io.BytesIO()
                redacted_frames[0].save(buffer, format="PNG")
                buffer.seek(0)
                replacement_image = OpenpyxlImage(buffer)
                replacement_image.anchor = copy.deepcopy(drawing_image.anchor)
                replacement_image.width = drawing_image.width
                replacement_image.height = drawing_image.height
                worksheet._images[image_index] = replacement_image
            except XlsxRedactionError:
                raise
            except Exception as exc:
                raise XlsxRedactionError("Embedded workbook image redaction failed") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(destination)
        workbook.close()
    except Exception as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, XlsxRedactionError):
            raise
        raise XlsxRedactionError("Excel redaction failed") from exc
    return len(redactions)
