"""Shared extracted text, layout, and source-location contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.detection.types import DetectionCandidate, StructuralContext


@dataclass(frozen=True, slots=True)
class LayoutToken:
    text: str
    start: int
    end: int
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    locator: str | None = None
    local_start: int = 0
    local_end: int | None = None
    source: str = "native"

    def overlaps(self, candidate: DetectionCandidate) -> bool:
        return self.start < candidate.end and self.end > candidate.start


@dataclass(slots=True)
class ExtractedDocument:
    text: str
    tokens: list[LayoutToken]
    structural_contexts: list[StructuralContext] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    preclassified_candidates: list[DetectionCandidate] = field(default_factory=list)

    def tokens_for(self, candidate: DetectionCandidate) -> list[LayoutToken]:
        return [token for token in self.tokens if token.overlaps(candidate)]

    def bbox_for(self, candidate: DetectionCandidate) -> tuple[int | None, tuple[float, float, float, float] | None]:
        tokens = [token for token in self.tokens_for(candidate) if token.bbox is not None]
        if not tokens:
            return candidate.page_number, None
        page = tokens[0].page_number
        same_page = [token for token in tokens if token.page_number == page]
        return page, (
            min(token.bbox[0] for token in same_page),
            min(token.bbox[1] for token in same_page),
            max(token.bbox[2] for token in same_page),
            max(token.bbox[3] for token in same_page),
        )
