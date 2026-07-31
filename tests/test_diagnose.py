from __future__ import annotations

from video_subtitle_pipeline.diagnose import diagnose_inputs
from video_subtitle_pipeline.models import ReadabilityConfig


def test_diagnose_reports_duplicate_order_and_overlap(tmp_path) -> None:
    srt = tmp_path / "input.srt"
    srt.write_text(
        "1\n00:00:02,000 --> 00:00:03,000\n第一条\n\n"
        "1\n00:00:01,500 --> 00:00:02,500\n第二条\n",
        encoding="utf-8",
    )
    video = tmp_path / "video.mp4"
    video.write_bytes(b"placeholder")

    _, report = diagnose_inputs(video, srt, ReadabilityConfig(), {"audio_stream_count": 1})

    issue_types = {item["type"] for item in report["issues"]}
    assert {"duplicate_cue_id", "timestamp_regression", "adjacent_overlap", "source_order_differs_from_time_order"} <= issue_types
