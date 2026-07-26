"""Construction of the local Presidio ensemble and MedVault recognizers."""

from __future__ import annotations

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.detection.medical_recognizers import HealthcareIdentifierRecognizer
from app.detection.scispacy_recognizer import SciSpacyRecognizer


def build_analyzer(
    *, model_name: str = "en_core_web_lg", include_scispacy: bool = True
) -> AnalyzerEngine:
    """Build a fully local English analyzer using the installed CPU models."""

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": model_name}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp_engine)
    registry.add_recognizer(HealthcareIdentifierRecognizer())
    if include_scispacy:
        registry.add_recognizer(SciSpacyRecognizer())
    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["en"],
        default_score_threshold=0.0,
    )


@lru_cache(maxsize=2)
def get_analyzer(model_name: str = "en_core_web_lg") -> AnalyzerEngine:
    """Load the general PII and custom-regex analyzer once per worker process."""

    return build_analyzer(model_name=model_name, include_scispacy=False)
