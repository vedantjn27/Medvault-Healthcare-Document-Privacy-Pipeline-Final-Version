"""Output re-extraction and residual-PHI verification."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.detection.pipeline import DetectionPipeline
from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.dicom_extractor import extract_dicom
from app.documents.extractors.docx_extractor import extract_docx
from app.documents.extractors.email_extractor import extract_email
from app.documents.extractors.image_extractor import extract_image
from app.documents.extractors.pdf_extractor import extract_pdf
from app.documents.extractors.xlsx_extractor import extract_xlsx
from app.documents.file_types import FileType
from app.redaction.mode_configs import ModeConfig


@dataclass(slots=True)
class VerificationResult:
    passed: bool
    residual_entity_types: tuple[str, ...]
    extracted_text: str = field(repr=False)
    candidates: list[DetectionCandidate] = field(default_factory=list, repr=False)


class RedactionVerifier:
    def __init__(self, detector: DetectionPipeline | None = None) -> None:
        self._detector = detector

    async def verify(
        self,
        output: Path,
        file_type: str,
        mode: ModeConfig,
        settings: Settings,
        *,
        allowed_replacements: set[str] | None = None,
        subject_patient_id: str | None = None,
    ) -> VerificationResult:
        extracted = await asyncio.to_thread(_extract_output, output, file_type, settings)
        detector = self._detector or DetectionPipeline(
            max_concurrent_chunks=settings.max_concurrent_chunks
        )
        candidates = await detector.analyze_document(
            extracted.text,
            mode,
            structural_contexts=extracted.structural_contexts,
            subject_patient_id=subject_patient_id,
        )
        candidates.extend(extracted.preclassified_candidates)
        allowed = {value.casefold() for value in (allowed_replacements or set())}
        residual = [candidate for candidate in candidates if _is_residual(candidate, allowed, file_type)]
        return VerificationResult(
            passed=not residual,
            residual_entity_types=tuple(sorted({item.entity_type for item in residual})),
            extracted_text=extracted.text,
            candidates=candidates,
        )


def _is_residual(candidate: DetectionCandidate, allowed: set[str], file_type: str) -> bool:
    if candidate.decision != DetectionDecision.AUTO_REDACT:
        return False
    value = candidate.matched_text.strip().casefold()
    if value and any(value in replacement for replacement in allowed):
        return False
    if value.startswith("[redacted") or value.startswith("[synthetic"):
        return False
    if file_type == "dicom" and candidate.entity_type in {"DICOM_UID", "DICOM_METADATA"}:
        if any("uid" in reason.casefold() for reason in candidate.trigger_reasons):
            return False
    return True


def _extract_output(path: Path, file_type: str, settings: Settings):
    if file_type == "pdf":
        return extract_pdf(path, tesseract_cmd=settings.tesseract_cmd)
    if file_type == "docx":
        return extract_docx(path, tesseract_cmd=settings.tesseract_cmd)
    if file_type == "xlsx":
        return extract_xlsx(path, tesseract_cmd=settings.tesseract_cmd)
    if file_type in {"jpeg", "png", "tiff"}:
        return extract_image(path, tesseract_cmd=settings.tesseract_cmd)
    if file_type == "dicom":
        return extract_dicom(path, tesseract_cmd=settings.tesseract_cmd)
    if file_type in {"eml", "mbox"}:
        return extract_email(path, file_type=FileType(file_type), tesseract_cmd=settings.tesseract_cmd)
    raise ValueError("Unsupported QA file type")
