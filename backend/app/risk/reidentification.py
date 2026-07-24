"""Conservative k-anonymity-style heuristic for surviving quasi-identifiers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.models import ReidentificationRisk
from app.detection.types import DetectionCandidate, DetectionDecision


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    level: ReidentificationRisk
    score: int
    factors: tuple[str, ...]


def assess_reidentification_risk(
    text: str, candidates: list[DetectionCandidate] | None = None
) -> RiskAssessment:
    factors: list[str] = []
    score = 0
    if re.search(r"\b(?:age|aged)\s*[:=]?\s*(?:[1-8]?\d|90)\b", text, re.I):
        factors.append("exact age survives")
        score += 2
    if re.search(r"\b(?:age\s*)?\d{1,2}\s*[-–]\s*\d{1,2}\b", text, re.I):
        factors.append("age band survives")
        score += 1
    if re.search(r"\b(?:zip|postal(?: code)?)\s*[:=]?\s*\d{3}", text, re.I):
        factors.append("ZIP3 geography survives")
        score += 3
    if re.search(r"\b(?:sex|gender)\s*[:=]?\s*(?:male|female|nonbinary|other)\b", text, re.I):
        factors.append("gender survives")
        score += 1
    surviving_clinical = [
        candidate
        for candidate in candidates or []
        if candidate.entity_type in {"MEDICAL_CONDITION", "CLINICAL_ENTITY"}
        and candidate.decision != DetectionDecision.AUTO_REDACT
    ]
    if surviving_clinical:
        factors.append("clinical condition survives")
        score += 2
    rare_terms = {
        "huntington disease", "cystic fibrosis", "amyotrophic lateral sclerosis",
        "als", "gaucher disease", "ehlers-danlos syndrome", "marfan syndrome",
        "sickle cell disease", "hemophilia", "narcolepsy", "wilson disease",
    }
    if any(
        candidate.matched_text.strip().casefold() in rare_terms
        or any("rare" in reason.casefold() for reason in candidate.trigger_reasons)
        for candidate in surviving_clinical
    ):
        factors.append("rare clinical condition survives")
        score += 3
    level = (
        ReidentificationRisk.LOW if score <= 2
        else ReidentificationRisk.MEDIUM if score <= 5
        else ReidentificationRisk.HIGH
    )
    return RiskAssessment(level=level, score=score, factors=tuple(factors))
