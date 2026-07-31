from __future__ import annotations

from video_subtitle_pipeline.models import SourceCue, TranscriptionConfig, WordTiming
from video_subtitle_pipeline.transcribe import transcribe_audio


class FakeWord:
    def __init__(self, word: str, start: float, end: float, probability: float) -> None:
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class FakeSegment:
    text = "你好"
    start = 0.0
    end = 1.0
    words = [FakeWord("你好", 0.0, 1.0, 0.9)]


class FakeInfo:
    language = "zh"
    language_probability = 0.99


class FakeModel:
    def __init__(self, _model: str, device: str, compute_type: str) -> None:
        if device == "cuda":
            raise RuntimeError("CUDA unavailable")
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, *_args, **_kwargs):
        return iter([FakeSegment()]), FakeInfo()


def test_auto_device_falls_back_to_cpu() -> None:
    result = transcribe_audio("audio.wav", TranscriptionConfig(), (), model_factory=FakeModel)

    assert result.runtime["device"] == "cpu"
    assert result.runtime["compute_type"] == "int8"
    assert result.runtime["device_fallback"] is True
    assert result.cues == (SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=1_000, text="你好"),)
    assert result.words == (WordTiming(text="你好", start_ms=0, end_ms=1_000, probability=0.9, segment_id=0),)
