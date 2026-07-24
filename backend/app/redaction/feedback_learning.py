"""Bounded, user-local detector calibration derived from explicit feedback."""

from __future__ import annotations

from beanie import PydanticObjectId

from app.db.models import Feedback, FeedbackVerdict, RedactionEntity


async def feedback_adjustments(user_id: PydanticObjectId) -> dict[str, float]:
    """Return bounded score deltas; no raw sensitive values are learned or stored."""

    records = await Feedback.find(Feedback.user_id == user_id).to_list()
    totals: dict[str, list[int]] = {}
    for record in records:
        entity_type = record.entity_type
        if entity_type is None and record.entity_id is not None:
            entity = await RedactionEntity.get(record.entity_id)
            entity_type = entity.entity_type if entity else None
        if not entity_type:
            continue
        correct, false_positive, missed = totals.setdefault(entity_type, [0, 0, 0])
        if record.verdict == FeedbackVerdict.CORRECT:
            correct += 1
        elif record.verdict == FeedbackVerdict.FALSE_POSITIVE:
            false_positive += 1
        else:
            missed += 1
        totals[entity_type] = [correct, false_positive, missed]
    adjustments: dict[str, float] = {}
    for entity_type, (correct, false_positive, missed) in totals.items():
        evidence = correct + false_positive + missed
        # Laplace smoothing and a hard ±0.10 cap prevent feedback poisoning.
        delta = 0.10 * ((correct + missed + 1) - (false_positive + 1)) / (evidence + 2)
        adjustments[entity_type] = round(max(-0.10, min(0.10, delta)), 6)
    return adjustments


def apply_feedback_adjustments(candidates, adjustments: dict[str, float], mode, subject_patient_id=None):
    from app.redaction.confidence import score_candidate

    for candidate in candidates:
        delta = adjustments.get(candidate.entity_type, 0.0)
        if delta:
            candidate.detector_score = max(0.0, min(1.0, candidate.detector_score + delta))
            candidate.trigger_reasons.append("confidence calibrated from prior user feedback")
            score_candidate(candidate, mode, subject_patient_id=subject_patient_id)
