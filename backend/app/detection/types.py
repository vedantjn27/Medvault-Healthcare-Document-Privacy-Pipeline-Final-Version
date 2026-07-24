"""Runtime-only detection contracts with privacy-safe report serialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class DetectorSource(StrEnum):
    PRESIDIO = "presidio"
    SCISPACY = "scispacy"
    REGEX = "regex"
    CONTEXT = "context"
    MISTRAL = "mistral"
    DOCUMENT_CACHE = "document_cache"
    OCR = "ocr"
    COMPUTER_VISION = "computer_vision"
    BARCODE = "barcode"
    DICOM_TAG = "dicom_tag"


class DetectionDecision(StrEnum):
    AUTO_REDACT = "auto_redact"
    AMBIGUITY_REVIEW = "ambiguity_review"
    REVIEWED_NOT_REDACTED = "reviewed_not_redacted"
    PRESERVED_BY_MODE = "preserved_by_mode"


@dataclass(frozen=True, slots=True)
class StructuralContext:
    start: int
    end: int
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Structural context must cover a non-empty text range")


@dataclass(slots=True)
class DetectionCandidate:
    """A sensitive span retained only in process memory during redaction."""

    entity_type: str
    start: int
    end: int
    matched_text: str = field(repr=False)
    detector_score: float
    pattern_validation: float = 0.5
    context_boost: float = 0.0
    mistral_score: float = 0.0
    detector_sources: set[DetectorSource] = field(default_factory=set)
    trigger_reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    decision: DetectionDecision = DetectionDecision.REVIEWED_NOT_REDACTED
    page_number: int | None = None
    replacement_text: str | None = field(default=None, repr=False)
    explanation_text: str | None = None
    privileged_flag: bool = False

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Detection offsets must describe a non-empty span")
        for name in ("detector_score", "pattern_validation", "context_boost", "mistral_score"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    def safe_report(self) -> dict[str, object]:
        """Serialize evidence without exposing the matched sensitive value."""

        return {
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "detector_sources": sorted(source.value for source in self.detector_sources),
            "trigger_reasons": list(self.trigger_reasons),
            "decision": self.decision.value,
            "page_number": self.page_number,
        }
