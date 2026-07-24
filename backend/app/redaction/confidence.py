"""Exact ensemble confidence calculation and mode-aware decisions."""

from __future__ import annotations

from app.detection.types import DetectionCandidate, DetectionDecision
from app.redaction.mode_configs import ModeConfig


AMBIGUITY_FLOOR = 0.40


def calculate_confidence(candidate: DetectionCandidate) -> float:
    """Apply the specification's fixed detector/evidence weighting."""

    score = (
        0.45 * candidate.detector_score
        + 0.25 * candidate.pattern_validation
        + 0.20 * candidate.context_boost
        + 0.10 * candidate.mistral_score
    )
    return round(min(1.0, max(0.0, score)), 6)


def score_candidate(
    candidate: DetectionCandidate,
    mode: ModeConfig,
    *,
    subject_patient_id: str | None = None,
) -> DetectionCandidate:
    candidate.confidence = calculate_confidence(candidate)
    if not mode.should_redact(
        candidate.entity_type,
        matched_text=candidate.matched_text,
        subject_patient_id=subject_patient_id,
    ):
        candidate.decision = DetectionDecision.PRESERVED_BY_MODE
    elif candidate.confidence >= mode.confidence_threshold:
        candidate.decision = DetectionDecision.AUTO_REDACT
    elif candidate.confidence >= AMBIGUITY_FLOOR:
        candidate.decision = DetectionDecision.AMBIGUITY_REVIEW
    else:
        candidate.decision = DetectionDecision.REVIEWED_NOT_REDACTED
    return candidate
