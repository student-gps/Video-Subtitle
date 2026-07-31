from __future__ import annotations

from dataclasses import dataclass

from video_subtitle_pipeline.models import PipelineConfig, RunInput, SourceCue, WordTiming
from video_subtitle_pipeline.paths import prepare_output_directory
from video_subtitle_pipeline.pipeline import SubtitlePipeline
from video_subtitle_pipeline.transcribe import TranscriptionResult


@dataclass
class FakeLLM:
    def request_json(self, _system_prompt: str, payload: dict) -> dict:
        if payload["task"] == "clean_subtitles":
            return {
                "cues": [
                    {"cue_key": cue["cue_key"], "cleaned_text": cue["text"].replace("嗯，", "")}
                    for cue in payload["cues"]
                ]
            }
        return {"break_after_character_offsets": []}


def fake_transcriber(*_args) -> TranscriptionResult:
    words = (
        WordTiming(text="我们", start_ms=0, end_ms=500, probability=0.9, segment_id=0),
        WordTiming(text="使用", start_ms=600, end_ms=1_000, probability=0.9, segment_id=0),
        WordTiming(text="BMAD", start_ms=1_100, end_ms=1_700, probability=0.9, segment_id=0),
    )
    return TranscriptionResult(
        cues=(SourceCue(source_id="1", source_index=0, start_ms=0, end_ms=2_000, text="我们使用BMAD"),),
        words=words,
        language="zh",
        language_probability=0.99,
        runtime={"model": "fake", "device": "cpu", "compute_type": "int8", "device_fallback": True},
        low_confidence_words=(),
    )


def test_pipeline_generates_all_artifacts_without_source_srt(monkeypatch, tmp_path) -> None:
    import video_subtitle_pipeline.pipeline as pipeline_module

    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    output = prepare_output_directory(tmp_path / "out", overwrite=False)
    monkeypatch.setattr(pipeline_module, "probe_video", lambda _: {"audio_stream_count": 1})
    monkeypatch.setattr(pipeline_module, "extract_audio", lambda _video, target: target)

    manifest = SubtitlePipeline(
        PipelineConfig(),
        FakeLLM(),
        transcriber=fake_transcriber,
    ).process(RunInput(video=video, output=output))

    assert manifest.status == "completed"
    assert (output / "02_原始转写.srt").is_file()
    assert (output / "05_意群逐句对齐.srt").is_file()
    assert (output / "05_校验报告.json").is_file()
    assert (output / "pipeline_manifest.json").is_file()
    assert video.read_bytes() == b"video"
