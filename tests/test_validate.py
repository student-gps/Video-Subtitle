from __future__ import annotations

from video_subtitle_pipeline.models import CleanedCue, ReadabilityConfig, SemanticGroup, SourceCue
from video_subtitle_pipeline.validate import validate_pipeline


def _cleaned(text: str) -> CleanedCue:
    source = SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=2_000, text=text)
    return CleanedCue(source=source, speaker_label_removed_text=text, cleaned_text=text, llm_modified=False)


def test_validation_accepts_text_conservation_and_non_overlap() -> None:
    groups = [
        SemanticGroup(
            group_id="1-1",
            source_ids=("1",),
            text="你好",
            start_offset=0,
            end_offset=2,
            start_ms=0,
            end_ms=1_000,
            alignment_method="word_timing",
            confidence=0.9,
        ),
        SemanticGroup(
            group_id="1-2",
            source_ids=("1",),
            text="世界",
            start_offset=2,
            end_offset=4,
            start_ms=1_001,
            end_ms=2_000,
            alignment_method="word_timing",
            confidence=0.9,
        ),
    ]

    report = validate_pipeline([_cleaned("你好世界")], groups, (), ReadabilityConfig())

    assert report["passed"] is True
    assert report["text_conservation"]["passed"] is True


def test_validation_rejects_changed_text() -> None:
    group = SemanticGroup(
        group_id="1-1",
        source_ids=("1",),
        text="你好",
        start_offset=0,
        end_offset=2,
        start_ms=0,
        end_ms=2_000,
        alignment_method="word_timing",
        confidence=0.9,
    )

    report = validate_pipeline([_cleaned("你好世界")], [group], (), ReadabilityConfig())

    assert report["passed"] is False
    assert report["issues"][0]["type"] == "text_conservation_failed"
