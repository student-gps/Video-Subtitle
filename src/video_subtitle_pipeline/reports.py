from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from video_subtitle_pipeline.io_utils import atomic_write_json
from video_subtitle_pipeline.models import CleanedCue, ReviewItem, SemanticGroup


def write_cleaning_report(path: Path, cues: Iterable[CleanedCue]) -> None:
    atomic_write_json(
        path,
        {
            "cues": [
                {
                    "source_cue_id": cue.source.source_id,
                    "source_index": cue.source.source_index,
                    "original_text": cue.source.text,
                    "speaker_label_removed_text": cue.speaker_label_removed_text,
                    "cleaned_text": cue.cleaned_text,
                    "llm_modified": cue.llm_modified,
                    "protected_terms_found": list(cue.protected_terms_found),
                }
                for cue in cues
            ]
        },
    )


def write_provenance_report(path: Path, groups: Iterable[SemanticGroup]) -> None:
    atomic_write_json(
        path,
        {
            "final_cues": [
                {
                    "final_cue_number": number,
                    "source_cue_ids": list(group.source_ids),
                    "group_id": group.group_id,
                    "text": group.text,
                    "start_ms": group.start_ms,
                    "end_ms": group.end_ms,
                    "alignment_method": group.alignment_method,
                    "confidence": group.confidence,
                }
                for number, group in enumerate(groups, start=1)
            ]
        },
    )


def collect_review_items(groups: Iterable[SemanticGroup], readability_reasons: dict[str, tuple[str, ...]]) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    for number, group in enumerate(groups, start=1):
        reasons = tuple(dict.fromkeys([*group.review_reasons, *readability_reasons.get(group.group_id, ())]))
        if reasons:
            items.append(
                ReviewItem(
                    final_cue_number=number,
                    start_ms=group.start_ms,
                    end_ms=group.end_ms,
                    text=group.text,
                    confidence=group.confidence,
                    reasons=reasons,
                )
            )
    return items


def write_review_report(path: Path, items: Iterable[ReviewItem]) -> None:
    atomic_write_json(path, {"items": [item.model_dump(mode="json") for item in items]})


def write_semantic_breaks(path: Path, decisions: Iterable[Any]) -> None:
    atomic_write_json(
        path,
        {
            "cues": [
                {
                    "source_cue_id": decision.source_id,
                    "source_index": decision.source_index,
                    "text": decision.text,
                    "protected_character_ranges": [list(span) for span in decision.protected_spans],
                    "llm_offsets": list(decision.llm_offsets),
                    "accepted_offsets": list(decision.accepted_offsets),
                    "fallback_offsets": list(decision.fallback_offsets),
                }
                for decision in decisions
            ]
        },
    )
