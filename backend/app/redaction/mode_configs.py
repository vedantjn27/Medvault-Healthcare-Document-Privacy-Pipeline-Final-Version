"""Immutable privacy-mode policies and validated custom rules."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import PrivacyMode


DIRECT_IDENTIFIERS = frozenset(
    {
        "PERSON",
        "PATIENT_NAME",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "US_BANK_NUMBER",
        "CREDIT_CARD",
        "CRYPTO",
        "IBAN_CODE",
        "LOCATION",
        "NRP",
        "IP_ADDRESS",
        "MAC_ADDRESS",
        "URL",
        "MRN",
        "NPI",
        "US_NPI",
        "DEA_NUMBER",
        "INSURANCE_ID",
        "POLICY_NUMBER",
        "MEDICAL_LICENSE",
        "US_ITIN",
        "US_MBI",
        "UK_NHS",
        "UK_NINO",
        "UK_PASSPORT",
        "UK_DRIVING_LICENCE",
        "ES_NIF",
        "ES_NIE",
        "ES_PASSPORT",
        "DATE_TIME",
    }
)
CLINICAL_ENTITIES = frozenset({"MEDICAL_CONDITION", "MEDICATION", "CLINICAL_ENTITY"})
CLAIM_ENTITIES = frozenset(
    {"PROCEDURE_CODE", "DIAGNOSIS_CODE", "BILLING_DATE", "PAYER_ID"}
)
KNOWN_ENTITY_TYPES = DIRECT_IDENTIFIERS | CLINICAL_ENTITIES | CLAIM_ENTITIES


@dataclass(frozen=True, slots=True)
class ModeConfig:
    mode: PrivacyMode
    entity_types_to_redact: frozenset[str]
    entity_types_to_preserve: frozenset[str]
    confidence_threshold: float
    synthetic_replacement: bool = False
    verbose_labels: bool = False
    privilege_flagging: bool = False

    def should_redact(
        self,
        entity_type: str,
        *,
        matched_text: str | None = None,
        subject_patient_id: str | None = None,
    ) -> bool:
        if entity_type in self.entity_types_to_preserve:
            return False
        if (
            self.mode == PrivacyMode.PATIENT_PORTAL
            and subject_patient_id
            and matched_text
            and matched_text.casefold() == subject_patient_id.casefold()
        ):
            return False
        return "*" in self.entity_types_to_redact or entity_type in self.entity_types_to_redact


class CustomRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_types_to_redact: set[str] = Field(min_length=1)
    entity_types_to_preserve: set[str] = Field(default_factory=set)
    confidence_threshold: float = Field(default=0.75, ge=0.4, le=1.0)
    synthetic_replacement: bool = False

    @model_validator(mode="after")
    def validate_entity_sets(self) -> "CustomRules":
        unknown = (self.entity_types_to_redact | self.entity_types_to_preserve) - KNOWN_ENTITY_TYPES
        if unknown:
            raise ValueError(f"Unsupported entity types: {', '.join(sorted(unknown))}")
        overlap = self.entity_types_to_redact & self.entity_types_to_preserve
        if overlap:
            raise ValueError(f"Entity types cannot be both redacted and preserved: {', '.join(sorted(overlap))}")
        return self

    def to_mode_config(self) -> ModeConfig:
        return ModeConfig(
            mode=PrivacyMode.CUSTOM,
            entity_types_to_redact=frozenset(self.entity_types_to_redact),
            entity_types_to_preserve=frozenset(self.entity_types_to_preserve),
            confidence_threshold=self.confidence_threshold,
            synthetic_replacement=self.synthetic_replacement,
        )


MODE_CONFIGS: dict[PrivacyMode, ModeConfig] = {
    PrivacyMode.PATIENT_PORTAL: ModeConfig(
        mode=PrivacyMode.PATIENT_PORTAL,
        entity_types_to_redact=DIRECT_IDENTIFIERS - {"DATE_TIME"},
        entity_types_to_preserve=frozenset({"DATE_TIME"}),
        confidence_threshold=0.75,
        verbose_labels=True,
    ),
    PrivacyMode.RESEARCH_SHARING: ModeConfig(
        mode=PrivacyMode.RESEARCH_SHARING,
        entity_types_to_redact=frozenset({"*"}),
        entity_types_to_preserve=frozenset(),
        confidence_threshold=0.70,
        synthetic_replacement=True,
    ),
    PrivacyMode.INSURANCE_PROCESSING: ModeConfig(
        mode=PrivacyMode.INSURANCE_PROCESSING,
        entity_types_to_redact=DIRECT_IDENTIFIERS | CLINICAL_ENTITIES,
        entity_types_to_preserve=CLAIM_ENTITIES | {"NPI", "US_NPI", "DATE_TIME"},
        confidence_threshold=0.75,
        verbose_labels=True,
    ),
    PrivacyMode.LEGAL_DISCOVERY: ModeConfig(
        mode=PrivacyMode.LEGAL_DISCOVERY,
        entity_types_to_redact=frozenset({"*"}),
        entity_types_to_preserve=frozenset(),
        confidence_threshold=0.60,
        privilege_flagging=True,
    ),
}


def get_mode_config(mode: PrivacyMode, custom_rules: CustomRules | None = None) -> ModeConfig:
    if mode == PrivacyMode.CUSTOM:
        if custom_rules is None:
            raise ValueError("custom_rules are required for custom privacy mode")
        return custom_rules.to_mode_config()
    if custom_rules is not None:
        raise ValueError("custom_rules are only valid for custom privacy mode")
    return MODE_CONFIGS[mode]
