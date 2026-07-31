from __future__ import annotations

from video_subtitle_pipeline.clean import clean_cues, remove_leading_speaker_label
from video_subtitle_pipeline.models import SourceCue


class FakeLLM:
    def request_json(self, _system_prompt: str, payload: dict) -> dict:
        return {
            "cues": [
                {"cue_key": cue["cue_key"], "cleaned_text": cue["text"].replace("嗯，", "")}
                for cue in payload["cues"]
            ]
        }


def test_remove_only_leading_speaker_label() -> None:
    assert remove_leading_speaker_label("张三：大家好，张三稍后补充") == "大家好，张三稍后补充"
    assert remove_leading_speaker_label("今天由张三介绍") == "今天由张三介绍"


def test_clean_cues_keeps_protected_term() -> None:
    cue = SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=2_000, text="张三：嗯，Claude Code 很好")

    cleaned = clean_cues([cue], ("Claude Code",), FakeLLM())

    assert cleaned[0].cleaned_text == "Claude Code 很好"
    assert cleaned[0].protected_terms_found == ("Claude Code",)
