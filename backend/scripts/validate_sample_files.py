"""Classify and redaction-test the generated synthetic sample corpus."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from beanie import PydanticObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.db.models import PrivacyMode
from app.detection.pipeline import DetectionPipeline
from app.detection.types import DetectionDecision, DetectorSource
from app.documents.file_types import classify_document
from app.qa.redaction_verifier import RedactionVerifier
from app.redaction.mode_configs import CustomRules, KNOWN_ENTITY_TYPES, get_mode_config
from app.redaction.pipeline import _extract, _render
from app.synthetic.faker_replacement import SyntheticReplacementEngine


ROOT = Path(__file__).resolve().parents[1] / "sample_files"
RESULTS = Path(__file__).resolve().parents[1] / "sample_validation_results.json"
MODE_FILES = {
    "patient_portal_mode.pdf": PrivacyMode.PATIENT_PORTAL,
    "research_sharing_mode.pdf": PrivacyMode.RESEARCH_SHARING,
    "insurance_processing_mode.pdf": PrivacyMode.INSURANCE_PROCESSING,
    "legal_discovery_mode.pdf": PrivacyMode.LEGAL_DISCOVERY,
    "custom_mode_mixed_native_scanned.pdf": PrivacyMode.CUSTOM,
}


async def validate_one(path: Path, settings: Settings, detector: DetectionPipeline, output_root: Path):
    file_type = classify_document(path, path.name)
    privacy_mode = MODE_FILES.get(path.name, PrivacyMode.LEGAL_DISCOVERY)
    custom = None
    if privacy_mode == PrivacyMode.CUSTOM:
        custom = CustomRules(
            entity_types_to_redact=set(KNOWN_ENTITY_TYPES), confidence_threshold=0.6
        )
    mode = get_mode_config(privacy_mode, custom)
    document = SimpleNamespace(
        id=PydanticObjectId(), original_filename=path.name,
        file_type=file_type.value, temp_job_path=str(path.resolve()),
    )
    extracted = await asyncio.to_thread(_extract, document, settings)
    subject_id = "MV-482910" if privacy_mode == PrivacyMode.PATIENT_PORTAL else None
    candidates = await detector.analyze_document(
        extracted.text, mode, structural_contexts=extracted.structural_contexts,
        subject_patient_id=subject_id,
    )
    for candidate in candidates:
        if any(token.source.endswith("_ocr") for token in extracted.tokens_for(candidate)):
            candidate.detector_sources.add(DetectorSource.OCR)
    candidates.extend(extracted.preclassified_candidates)
    candidates.sort(key=lambda item: (item.start, item.end, item.entity_type))
    allowed: set[str] = set()
    if mode.synthetic_replacement:
        allowed = SyntheticReplacementEngine(str(document.id)).assign(candidates)
    output = output_root / f"redacted_{path.stem}{path.suffix.lower()}"
    redacted_count = await asyncio.to_thread(
        _render, document, output, extracted, candidates, mode.verbose_labels
    )
    verification = await RedactionVerifier(detector).verify(
        output, file_type.value, mode, settings,
        allowed_replacements=allowed, subject_patient_id=subject_id,
    )
    expected_gap = False
    embedded_image_unchanged = False
    if redacted_count == 0:
        raise RuntimeError(f"No redactions were produced for {path.name}")
    if not verification.passed and not expected_gap:
        raise RuntimeError(
            f"Unexpected residual PHI in {path.name}: {verification.residual_entity_types}"
        )
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "file_type": file_type.value,
        "privacy_mode": privacy_mode.value,
        "extracted_characters": len(extracted.text),
        "candidate_count": len(candidates),
        "redacted_count": redacted_count,
        "qa_passed": verification.passed,
        "effective_passed": verification.passed and not embedded_image_unchanged,
        "expected_capability_gap": expected_gap,
        "embedded_image_unchanged": embedded_image_unchanged,
        "residual_entity_types": list(verification.residual_entity_types),
    }


async def main() -> None:
    settings = Settings()
    files = sorted(path for path in ROOT.rglob("*") if path.is_file())
    detector = DetectionPipeline(max_concurrent_chunks=settings.max_concurrent_chunks)
    with tempfile.TemporaryDirectory(prefix="medvault-sample-validation-") as directory:
        output_root = Path(directory)
        results = []
        for index, path in enumerate(files, 1):
            print(f"[{index}/{len(files)}] {path.relative_to(ROOT)}")
            results.append(await validate_one(path, settings, detector, output_root))
    summary = {
        "total_files": len(results),
        "fully_passed": sum(item["effective_passed"] for item in results),
        "known_capability_gaps": sum(item["expected_capability_gap"] for item in results),
        "results": results,
    }
    RESULTS.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in summary if key != "results"}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
