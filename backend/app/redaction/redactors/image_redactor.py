"""True raster-pixel overwrite for OCR, face, and barcode regions."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.types import ExtractedDocument, LayoutToken


class ImageRedactionError(ValueError):
    pass


def redact_pil_frames(
    frames: list[Image.Image],
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
) -> list[Image.Image]:
    output = [frame.convert("RGB") for frame in frames]
    for candidate in candidates:
        if candidate.decision != DetectionDecision.AUTO_REDACT:
            continue
        tokens = [token for token in extracted.tokens_for(candidate) if token.bbox is not None]
        if not tokens:
            raise ImageRedactionError("Detected image region could not be mapped safely")
        grouped: dict[int, list[LayoutToken]] = {}
        for token in tokens:
            grouped.setdefault((token.page_number or 1) - 1, []).append(token)
        for frame_index, frame_tokens in grouped.items():
            if not 0 <= frame_index < len(output):
                raise ImageRedactionError("Detected image frame is out of range")
            boxes = [token.bbox for token in frame_tokens if token.bbox is not None]
            rectangle = (
                int(min(box[0] for box in boxes)), int(min(box[1] for box in boxes)),
                int(max(box[2] for box in boxes)), int(max(box[3] for box in boxes)),
            )
            draw = ImageDraw.Draw(output[frame_index])
            draw.rectangle(rectangle, fill="black")
            if candidate.entity_type not in {"FACE", "BARCODE"}:
                font = ImageFont.load_default()
                label = "[REDACTED]"
                if draw.textlength(label, font=font) <= max(1, rectangle[2] - rectangle[0]):
                    draw.text((rectangle[0], rectangle[1]), label, fill="white", font=font)
    return output


def redact_image(
    source: Path,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
) -> int:
    redactions = [item for item in candidates if item.decision == DetectionDecision.AUTO_REDACT]
    try:
        with Image.open(source) as original:
            image_format = original.format or "PNG"
            frames = [frame.copy() for frame in ImageSequence.Iterator(original)]
            durations = [frame.info.get("duration", original.info.get("duration", 0)) for frame in frames]
        output = redact_pil_frames(frames, extracted, candidates)
        destination.parent.mkdir(parents=True, exist_ok=True)
        save_options = {}
        if len(output) > 1:
            save_options.update(save_all=True, append_images=output[1:], duration=durations, loop=0)
        output[0].save(destination, format=image_format, **save_options)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, ImageRedactionError):
            raise
        raise ImageRedactionError("Image redaction failed") from exc
    return len(redactions)
