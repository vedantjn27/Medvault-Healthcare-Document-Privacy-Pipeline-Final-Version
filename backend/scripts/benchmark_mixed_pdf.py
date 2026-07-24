"""Generate and validate a synthetic ten-page native/scanned PDF benchmark."""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import tempfile
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.db.models import PrivacyMode
from app.detection.pipeline import DetectionPipeline
from app.detection.types import DetectionDecision, DetectorSource
from app.documents.extractors.pdf_extractor import extract_pdf
from app.qa.redaction_verifier import RedactionVerifier
from app.redaction.mode_configs import get_mode_config
from app.redaction.redactors.pdf_redactor import redact_pdf


SYNTHETIC_LINES = (
    "Patient: Jordan Benchmark",
    "Email: benchmark.patient@example.com",
    "Phone: 415-555-0188",
    "MRN: MV-482910",
    "NPI: 1234567893",
    "DOB: 1984-01-15",
    "Medication: metformin",
    "Diagnosis: diabetes mellitus",
)


def _font(size: int):
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def build_fixture(path: Path) -> None:
    document = fitz.open()
    for index in range(10):
        page = document.new_page(width=612, height=792)
        if index % 2 == 0:
            page.insert_text((54, 45), f"Synthetic Clinical Record — Page {index + 1}", fontsize=15)
            for row, line in enumerate(SYNTHETIC_LINES):
                y = 90 + row * 42
                page.draw_rect(fitz.Rect(48, y - 22, 560, y + 10), color=(0.65, 0.65, 0.65))
                page.insert_text((58, y), line, fontsize=12)
        else:
            image = Image.new("RGB", (1800, 2200), "white")
            draw = ImageDraw.Draw(image)
            draw.text((100, 90), f"SCANNED CLINICAL RECORD PAGE {index + 1}", fill="black", font=_font(54))
            for row, line in enumerate(SYNTHETIC_LINES):
                draw.text((110, 240 + row * 170), line, fill="black", font=_font(48))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
            page.insert_image(page.rect, stream=buffer.getvalue())
    document.save(path)
    document.close()


async def run_benchmark(workdir: Path) -> dict[str, object]:
    settings = Settings()
    source, output = workdir / "mixed_10_page.pdf", workdir / "mixed_10_page_redacted.pdf"
    build_fixture(source)
    started = time.perf_counter()
    extracted = await asyncio.to_thread(extract_pdf, source, tesseract_cmd=settings.tesseract_cmd)
    extraction_seconds = time.perf_counter() - started
    mode = get_mode_config(PrivacyMode.LEGAL_DISCOVERY)
    detection_started = time.perf_counter()
    candidates = await DetectionPipeline(
        max_concurrent_chunks=settings.max_concurrent_chunks
    ).analyze_document(extracted.text, mode, structural_contexts=extracted.structural_contexts)
    for candidate in candidates:
        if any(token.source.endswith("_ocr") for token in extracted.tokens_for(candidate)):
            candidate.detector_sources.add(DetectorSource.OCR)
    detection_seconds = time.perf_counter() - detection_started
    render_started = time.perf_counter()
    await asyncio.to_thread(redact_pdf, source, output, extracted, candidates)
    render_seconds = time.perf_counter() - render_started
    qa_started = time.perf_counter()
    verification = await RedactionVerifier().verify(output, "pdf", mode, settings)
    qa_seconds = time.perf_counter() - qa_started
    redacted = [item for item in candidates if item.decision == DetectionDecision.AUTO_REDACT]
    if extracted.metadata.get("page_count") != 10:
        raise RuntimeError("Benchmark fixture did not extract ten pages")
    if not redacted:
        raise RuntimeError("Benchmark detected no redactions")
    if not verification.passed:
        raise RuntimeError(f"Benchmark QA failed: {verification.residual_entity_types}")
    return {
        "pages": 10,
        "native_pages": 5,
        "scanned_pages": 5,
        "candidates": len(candidates),
        "redacted_candidates": len(redacted),
        "qa_passed": verification.passed,
        "source_bytes": source.stat().st_size,
        "output_bytes": output.stat().st_size,
        "extraction_seconds": round(extraction_seconds, 3),
        "detection_seconds": round(detection_seconds, 3),
        "render_seconds": round(render_seconds, 3),
        "qa_seconds": round(qa_seconds, 3),
        "total_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="medvault-benchmark-") as directory:
        result = asyncio.run(run_benchmark(Path(directory)))
    rendered = json.dumps(result, indent=2)
    if args.output_json:
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
