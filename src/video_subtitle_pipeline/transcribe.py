from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from video_subtitle_pipeline.errors import DependencyError, PipelineError
from video_subtitle_pipeline.models import SourceCue, TranscriptionConfig, WordTiming


@dataclass(frozen=True)
class TranscriptionResult:
    cues: tuple[SourceCue, ...]
    words: tuple[WordTiming, ...]
    language: str | None
    language_probability: float | None
    runtime: dict[str, str | bool | None]
    low_confidence_words: tuple[WordTiming, ...]


def transcribe_audio(
    audio_path: str,
    config: TranscriptionConfig,
    glossary_terms: tuple[str, ...],
    model_factory: Callable[..., Any] | None = None,
) -> TranscriptionResult:
    factory = model_factory or _load_model_factory()
    selected_device, selected_compute_type, fallback = _select_runtime(config)
    try:
        return _run_transcription(
            factory,
            audio_path,
            config,
            glossary_terms,
            selected_device,
            selected_compute_type,
            fallback,
        )
    except Exception as exc:
        if config.device != "auto" or selected_device != "cuda":
            if isinstance(exc, PipelineError):
                raise
            raise PipelineError(f"本地转写失败：{exc}") from exc
        try:
            return _run_transcription(
                factory,
                audio_path,
                config,
                glossary_terms,
                "cpu",
                "int8",
                True,
            )
        except Exception as fallback_exc:
            raise PipelineError(f"GPU 转写失败且 CPU 回退失败：{fallback_exc}") from fallback_exc


def _load_model_factory() -> Callable[..., Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise DependencyError("未安装 faster-whisper。请运行 uv sync 后重试。") from exc
    return WhisperModel


def cuda_status() -> tuple[bool, str]:
    """返回 CTranslate2 能否为 Faster-Whisper 提供 CUDA 的检测结果。"""
    try:
        import ctranslate2

        compute_types = ctranslate2.get_supported_compute_types("cuda")
    except (ImportError, RuntimeError, ValueError, OSError) as exc:
        return False, f"不可用：{exc}"
    if not compute_types:
        return False, "不可用：未检测到 CUDA 计算类型。"
    return True, "可用计算类型：" + ", ".join(sorted(compute_types))


def _select_runtime(config: TranscriptionConfig) -> tuple[str, str, bool]:
    if config.device == "cpu":
        return "cpu", config.compute_type if config.compute_type != "auto" else "int8", False
    if config.device == "cuda":
        return "cuda", config.compute_type if config.compute_type != "auto" else "float16", False
    return "cuda", config.compute_type if config.compute_type != "auto" else "float16", False


def _run_transcription(
    factory: Callable[..., Any],
    audio_path: str,
    config: TranscriptionConfig,
    glossary_terms: tuple[str, ...],
    device: str,
    compute_type: str,
    fallback: bool,
) -> TranscriptionResult:
    model = factory(config.model, device=device, compute_type=compute_type)
    prompt = "；".join(glossary_terms) or None
    transcribe_kwargs = {
        "language": None if config.language in {None, "auto"} else config.language,
        "word_timestamps": True,
        "vad_filter": config.vad_filter,
    }
    if prompt:
        transcribe_kwargs["initial_prompt"] = prompt
    segments, info = model.transcribe(audio_path, **transcribe_kwargs)
    cues: list[SourceCue] = []
    words: list[WordTiming] = []
    for index, segment in enumerate(segments):
        text = segment.text.strip()
        start_ms = _seconds_to_ms(segment.start)
        end_ms = _seconds_to_ms(segment.end)
        if end_ms <= start_ms:
            continue
        cues.append(
            SourceCue(
                source_id=str(index + 1),
                source_index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            )
        )
        for word in segment.words or []:
            word_start = _seconds_to_ms(word.start)
            word_end = _seconds_to_ms(word.end)
            if word_end < word_start:
                continue
            words.append(
                WordTiming(
                    text=word.word.strip(),
                    start_ms=word_start,
                    end_ms=word_end,
                    probability=getattr(word, "probability", None),
                    segment_id=index,
                )
            )
    low_confidence = tuple(word for word in words if word.probability is not None and word.probability < 0.6)
    return TranscriptionResult(
        cues=tuple(cues),
        words=tuple(words),
        language=getattr(info, "language", None),
        language_probability=getattr(info, "language_probability", None),
        runtime={
            "model": config.model,
            "device": device,
            "compute_type": compute_type,
            "device_fallback": fallback,
        },
        low_confidence_words=low_confidence,
    )


def _seconds_to_ms(seconds: float) -> int:
    return max(0, round(seconds * 1_000))
