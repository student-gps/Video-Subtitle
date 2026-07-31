from __future__ import annotations

from video_subtitle_pipeline.srt_io import parse_srt, render_srt


def test_parse_and_render_srt_round_trip() -> None:
    cues = parse_srt(
        "7\n00:00:01,000 --> 00:00:02,500\n你好\n世界\n\n"
        "8\n00:00:03,000 --> 00:00:04,000\nClaude Code\n"
    )

    assert [cue.source_id for cue in cues] == ["7", "8"]
    assert cues[0].start_ms == 1_000
    assert cues[0].end_ms == 2_500
    assert render_srt(cues).startswith("1\n00:00:01,000 --> 00:00:02,500\n你好\n世界")
