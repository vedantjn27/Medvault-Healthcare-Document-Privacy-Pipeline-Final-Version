"""Bounded concurrent text detection, evidence merging, and entity caching."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Protocol

from presidio_analyzer import RecognizerResult

from app.detection.context_boost import context_evidence
from app.detection.presidio_setup import get_analyzer
from app.detection.scispacy_recognizer import SciSpacyRecognizer, get_scispacy_recognizer
from app.detection.types import (
    DetectionCandidate,
    DetectionDecision,
    DetectorSource,
    StructuralContext,
)
from app.redaction.confidence import score_candidate
from app.redaction.mode_configs import ModeConfig


DEFAULT_CHUNK_CHARACTERS = 2_000
DEFAULT_SENTENCE_OVERLAP = 2


class AnalyzerProtocol(Protocol):
    def analyze(self, *, text: str, language: str, score_threshold: float, return_decision_process: bool): ...


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    text: str
    start: int
    end: int


def _sentence_spans(text: str, max_characters: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r".+?(?:[.!?](?=\s)|\n+|$)", text, flags=re.DOTALL):
        start, end = match.span()
        while end - start > max_characters:
            split = text.rfind(" ", start, start + max_characters)
            if split <= start:
                split = start + max_characters
            spans.append((start, split))
            start = split
            while start < end and text[start].isspace():
                start += 1
        if end > start:
            spans.append((start, end))
    return spans or ([(0, len(text))] if text else [])


def chunk_text(
    text: str,
    *,
    max_characters: int = DEFAULT_CHUNK_CHARACTERS,
    sentence_overlap: int = DEFAULT_SENTENCE_OVERLAP,
) -> list[TextChunk]:
    """Chunk on sentence/paragraph boundaries with a two-sentence overlap."""

    if max_characters < 200:
        raise ValueError("max_characters must be at least 200")
    if sentence_overlap < 0:
        raise ValueError("sentence_overlap cannot be negative")
    sentences = _sentence_spans(text, max_characters)
    chunks: list[TextChunk] = []
    cursor = 0
    while cursor < len(sentences):
        start_index = cursor
        start = sentences[start_index][0]
        end = sentences[start_index][1]
        cursor += 1
        while cursor < len(sentences) and sentences[cursor][1] - start <= max_characters:
            end = sentences[cursor][1]
            cursor += 1
        chunks.append(TextChunk(len(chunks), text[start:end], start, end))
        if cursor >= len(sentences):
            break
        next_cursor = max(start_index + 1, cursor - sentence_overlap)
        cursor = next_cursor
    return chunks


def _source_from_result(result: RecognizerResult) -> DetectorSource:
    metadata = result.recognition_metadata or {}
    declared = metadata.get("detector_source")
    if declared in {source.value for source in DetectorSource}:
        return DetectorSource(declared)
    return DetectorSource.PRESIDIO


def _pattern_validation_from_result(result: RecognizerResult) -> float:
    metadata = result.recognition_metadata or {}
    if "pattern_validation" in metadata:
        return float(metadata["pattern_validation"])
    recognizer_name = str(
        metadata.get(RecognizerResult.RECOGNIZER_NAME_KEY)
        or getattr(result.analysis_explanation, "recognizer", "")
    )
    if recognizer_name in {"SpacyRecognizer", "MedVaultSciSpacyRecognizer"}:
        return 0.5
    if recognizer_name.endswith("Recognizer"):
        return 1.0
    return 0.5


def _merge_exact(candidates: list[DetectionCandidate]) -> list[DetectionCandidate]:
    merged: dict[tuple[int, int, str], DetectionCandidate] = {}
    for candidate in candidates:
        key = (candidate.start, candidate.end, candidate.entity_type)
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue
        existing.detector_score = max(existing.detector_score, candidate.detector_score)
        existing.pattern_validation = max(existing.pattern_validation, candidate.pattern_validation)
        existing.context_boost = max(existing.context_boost, candidate.context_boost)
        existing.detector_sources.update(candidate.detector_sources)
        existing.trigger_reasons = list(
            dict.fromkeys(existing.trigger_reasons + candidate.trigger_reasons)
        )
    return list(merged.values())


def _remove_near_duplicate_overlaps(candidates: list[DetectionCandidate]) -> list[DetectionCandidate]:
    retained: list[DetectionCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.start, item.end, item.entity_type)):
        duplicate: DetectionCandidate | None = None
        for existing in retained:
            if existing.entity_type != candidate.entity_type:
                continue
            intersection = max(0, min(existing.end, candidate.end) - max(existing.start, candidate.start))
            shorter = min(existing.end - existing.start, candidate.end - candidate.start)
            if shorter and intersection / shorter >= 0.8:
                duplicate = existing
                break
        if duplicate is None:
            retained.append(candidate)
            continue
        winner, loser = (
            (candidate, duplicate)
            if (candidate.detector_score, candidate.end - candidate.start)
            > (duplicate.detector_score, duplicate.end - duplicate.start)
            else (duplicate, candidate)
        )
        winner.detector_sources.update(loser.detector_sources)
        winner.trigger_reasons = list(dict.fromkeys(winner.trigger_reasons + loser.trigger_reasons))
        if winner is candidate:
            retained[retained.index(duplicate)] = candidate
    return retained


class DetectionPipeline:
    def __init__(
        self,
        analyzer: AnalyzerProtocol | None = None,
        scispacy_recognizer: SciSpacyRecognizer | None = None,
        *,
        max_concurrent_chunks: int = 4,
        chunk_characters: int = DEFAULT_CHUNK_CHARACTERS,
    ) -> None:
        if not 1 <= max_concurrent_chunks <= 32:
            raise ValueError("max_concurrent_chunks must be between 1 and 32")
        using_default_ensemble = analyzer is None
        self.analyzer = analyzer or get_analyzer()
        self.scispacy_recognizer = (
            scispacy_recognizer
            if scispacy_recognizer is not None
            else (get_scispacy_recognizer() if using_default_ensemble else None)
        )
        self.max_concurrent_chunks = max_concurrent_chunks
        self.chunk_characters = chunk_characters

    def _results_to_candidates(
        self,
        results: list[RecognizerResult],
        chunk: TextChunk,
        full_text: str,
        structural_labels: list[str] | None,
        structural_contexts: list[StructuralContext] | None = None,
    ) -> list[DetectionCandidate]:
        candidates: list[DetectionCandidate] = []
        for result in results:
            start, end = result.start + chunk.start, result.end + chunk.start
            if start < 0 or end > len(full_text) or end <= start:
                continue
            local_labels = list(structural_labels or [])
            for context in structural_contexts or []:
                if context.start <= start < context.end:
                    local_labels.extend(context.labels)
            evidence = context_evidence(
                full_text,
                start,
                result.entity_type,
                structural_labels=local_labels,
            )
            pattern_validation = _pattern_validation_from_result(result)
            reasons = list(evidence.reasons)
            sources = {_source_from_result(result)}
            if evidence.score > 0:
                sources.add(DetectorSource.CONTEXT)
            if pattern_validation >= 0.85:
                reasons.append("matched a validated identifier format")
            candidates.append(
                DetectionCandidate(
                    entity_type=result.entity_type,
                    start=start,
                    end=end,
                    matched_text=full_text[start:end],
                    detector_score=float(result.score),
                    pattern_validation=pattern_validation,
                    context_boost=evidence.score,
                    detector_sources=sources,
                    trigger_reasons=reasons,
                )
            )
        return candidates

    def _analyze_presidio_chunk(
        self,
        chunk: TextChunk,
        full_text: str,
        structural_labels: list[str] | None,
        structural_contexts: list[StructuralContext] | None = None,
    ) -> list[DetectionCandidate]:
        results = self.analyzer.analyze(
            text=chunk.text,
            language="en",
            score_threshold=0.0,
            return_decision_process=True,
        )
        return self._results_to_candidates(
            results, chunk, full_text, structural_labels, structural_contexts
        )

    def _analyze_scispacy_chunk(
        self,
        chunk: TextChunk,
        full_text: str,
        structural_labels: list[str] | None,
        structural_contexts: list[StructuralContext] | None = None,
    ) -> list[DetectionCandidate]:
        if self.scispacy_recognizer is None:
            return []
        results = self.scispacy_recognizer.analyze(
            chunk.text,
            self.scispacy_recognizer.supported_entities,
        )
        return self._results_to_candidates(
            results, chunk, full_text, structural_labels, structural_contexts
        )

    async def analyze_document(
        self,
        text: str,
        mode: ModeConfig,
        *,
        structural_labels: list[str] | None = None,
        structural_contexts: list[StructuralContext] | None = None,
        subject_patient_id: str | None = None,
    ) -> list[DetectionCandidate]:
        if not text:
            return []
        chunks = chunk_text(text, max_characters=self.chunk_characters)
        semaphore = asyncio.Semaphore(self.max_concurrent_chunks)

        async def analyze_one(chunk: TextChunk) -> list[DetectionCandidate]:
            async with semaphore:
                presidio_results, scispacy_results = await asyncio.gather(
                    asyncio.to_thread(
                        self._analyze_presidio_chunk,
                        chunk,
                        text,
                        structural_labels,
                        structural_contexts,
                    ),
                    asyncio.to_thread(
                        self._analyze_scispacy_chunk,
                        chunk,
                        text,
                        structural_labels,
                        structural_contexts,
                    ),
                )
                return presidio_results + scispacy_results

        batches = await asyncio.gather(*(analyze_one(chunk) for chunk in chunks))
        merged = _remove_near_duplicate_overlaps(_merge_exact([item for batch in batches for item in batch]))
        for candidate in merged:
            score_candidate(candidate, mode, subject_patient_id=subject_patient_id)

        cached = self._propagate_document_cache(
            text,
            merged,
            mode,
            subject_patient_id=subject_patient_id,
        )
        combined = _merge_exact(merged + cached)
        return sorted(combined, key=lambda item: (item.start, item.end, item.entity_type))

    def _propagate_document_cache(
        self,
        text: str,
        candidates: list[DetectionCandidate],
        mode: ModeConfig,
        *,
        subject_patient_id: str | None,
    ) -> list[DetectionCandidate]:
        existing = {(candidate.start, candidate.end, candidate.entity_type) for candidate in candidates}
        additions: list[DetectionCandidate] = []
        cache: dict[tuple[str, str], DetectionCandidate] = {}
        for candidate in candidates:
            if candidate.decision == DetectionDecision.AUTO_REDACT and len(candidate.matched_text.strip()) >= 2:
                cache[(candidate.entity_type, candidate.matched_text)] = candidate
        for (entity_type, value), source in cache.items():
            escaped = re.escape(value)
            prefix = r"(?<!\w)" if value[0].isalnum() else ""
            suffix = r"(?!\w)" if value[-1].isalnum() else ""
            for match in re.finditer(f"{prefix}{escaped}{suffix}", text):
                key = (match.start(), match.end(), entity_type)
                if key in existing:
                    continue
                candidate = DetectionCandidate(
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    matched_text=match.group(0),
                    detector_score=source.detector_score,
                    pattern_validation=source.pattern_validation,
                    context_boost=source.context_boost,
                    detector_sources=set(source.detector_sources) | {DetectorSource.DOCUMENT_CACHE},
                    trigger_reasons=list(source.trigger_reasons) + ["matched a high-confidence document entity"],
                )
                score_candidate(candidate, mode, subject_patient_id=subject_patient_id)
                additions.append(candidate)
                existing.add(key)
        return additions
