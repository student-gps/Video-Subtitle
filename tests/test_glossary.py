from __future__ import annotations

import pytest

from video_subtitle_pipeline.errors import LLMResponseError
from video_subtitle_pipeline.glossary import protected_spans
from video_subtitle_pipeline.llm import expect_offsets


def test_protected_spans_prefer_longest_term() -> None:
    assert protected_spans("使用 Claude Code 编写代码", ("Claude", "Claude Code")) == ((3, 14),)


def test_offsets_reject_duplicate_and_out_of_range_values() -> None:
    with pytest.raises(LLMResponseError):
        expect_offsets({"break_after_character_offsets": [2, 2]}, 5)
