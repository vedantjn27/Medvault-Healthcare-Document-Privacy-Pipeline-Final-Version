"""DICOM PHI-tag inventory and multi-frame burned-in pixel analysis."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

from app.detection.types import DetectionCandidate, DetectionDecision, DetectorSource
from app.documents.extractors.image_extractor import analyze_image_frames
from app.documents.extractors.types import ExtractedDocument, LayoutToken
from app.redaction.dicom_tags import DICOM_PHI_KEYWORDS, DICOM_UID_KEYWORDS


class DicomExtractionError(ValueError):
    pass


def dataset_to_frames(dataset: pydicom.Dataset) -> list[Image.Image]:
    if "PixelData" not in dataset:
        return []
    try:
        pixels = np.asarray(dataset.pixel_array)
    except Exception as exc:
        raise DicomExtractionError("DICOM pixel data could not be decoded safely") from exc
    frame_count = int(getattr(dataset, "NumberOfFrames", 1))
    if frame_count > 1:
        arrays = list(pixels)
    else:
        arrays = [pixels]
    frames = []
    for array in arrays:
        values = np.asarray(array)
        if values.ndim == 3 and values.shape[-1] in {3, 4}:
            rendered = np.clip(values[..., :3], 0, 255).astype(np.uint8)
            frames.append(Image.fromarray(rendered, mode="RGB"))
            continue
        values = values.astype(np.float32)
        minimum, maximum = float(values.min()), float(values.max())
        normalized = np.zeros_like(values, dtype=np.uint8)
        if maximum > minimum:
            normalized = ((values - minimum) * (255.0 / (maximum - minimum))).astype(np.uint8)
        image = Image.fromarray(normalized, mode="L")
        if str(getattr(dataset, "PhotometricInterpretation", "")) == "MONOCHROME1":
            image = Image.fromarray(255 - normalized, mode="L")
        frames.append(image.convert("RGB"))
    return frames


def _metadata_extraction(dataset: pydicom.Dataset) -> ExtractedDocument:
    parts: list[str] = []
    tokens: list[LayoutToken] = []
    candidates: list[DetectionCandidate] = []
    count = 0
    for element in dataset.iterall():
        keyword = element.keyword
        if keyword not in DICOM_PHI_KEYWORDS and keyword not in DICOM_UID_KEYWORDS:
            continue
        if element.VR == "SQ" or element.value is None or element.value == "":
            continue
        value = str(element.value)
        if parts:
            parts.append("\n")
        start = sum(len(part) for part in parts)
        parts.append(value)
        end = start + len(value)
        locator = f"dicom_tag:{int(element.tag):08X}:{count}"
        count += 1
        for index, character in enumerate(value):
            tokens.append(
                LayoutToken(
                    text=character,
                    start=start + index,
                    end=start + index + 1,
                    locator=locator,
                    local_start=index,
                    local_end=index + 1,
                    source="dicom_tag",
                )
            )
        candidates.append(
            DetectionCandidate(
                entity_type="DICOM_METADATA",
                start=start,
                end=end,
                matched_text=value,
                detector_score=1.0,
                pattern_validation=1.0,
                context_boost=1.0,
                detector_sources={DetectorSource.DICOM_TAG},
                trigger_reasons=[f"DICOM confidentiality profile identifies the {keyword} tag"],
                confidence=1.0,
                decision=DetectionDecision.AUTO_REDACT,
            )
        )
    return ExtractedDocument(text="".join(parts), tokens=tokens, preclassified_candidates=candidates)


def extract_dicom(path: Path, *, tesseract_cmd: Path | None = None) -> ExtractedDocument:
    if tesseract_cmd is not None:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)
    try:
        dataset = pydicom.dcmread(path)
        metadata = _metadata_extraction(dataset)
        frames = dataset_to_frames(dataset)
        visual = analyze_image_frames(frames, locator_prefix="dicom") if frames else ExtractedDocument("", [])
    except DicomExtractionError:
        raise
    except Exception as exc:
        raise DicomExtractionError("DICOM extraction failed") from exc

    separator = "\n" if metadata.text and visual.text else ""
    offset = len(metadata.text) + len(separator)
    shifted_tokens = [
        replace(token, start=token.start + offset, end=token.end + offset)
        for token in visual.tokens
    ]
    shifted_candidates = [
        replace(candidate, start=candidate.start + offset, end=candidate.end + offset)
        for candidate in visual.preclassified_candidates
    ]
    return ExtractedDocument(
        text=metadata.text + separator + visual.text,
        tokens=metadata.tokens + shifted_tokens,
        preclassified_candidates=metadata.preclassified_candidates + shifted_candidates,
        metadata={
            "frame_count": len(frames),
            "phi_tag_count": len(metadata.preclassified_candidates),
            **visual.metadata,
        },
    )
