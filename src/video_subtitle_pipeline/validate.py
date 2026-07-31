from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from video_subtitle_pipeline.models import CleanedCue, ReadabilityConfig, SemanticGroup
from video_subtitle_pipeline.readability import assess_group


def validate_pipeline(
    cleaned_cues: Iterable[CleanedCue],
    groups: Iterable[SemanticGroup],
    terms: tuple[str, ...],
    readability: ReadabilityConfig,
) -> dict[str, Any]:
    cleaned = list(cleaned_cues)
    final_groups = list(groups)
    expected_text = "".join(cue.cleaned_text for cue in sorted(cleaned, key=lambda item: (item.source.start_ms, item.source.end_ms, item.source.source_index)))
    actual_text = "".join(group.text for group in final_groups)
    issues: list[dict[str, Any]] = []
    if expected_text != actual_text:
        issues.append({"type": "text_conservation_failed", "expected": expected_text, "actual": actual_text})

    expected_by_source: dict[str, str] = {}
    for cue in cleaned:
        expected_by_source[cue.source.source_id] = (
            expected_by_source.get(cue.source.source_id, "") + cue.cleaned_text
        )
    actual_by_source: dict[str, str] = {}
    for group in final_groups:
        for source_id in group.source_ids:
            actual_by_source[source_id] = actual_by_source.get(source_id, "") + group.text
    for source_id, source_text in expected_by_source.items():
        final_text = actual_by_source.get(source_id, "")
        for term in terms:
            if source_text.count(term) > final_text.count(term):
                issues.append(
                    {
                        "type": "protected_term_missing",
                        "source_cue_id": source_id,
                        "term": term,
                    }
                )

    previous_end = -1
    for number, group in enumerate(final_groups, start=1):
        if group.end_ms <= group.start_ms:
            issues.append({"type": "invalid_interval", "cue_number": number})
        if group.start_ms <= previous_end:
            issues.append({"type": "overlap_or_non_increasing_time", "cue_number": number})
        previous_end = group.end_ms
        metrics = assess_group(group, readability)
        for reason in metrics.reasons:
            issues.append({"type": reason, "cue_number": number})

    confidences = [group.confidence for group in final_groups if group.confidence is not None]
    return {
        "passed": not any(issue["type"] in {"text_conservation_failed", "invalid_interval", "overlap_or_non_increasing_time"} for issue in issues),
        "text_conservation": {"passed": expected_text == actual_text},
        "time_validity": {
            "passed": not any(issue["type"] in {"invalid_interval", "overlap_or_non_increasing_time"} for issue in issues),
            "final_cue_count": len(final_groups),
        },
        "alignment_quality": {
            "high_confidence_count": sum(value >= 0.85 for value in confidences),
            "medium_confidence_count": sum(0.6 <= value < 0.85 for value in confidences),
            "low_confidence_count": sum(value < 0.6 for value in confidences)
            + sum(group.confidence is None for group in final_groups),
            "interpolated_boundary_count": sum(group.alignment_method == "interpolation" for group in final_groups),
            "readability_review_count": sum(
                bool(assess_group(group, readability).reasons) for group in final_groups
            ),
        },
        "issues": issues,
    }
