from __future__ import annotations

from video_subtitle_pipeline.models import ReadabilityConfig
from video_subtitle_pipeline.readability import assess_text


def test_mixed_text_reading_load_is_flagged() -> None:
    metrics = assess_text("这是一个很长的字幕 Claude Code tutorial", 500, ReadabilityConfig())

    assert metrics.chinese_characters > 0
    assert metrics.english_words == 3
    assert "display_duration_below_minimum" in metrics.reasons
    assert "reading_speed_exceeded" in metrics.reasons
