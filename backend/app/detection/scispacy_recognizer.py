"""Presidio adapter for AllenAI biomedical entity models."""

from __future__ import annotations

from functools import lru_cache

from presidio_analyzer import EntityRecognizer, RecognizerResult
import spacy


class SciSpacyRecognizer(EntityRecognizer):
    """Map BC5CDR disease/chemical entities and generic clinical spans."""

    def __init__(
        self,
        core_model: str = "en_core_sci_md",
        ner_model: str = "en_ner_bc5cdr_md",
    ) -> None:
        self.core_model_name = core_model
        self.ner_model_name = ner_model
        self.core_nlp = None
        self.ner_nlp = None
        super().__init__(
            supported_entities=["MEDICAL_CONDITION", "MEDICATION", "CLINICAL_ENTITY"],
            name="MedVaultSciSpacyRecognizer",
            supported_language="en",
            version="2.0.0",
        )

    def load(self) -> None:
        self.core_nlp = spacy.load(self.core_model_name)
        self.ner_nlp = spacy.load(self.ner_model_name)

    def analyze(self, text, entities, nlp_artifacts=None):
        del nlp_artifacts
        requested = set(entities or self.supported_entities)
        results: list[RecognizerResult] = []
        seen: set[tuple[int, int, str]] = set()

        if self.ner_nlp is not None:
            for span in self.ner_nlp(text).ents:
                mapped = {"DISEASE": "MEDICAL_CONDITION", "CHEMICAL": "MEDICATION"}.get(span.label_)
                if mapped is None or mapped not in requested:
                    continue
                key = (span.start_char, span.end_char, mapped)
                seen.add(key)
                results.append(self._result(mapped, span.start_char, span.end_char, 0.82))

        if self.core_nlp is not None and "CLINICAL_ENTITY" in requested:
            for span in self.core_nlp(text).ents:
                key = (span.start_char, span.end_char, "CLINICAL_ENTITY")
                if key in seen:
                    continue
                results.append(self._result("CLINICAL_ENTITY", span.start_char, span.end_char, 0.50))
        return results

    def _result(self, entity_type: str, start: int, end: int, score: float) -> RecognizerResult:
        return RecognizerResult(
            entity_type=entity_type,
            start=start,
            end=end,
            score=score,
            recognition_metadata={
                RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                "detector_source": "scispacy",
                "pattern_validation": 0.5,
            },
        )


@lru_cache(maxsize=1)
def get_scispacy_recognizer() -> SciSpacyRecognizer:
    """Load both biomedical pipelines once per worker process."""

    return SciSpacyRecognizer()
