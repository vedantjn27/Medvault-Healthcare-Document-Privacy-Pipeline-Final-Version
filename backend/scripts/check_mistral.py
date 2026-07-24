"""Validate configured Mistral review using synthetic, non-patient text only."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.mistral_agent import MistralPrivacyAgent
from app.config import Settings
from app.db.models import PrivacyMode
from app.detection.types import DetectionCandidate, DetectionDecision, DetectorSource
from app.redaction.confidence import score_candidate
from app.redaction.mode_configs import get_mode_config


async def main() -> None:
    settings = Settings()
    if settings.mistral_api_key is None:
        print("Mistral is optional and not configured")
        return
    text = "Synthetic benchmark patient name: Example Person. This is not a real record."
    start = text.index("Example Person")
    candidate = DetectionCandidate(
        entity_type="PERSON", start=start, end=start + len("Example Person"),
        matched_text="Example Person", detector_score=0.75,
        pattern_validation=0.7, context_boost=0.45,
    )
    mode = get_mode_config(PrivacyMode.RESEARCH_SHARING)
    score_candidate(candidate, mode)
    if candidate.decision != DetectionDecision.AMBIGUITY_REVIEW:
        raise RuntimeError("Synthetic validation candidate is not ambiguous")
    agent = MistralPrivacyAgent(settings)
    try:
        diagnostic = await agent._json_call(
            "Return JSON only with keys is_phi, entity_type, confidence, reasoning. "
            "Never repeat the supplied span in reasoning.",
            {"span": "Example Person", "context_before": "Synthetic name", "context_after": "not real"},
        )
    except Exception as exc:
        raise RuntimeError(f"Mistral request failed ({type(exc).__name__}: {exc})") from exc
    if not {"is_phi", "entity_type", "confidence", "reasoning"}.issubset(diagnostic):
        raise RuntimeError("Mistral diagnostic response did not match the required schema")
    await agent.enrich([candidate], text, mode)
    if DetectorSource.MISTRAL not in candidate.detector_sources:
        raise RuntimeError("Configured Mistral review did not return a valid response")
    if not candidate.explanation_text or "Example Person" in candidate.explanation_text:
        raise RuntimeError("Mistral explanation privacy validation failed")
    print("Mistral synthetic validation passed")


if __name__ == "__main__":
    asyncio.run(main())
