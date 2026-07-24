"""Checksum-backed and context-constrained healthcare identifier recognizers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from presidio_analyzer import EntityRecognizer, RecognizerResult


def luhn_valid(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit()]
    if not digits:
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def npi_checksum_valid(value: str) -> bool:
    """Validate the CMS NPI check digit using the required 80840 prefix."""

    normalized = re.sub(r"\D", "", value)
    return len(normalized) == 10 and luhn_valid(f"80840{normalized}")


def dea_checksum_valid(value: str) -> bool:
    """Validate a DEA registration number's final check digit."""

    normalized = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if not re.fullmatch(r"[A-Z][A-Z9]\d{7}", normalized):
        return False
    digits = [int(character) for character in normalized[2:]]
    checksum = (digits[0] + digits[2] + digits[4] + 2 * (digits[1] + digits[3] + digits[5])) % 10
    return checksum == digits[6]


def always_valid(_: str) -> bool:
    return True


@dataclass(frozen=True, slots=True)
class IdentifierPattern:
    entity_type: str
    regex: re.Pattern[str]
    score: float
    validator: Callable[[str], bool]
    group: str = "value"
    validation_score: float = 1.0


IDENTIFIER_PATTERNS = (
    IdentifierPattern(
        "MRN",
        re.compile(
            r"(?i)\b(?:MRN|medical\s+record(?:\s+number)?|record\s+number)\s*[:#-]?\s*"
            r"(?P<value>[A-Z0-9][A-Z0-9-]{4,19})\b"
        ),
        0.85,
        always_valid,
    ),
    IdentifierPattern(
        "NPI",
        re.compile(r"(?<!\d)(?P<value>\d{10})(?!\d)"),
        0.90,
        npi_checksum_valid,
    ),
    IdentifierPattern(
        "DEA_NUMBER",
        re.compile(r"(?i)(?<![A-Z0-9])(?P<value>[A-Z][A-Z9]\d{7})(?![A-Z0-9])"),
        0.90,
        dea_checksum_valid,
    ),
    IdentifierPattern(
        "INSURANCE_ID",
        re.compile(
            r"(?i)\b(?:member|subscriber|beneficiary|insurance)\s*(?:id|number|no\.?)\s*[:#-]?\s*"
            r"(?P<value>[A-Z0-9][A-Z0-9-]{5,24})\b"
        ),
        0.85,
        always_valid,
    ),
    IdentifierPattern(
        "POLICY_NUMBER",
        re.compile(
            r"(?i)\bpolicy\s*(?:number|no\.?)?\s*[:#-]?\s*"
            r"(?P<value>[A-Z0-9][A-Z0-9-]{5,24})\b"
        ),
        0.85,
        always_valid,
    ),
    IdentifierPattern(
        "DIAGNOSIS_CODE",
        re.compile(r"(?i)\b(?:ICD-?10\s*[:#-]?\s*)?(?P<value>[A-TV-Z]\d{2}(?:\.\d{1,4})?)\b"),
        0.72,
        always_valid,
        validation_score=0.85,
    ),
    IdentifierPattern(
        "PROCEDURE_CODE",
        re.compile(r"(?i)\b(?:CPT|HCPCS)\s*[:#-]?\s*(?P<value>\d{5}|[A-Z]\d{4})\b"),
        0.82,
        always_valid,
    ),
    IdentifierPattern(
        "PAYER_ID",
        re.compile(r"(?i)\bpayer\s*(?:id|number)?\s*[:#-]?\s*(?P<value>[A-Z0-9-]{5,15})\b"),
        0.82,
        always_valid,
    ),
)


class HealthcareIdentifierRecognizer(EntityRecognizer):
    """Recognize only validated values and return the sensitive value's exact span."""

    def __init__(self) -> None:
        super().__init__(
            supported_entities=sorted({pattern.entity_type for pattern in IDENTIFIER_PATTERNS}),
            name="MedVaultHealthcareIdentifierRecognizer",
            supported_language="en",
            version="2.0.0",
        )

    def load(self) -> None:
        return None

    def analyze(self, text, entities, nlp_artifacts=None):
        del nlp_artifacts
        requested = set(entities or self.supported_entities)
        results: list[RecognizerResult] = []
        for pattern in IDENTIFIER_PATTERNS:
            if pattern.entity_type not in requested:
                continue
            for match in pattern.regex.finditer(text):
                value = match.group(pattern.group)
                if not pattern.validator(value):
                    continue
                start, end = match.span(pattern.group)
                results.append(
                    RecognizerResult(
                        entity_type=pattern.entity_type,
                        start=start,
                        end=end,
                        score=pattern.score,
                        recognition_metadata={
                            RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                            RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                            "detector_source": "regex",
                            "pattern_validation": pattern.validation_score,
                        },
                    )
                )
        return results
