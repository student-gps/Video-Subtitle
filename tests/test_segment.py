from __future__ import annotations

import pytest

from video_subtitle_pipeline.errors import LLMResponseError
from video_subtitle_pipeline.models import CleanedCue, SegmentationConfig, SourceCue
from video_subtitle_pipeline.segment import segment_cue, split_text


class FakeLLM:
    def __init__(self, offsets: list[int]) -> None:
        self.offsets = offsets

    def request_json(self, _system_prompt: str, _payload: dict) -> dict:
        return {"break_after_character_offsets": self.offsets}


def _cue(text: str) -> CleanedCue:
    source = SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=5_000, text=text)
    return CleanedCue(source=source, speaker_label_removed_text=text, cleaned_text=text, llm_modified=False)


def test_segment_keeps_protected_term_whole() -> None:
    text = "我们使用 Claude Code 来处理字幕并保证输出准确"
    decision = segment_cue(_cue(text), ("Claude Code",), SegmentationConfig(), FakeLLM([3]))

    pieces = split_text(text, decision.accepted_offsets)

    assert "".join(piece[2] for piece in pieces) == text
    assert all(not (3 < offset < 14) for offset in decision.accepted_offsets)


def test_segment_rejects_break_inside_protected_term() -> None:
    text = "我们使用 Claude Code 来处理字幕"
    with pytest.raises(LLMResponseError):
        segment_cue(_cue(text), ("Claude Code",), SegmentationConfig(), FakeLLM([7]))
