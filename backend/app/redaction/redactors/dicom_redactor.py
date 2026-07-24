"""DICOM metadata de-identification and destructive burned-in pixel redaction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
from pydicom.uid import generate_uid

from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.types import ExtractedDocument
from app.redaction.dicom_tags import DICOM_PHI_KEYWORDS, DICOM_UID_KEYWORDS


class DicomRedactionError(ValueError):
    pass


def scrub_dicom_metadata(dataset: pydicom.Dataset) -> int:
    uid_map: dict[str, str] = {}
    changed = 0

    def scrub(current: pydicom.Dataset) -> None:
        nonlocal changed
        for element in list(current):
            if element.VR == "SQ":
                for item in element.value:
                    scrub(item)
            keyword = element.keyword
            if keyword in DICOM_UID_KEYWORDS:
                original = str(element.value)
                replacement = uid_map.setdefault(original, generate_uid())
                element.value = replacement
                changed += 1
            elif keyword in DICOM_PHI_KEYWORDS:
                del current[element.tag]
                changed += 1

    scrub(dataset)
    dataset.remove_private_tags()
    dataset.PatientIdentityRemoved = "YES"
    dataset.DeidentificationMethod = "MedVault PS3.15 Basic Application Confidentiality Profile"
    if "SOPInstanceUID" in dataset and getattr(dataset, "file_meta", None) is not None:
        dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    return changed


def _redact_pixels(
    dataset: pydicom.Dataset,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
) -> int:
    visual_candidates = [
        candidate
        for candidate in candidates
        if candidate.decision == DetectionDecision.AUTO_REDACT
        and candidate.entity_type != "DICOM_METADATA"
        and any(token.bbox is not None for token in extracted.tokens_for(candidate))
    ]
    if not visual_candidates or "PixelData" not in dataset:
        return 0
    if dataset.file_meta.TransferSyntaxUID.is_compressed:
        dataset.decompress()
    pixels = np.asarray(dataset.pixel_array).copy()
    frame_count = int(getattr(dataset, "NumberOfFrames", 1))
    frames = pixels if frame_count > 1 else np.expand_dims(pixels, axis=0)
    monochrome_one = str(getattr(dataset, "PhotometricInterpretation", "")) == "MONOCHROME1"
    fill_value = np.iinfo(frames.dtype).max if monochrome_one and np.issubdtype(frames.dtype, np.integer) else 0
    applied = 0
    for candidate in visual_candidates:
        grouped: dict[int, list[tuple[float, float, float, float]]] = {}
        for token in extracted.tokens_for(candidate):
            if token.bbox is not None:
                grouped.setdefault((token.page_number or 1) - 1, []).append(token.bbox)
        for frame_index, boxes in grouped.items():
            if not 0 <= frame_index < len(frames):
                raise DicomRedactionError("DICOM frame mapping is invalid")
            x0 = max(0, int(min(box[0] for box in boxes)))
            y0 = max(0, int(min(box[1] for box in boxes)))
            x1 = min(frames[frame_index].shape[1], int(max(box[2] for box in boxes)) + 1)
            y1 = min(frames[frame_index].shape[0], int(max(box[3] for box in boxes)) + 1)
            frames[frame_index][y0:y1, x0:x1, ...] = fill_value
            applied += 1
    dataset.PixelData = (frames if frame_count > 1 else frames[0]).tobytes()
    dataset.BurnedInAnnotation = "NO"
    return applied


def redact_dicom(
    source: Path,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
) -> int:
    try:
        dataset = pydicom.dcmread(source)
        pixel_count = _redact_pixels(dataset, extracted, candidates)
        metadata_count = scrub_dicom_metadata(dataset)
        destination.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_as(destination, enforce_file_format=True)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, DicomRedactionError):
            raise
        raise DicomRedactionError("DICOM redaction failed") from exc
    return metadata_count + pixel_count
