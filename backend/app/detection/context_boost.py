"""Deterministic label-proximity and structural-header evidence scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass


ENTITY_LABELS: dict[str, frozenset[str]] = {
    "PATIENT_NAME": frozenset({"patient", "patient name", "member name", "name"}),
    "PERSON": frozenset({"patient", "patient name", "provider", "physician", "doctor", "name"}),
    "MRN": frozenset({"mrn", "medical record", "medical record number", "record number"}),
    "NPI": frozenset({"npi", "national provider identifier", "provider id"}),
    "US_NPI": frozenset({"npi", "national provider identifier", "provider id"}),
    "DEA_NUMBER": frozenset({"dea", "dea number", "prescriber dea"}),
    "INSURANCE_ID": frozenset({"insurance id", "member id", "subscriber id", "beneficiary id"}),
    "POLICY_NUMBER": frozenset({"policy", "policy number", "plan number"}),
    "DATE_TIME": frozenset({"dob", "date of birth", "birth date", "admission date", "discharge date"}),
    "PHONE_NUMBER": frozenset({"phone", "telephone", "mobile", "fax"}),
    "EMAIL_ADDRESS": frozenset({"email", "e-mail"}),
    "MEDICAL_CONDITION": frozenset({"diagnosis", "condition", "assessment", "problem"}),
    "MEDICATION": frozenset({"medication", "drug", "prescription", "rx"}),
}


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    score: float
    reasons: tuple[str, ...]


def context_evidence(
    text: str,
    start: int,
    entity_type: str,
    *,
    structural_labels: list[str] | None = None,
) -> ContextEvidence:
    labels = ENTITY_LABELS.get(entity_type, frozenset())
    if not labels:
        return ContextEvidence(0.0, ())

    normalized_headers = {label.strip().casefold().rstrip(":# ") for label in structural_labels or []}
    matching_headers = sorted(labels & normalized_headers)
    if matching_headers:
        return ContextEvidence(1.0, (f"matched structural label '{matching_headers[0]}'",))

    line_start = max(text.rfind("\n", 0, start) + 1, start - 80)
    preceding = text[line_start:start].casefold()
    best_score = 0.0
    best_label: str | None = None
    for label in sorted(labels, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(label)}\b\s*[:#-]?\s*$", preceding)
        if match:
            distance = len(preceding) - match.end()
            score = 1.0 if distance <= 2 else 0.85
        elif re.search(rf"\b{re.escape(label)}\b", preceding[-40:]):
            score = 0.65
        else:
            continue
        if score > best_score:
            best_score, best_label = score, label
    reasons = (f"appeared near '{best_label}' label",) if best_label else ()
    return ContextEvidence(best_score, reasons)
