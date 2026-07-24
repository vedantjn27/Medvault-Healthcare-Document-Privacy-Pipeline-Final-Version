"""PDF/DOCX/XLSX extraction, detection, rendering, and metadata persistence."""

from __future__ import annotations

import asyncio
from pathlib import Path

from beanie import PydanticObjectId

from app.ai.mistral_agent import MistralPrivacyAgent, local_explanation
from app.config import Settings
from app.db.models import (
    BoundingBox,
    DocumentStatus,
    JobStatus,
    RedactionEntity,
    RedactionJob,
    UploadedDocument,
    utc_now,
)
from app.detection.pipeline import DetectionPipeline
from app.detection.types import DetectionCandidate, DetectionDecision, DetectorSource
from app.documents.extractors.docx_extractor import extract_docx
from app.documents.extractors.dicom_extractor import extract_dicom
from app.documents.extractors.email_extractor import extract_email
from app.documents.extractors.image_extractor import extract_image
from app.documents.extractors.pdf_extractor import extract_pdf
from app.documents.extractors.types import ExtractedDocument
from app.documents.extractors.xlsx_extractor import extract_xlsx
from app.documents.file_types import FileType
from app.redaction.mode_configs import CustomRules, get_mode_config
from app.redaction.redactors.docx_redactor import redact_docx
from app.redaction.redactors.dicom_redactor import redact_dicom
from app.redaction.redactors.email_redactor import redact_email
from app.redaction.redactors.image_redactor import redact_image
from app.redaction.redactors.pdf_redactor import redact_pdf
from app.redaction.redactors.xlsx_redactor import redact_xlsx
from app.qa.redaction_verifier import RedactionVerifier
from app.risk.reidentification import assess_reidentification_risk
from app.synthetic.faker_replacement import SyntheticReplacementEngine
from app.audit.hash_chain import append_audit_event
from app.auth.push import notify_job_finished
from app.db.models import User
from app.redaction.feedback_learning import apply_feedback_adjustments, feedback_adjustments


SUPPORTED_PIPELINE_TYPES = {
    "pdf", "docx", "xlsx", "jpeg", "png", "tiff", "dicom", "eml", "mbox"
}


class RedactionPipelineError(RuntimeError):
    pass


def output_path_for(document: UploadedDocument, job_id: PydanticObjectId) -> Path:
    source = Path(document.temp_job_path)
    return source.parent / f"redacted_{job_id}{source.suffix.lower()}"


def _extract(document: UploadedDocument, settings: Settings) -> ExtractedDocument:
    source = Path(document.temp_job_path)
    if document.file_type == "pdf":
        return extract_pdf(source, tesseract_cmd=settings.tesseract_cmd)
    if document.file_type == "docx":
        return extract_docx(source, tesseract_cmd=settings.tesseract_cmd)
    if document.file_type == "xlsx":
        return extract_xlsx(source, tesseract_cmd=settings.tesseract_cmd)
    if document.file_type in {"jpeg", "png", "tiff"}:
        return extract_image(source, tesseract_cmd=settings.tesseract_cmd)
    if document.file_type == "dicom":
        return extract_dicom(source, tesseract_cmd=settings.tesseract_cmd)
    if document.file_type in {"eml", "mbox"}:
        return extract_email(
            source,
            file_type=FileType(document.file_type),
            tesseract_cmd=settings.tesseract_cmd,
        )
    raise RedactionPipelineError("This file type is not enabled in the current pipeline phase")


def _render(
    document: UploadedDocument,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
    verbose_labels: bool,
) -> int:
    source = Path(document.temp_job_path)
    if document.file_type == "pdf":
        return redact_pdf(source, destination, extracted, candidates, verbose_labels=verbose_labels)
    if document.file_type == "docx":
        return redact_docx(source, destination, extracted, candidates, verbose_labels=verbose_labels)
    if document.file_type == "xlsx":
        return redact_xlsx(source, destination, extracted, candidates, verbose_labels=verbose_labels)
    if document.file_type in {"jpeg", "png", "tiff"}:
        return redact_image(source, destination, extracted, candidates)
    if document.file_type == "dicom":
        return redact_dicom(source, destination, extracted, candidates)
    if document.file_type in {"eml", "mbox"}:
        return redact_email(
            source,
            destination,
            extracted,
            candidates,
            verbose_labels=verbose_labels,
        )
    raise RedactionPipelineError("This file type is not enabled in the current pipeline phase")


async def _persist_entities(
    job: RedactionJob,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
) -> None:
    documents: list[RedactionEntity] = []
    for candidate in candidates:
        page_number, raw_bbox = extracted.bbox_for(candidate)
        bbox = BoundingBox(x0=raw_bbox[0], y0=raw_bbox[1], x1=raw_bbox[2], y1=raw_bbox[3]) if raw_bbox else None
        documents.append(
            RedactionEntity(
                job_id=job.id,
                entity_type=candidate.entity_type,
                page_number=page_number,
                bbox=bbox,
                confidence=candidate.confidence,
                detector_source=sorted(source.value for source in candidate.detector_sources),
                explanation_text=candidate.explanation_text or local_explanation(candidate),
                was_redacted=candidate.decision == DetectionDecision.AUTO_REDACT,
                privileged_flag=candidate.privileged_flag,
            )
        )
    if documents:
        await RedactionEntity.insert_many(documents)


async def process_redaction_job(
    job_id: PydanticObjectId,
    settings: Settings,
    *,
    subject_patient_id: str | None = None,
    verbose_labels: bool = False,
    detector: DetectionPipeline | None = None,
    verifier: RedactionVerifier | None = None,
    ai_agent: MistralPrivacyAgent | None = None,
) -> None:
    """Run one job and persist only privacy-safe detection metadata."""

    job = await RedactionJob.get(job_id)
    if job is None:
        return
    document = await UploadedDocument.get(job.document_id)
    if document is None:
        job.status = JobStatus.ERROR
        job.error_message = "Source document metadata is unavailable"
        job.completed_at = utc_now()
        await job.save()
        return

    job.status = JobStatus.PROCESSING
    job.error_message = None
    document.status = DocumentStatus.PROCESSING
    await job.save()
    await document.save()
    await append_audit_event(
        document.id, "redaction_started",
        {"privacy_mode": job.privacy_mode.value}, job_id=job.id,
    )
    partial_output = output_path_for(document, job.id).with_suffix(
        output_path_for(document, job.id).suffix + ".partial"
    )
    final_output = output_path_for(document, job.id)
    try:
        if document.file_type not in SUPPORTED_PIPELINE_TYPES:
            raise RedactionPipelineError("This file type is not enabled in the current pipeline phase")
        source = Path(document.temp_job_path)
        if not source.is_file():
            raise RedactionPipelineError("Source document temporary data is unavailable")
        extracted = await asyncio.to_thread(_extract, document, settings)
        custom_rules = CustomRules.model_validate(job.custom_rules) if job.custom_rules else None
        mode = get_mode_config(job.privacy_mode, custom_rules)
        detection_pipeline = detector or DetectionPipeline(
            max_concurrent_chunks=settings.max_concurrent_chunks
        )
        candidates = await detection_pipeline.analyze_document(
            extracted.text,
            mode,
            structural_contexts=extracted.structural_contexts,
            subject_patient_id=subject_patient_id,
        )
        for candidate in candidates:
            if any(token.source.endswith("_ocr") for token in extracted.tokens_for(candidate)):
                candidate.detector_sources.add(DetectorSource.OCR)
                candidate.trigger_reasons.append("identified in locally OCR-extracted image text")
        candidates.extend(extracted.preclassified_candidates)
        candidates.sort(key=lambda item: (item.start, item.end, item.entity_type))
        adjustments = await feedback_adjustments(job.owner_id)
        apply_feedback_adjustments(candidates, adjustments, mode, subject_patient_id)
        if mode.privilege_flagging:
            _apply_legal_privilege_flags(candidates, extracted.text)
        agent = ai_agent or MistralPrivacyAgent(settings)
        await agent.enrich(
            candidates,
            extracted.text,
            mode,
            subject_patient_id=subject_patient_id,
        )
        allowed_replacements: set[str] = set()
        if mode.synthetic_replacement:
            allowed_replacements = SyntheticReplacementEngine(str(document.id)).assign(candidates)
        await asyncio.to_thread(
            _render,
            document,
            partial_output,
            extracted,
            candidates,
            verbose_labels or mode.verbose_labels,
        )
        partial_output.replace(final_output)
        await _persist_entities(job, extracted, candidates)
        await append_audit_event(
            document.id,
            "redaction_decisions_recorded",
            {
                "decisions": [
                    {
                        "entity_type": candidate.entity_type,
                        "confidence": candidate.confidence,
                        "decision": candidate.decision.value,
                        "explanation": candidate.explanation_text or local_explanation(candidate),
                        "privileged": candidate.privileged_flag,
                    }
                    for candidate in candidates
                ]
            },
            job_id=job.id,
        )
        verification = await (verifier or RedactionVerifier()).verify(
            final_output,
            document.file_type,
            mode,
            settings,
            allowed_replacements=allowed_replacements,
            subject_patient_id=subject_patient_id,
        )
        job.qa_passed = verification.passed
        if job.privacy_mode.value == "research_sharing":
            risk = assess_reidentification_risk(
                verification.extracted_text, verification.candidates
            )
            job.reidentification_risk = risk.level
            job.reidentification_factors = list(risk.factors)
        job.status = JobStatus.COMPLETE if verification.passed else JobStatus.QA_FAILED
        if not verification.passed:
            job.error_message = (
                "Post-redaction QA detected residual sensitive categories: "
                + ", ".join(verification.residual_entity_types)
            )
        job.completed_at = utc_now()
        document.status = DocumentStatus.DONE if verification.passed else DocumentStatus.UPLOADED
        await job.save()
        await document.save()
        await append_audit_event(
            document.id,
            "redaction_completed" if verification.passed else "redaction_qa_failed",
            {
                "status": job.status.value,
                "qa_passed": job.qa_passed,
                "entity_count": len(candidates),
                "redacted_count": sum(c.decision == DetectionDecision.AUTO_REDACT for c in candidates),
                "reidentification_risk": job.reidentification_risk.value if job.reidentification_risk else None,
            },
            job_id=job.id,
        )
        user = await User.get(job.owner_id)
        if user is not None:
            try:
                await notify_job_finished(user, job, settings)
            except Exception:
                pass
    except Exception as exc:
        partial_output.unlink(missing_ok=True)
        final_output.unlink(missing_ok=True)
        job.status = JobStatus.ERROR
        job.completed_at = utc_now()
        job.error_message = f"Processing failed ({type(exc).__name__})"
        document.status = DocumentStatus.UPLOADED
        await job.save()
        await document.save()
        try:
            await append_audit_event(
                document.id, "redaction_error",
                {"error_type": type(exc).__name__}, job_id=job.id,
            )
        except Exception:
            pass


def _apply_legal_privilege_flags(candidates: list[DetectionCandidate], text: str) -> None:
    import re

    legal = re.compile(
        r"\b(?:attorney[- ]client|legal privilege|privileged and confidential|"
        r"outside counsel|general counsel|law firm|legal advice|work product)\b",
        re.IGNORECASE,
    )
    for candidate in candidates:
        context = text[max(0, candidate.start - 160): min(len(text), candidate.end + 160)]
        if legal.search(context):
            candidate.privileged_flag = True
            candidate.trigger_reasons.append("appeared in attorney or privileged legal-note context")
