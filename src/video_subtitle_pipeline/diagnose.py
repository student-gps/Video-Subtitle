from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from video_subtitle_pipeline.models import ReadabilityConfig, SourceCue
from video_subtitle_pipeline.readability import assess_text
from video_subtitle_pipeline.srt_io import read_srt


def diagnose_inputs(
    video: Path,
    srt: Path | None,
    readability: ReadabilityConfig,
    video_metadata: dict[str, Any] | None,
) -> tuple[list[SourceCue], dict[str, Any]]:
    cues = read_srt(str(srt)) if srt else []
    issue_items: list[dict[str, Any]] = []
    if video_metadata is not None and video_metadata.get("audio_stream_count", 0) == 0:
        issue_items.append({"type": "video_has_no_audio_stream"})

    ids = Counter(cue.source_id for cue in cues)
    for source_id, count in ids.items():
        if count > 1:
            issue_items.append({"type": "duplicate_cue_id", "source_id": source_id, "count": count})

    previous: SourceCue | None = None
    chronological_indexes = [cue.source_index for cue in sorted(cues, key=lambda cue: (cue.start_ms, cue.end_ms))]
    for cue in cues:
        if not cue.text.strip():
            issue_items.append({"type": "empty_cue", "source_id": cue.source_id})
        metrics = assess_text(cue.text, cue.end_ms - cue.start_ms, readability)
        for reason in metrics.reasons:
            issue_items.append(
                {
                    "type": reason,
                    "source_id": cue.source_id,
                    "duration_seconds": round(metrics.duration_seconds, 3),
                    "reading_load_per_second": round(metrics.load_per_second, 3),
                }
            )
        if previous is not None:
            if cue.start_ms < previous.start_ms:
                issue_items.append(
                    {
                        "type": "timestamp_regression",
                        "source_id": cue.source_id,
                        "previous_source_id": previous.source_id,
                    }
                )
            if cue.start_ms < previous.end_ms:
                issue_items.append(
                    {
                        "type": "adjacent_overlap",
                        "source_id": cue.source_id,
                        "previous_source_id": previous.source_id,
                        "overlap_ms": previous.end_ms - cue.start_ms,
                    }
                )
        previous = cue

    if chronological_indexes != list(range(len(cues))):
        issue_items.append({"type": "source_order_differs_from_time_order"})

    report = {
        "video": {
            "path": str(video.resolve()),
            "exists": video.is_file(),
            "metadata": video_metadata,
        },
        "srt": {
            "path": str(srt.resolve()) if srt else None,
            "provided": srt is not None,
            "cue_count": len(cues),
        },
        "issues": issue_items,
        "issue_count": len(issue_items),
    }
    return cues, report
