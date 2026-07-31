from __future__ import annotations

from video_subtitle_pipeline.align import align_decision
from video_subtitle_pipeline.models import CleanedCue, SourceCue, WordTiming
from video_subtitle_pipeline.segment import SegmentationDecision


def test_aligns_semantic_groups_to_word_timings() -> None:
    source = SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=4_000, text="你好世界")
    cue = CleanedCue(source=source, speaker_label_removed_text="你好世界", cleaned_text="你好世界", llm_modified=False)
    decision = SegmentationDecision(
        source_id="1",
        source_index=0,
        text="你好世界",
        protected_spans=(),
        llm_offsets=(2,),
        accepted_offsets=(2,),
        fallback_offsets=(),
    )
    words = [
        WordTiming(text="你好", start_ms=100, end_ms=800, probability=0.9, segment_id=0),
        WordTiming(text="世界", start_ms=1_000, end_ms=1_800, probability=0.8, segment_id=0),
    ]

    groups = align_decision(cue, decision, words)

    assert [(group.start_ms, group.end_ms) for group in groups] == [(100, 800), (1_000, 1_800)]
    assert all(group.alignment_method == "word_timing" for group in groups)


def test_unmatched_group_uses_interpolation_and_review_reason() -> None:
    source = SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=2_000, text="不存在")
    cue = CleanedCue(source=source, speaker_label_removed_text="不存在", cleaned_text="不存在", llm_modified=False)
    decision = SegmentationDecision("1", 0, "不存在", (), (), (), ())

    group = align_decision(cue, decision, [])[0]

    assert group.alignment_method == "interpolation"
    assert "alignment_low_confidence" in group.review_reasons
