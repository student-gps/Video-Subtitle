from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from video_subtitle_pipeline import __version__
from video_subtitle_pipeline.align import align_decision, ensure_monotonic_non_overlapping
from video_subtitle_pipeline.clean import clean_cues
from video_subtitle_pipeline.config import safe_config_dump
from video_subtitle_pipeline.diagnose import diagnose_inputs
from video_subtitle_pipeline.errors import PipelineError
from video_subtitle_pipeline.ffmpeg import extract_audio, probe_video
from video_subtitle_pipeline.glossary import load_glossary
from video_subtitle_pipeline.io_utils import atomic_write_json, file_metadata, sha256_file
from video_subtitle_pipeline.models import (
    PipelineConfig,
    RunInput,
    RunManifest,
    SemanticGroup,
    SourceCue,
)
from video_subtitle_pipeline.paths import artifact_path, work_directory
from video_subtitle_pipeline.readability import assess_group
from video_subtitle_pipeline.reports import (
    collect_review_items,
    write_cleaning_report,
    write_provenance_report,
    write_review_report,
    write_semantic_breaks,
)
from video_subtitle_pipeline.segment import segment_cue
from video_subtitle_pipeline.srt_io import render_srt
from video_subtitle_pipeline.transcribe import TranscriptionResult, transcribe_audio
from video_subtitle_pipeline.validate import validate_pipeline

ProgressCallback = Callable[[str], None]


class SubtitlePipeline:
    def __init__(
        self,
        config: PipelineConfig,
        llm: Any,
        progress: ProgressCallback | None = None,
        transcriber: Callable[..., TranscriptionResult] = transcribe_audio,
    ) -> None:
        self.config = config
        self.llm = llm
        self.progress = progress or (lambda _: None)
        self.transcriber = transcriber
        self._stage = "initialization"

    def process(self, run_input: RunInput, keep_workdir: bool = False) -> RunManifest:
        self._validate_input(run_input)
        manifest = self._create_manifest(run_input)
        manifest_path = artifact_path(run_input.output, "manifest")
        self._write_manifest(manifest_path, manifest)
        try:
            self._set_stage("diagnose", "正在诊断视频与字幕输入…")
            video_metadata = probe_video(run_input.video)
            source_cues, diagnosis = diagnose_inputs(
                run_input.video,
                run_input.srt,
                self.config.readability,
                video_metadata,
            )
            atomic_write_json(artifact_path(run_input.output, "diagnostic"), diagnosis)

            self._set_stage("glossary", "正在加载术语表…")
            terms = load_glossary(run_input.glossary)

            self._set_stage("transcribe", "正在提取本地音频并生成词级时间轴…")
            audio_path = work_directory(run_input.output) / "audio.wav"
            extract_audio(run_input.video, audio_path)
            transcription = self.transcriber(
                str(audio_path), self.config.transcription, terms
            )
            self._write_transcription_artifacts(run_input.output, transcription, not bool(run_input.srt))
            manifest.transcription = dict(transcription.runtime)

            baseline_cues = source_cues if run_input.srt else list(transcription.cues)
            if not baseline_cues:
                raise PipelineError("没有可用于生成字幕的文本基线。")

            self._set_stage("clean", "正在调用 LLM 清洗字幕文本…")
            cleaned_cues = clean_cues(baseline_cues, terms, self.llm)
            self._write_cleaned_artifacts(run_input.output, cleaned_cues)

            self._set_stage("segment", "正在按真实时间排序并调用 LLM 建议语义切点…")
            ordered_cues = sorted(
                cleaned_cues,
                key=lambda item: (item.source.start_ms, item.source.end_ms, item.source.source_index),
            )
            decisions = [
                segment_cue(cue, terms, self.config.segmentation, self.llm)
                for cue in ordered_cues
            ]
            write_semantic_breaks(artifact_path(run_input.output, "semantic_breaks"), decisions)

            self._set_stage("align", "正在使用本地词级时间重新对齐字幕…")
            groups: list[SemanticGroup] = []
            for cue, decision in zip(ordered_cues, decisions, strict=True):
                groups.extend(align_decision(cue, decision, transcription.words))
            groups = ensure_monotonic_non_overlapping(groups)

            self._set_stage("finalize", "正在检查可读性、生成最终字幕与报告…")
            self._write_final_artifacts(run_input.output, ordered_cues, groups, terms)
            manifest.status = "completed"
            manifest.failed_stage = None
            manifest.error = None
        except Exception as exc:
            manifest.status = "failed"
            manifest.failed_stage = self._current_stage_message()
            manifest.error = str(exc)
            self._refresh_artifacts(manifest, run_input.output)
            self._write_manifest(manifest_path, manifest)
            if isinstance(exc, PipelineError):
                raise
            raise PipelineError(f"处理失败：{exc}") from exc
        finally:
            if not keep_workdir:
                shutil.rmtree(work_directory(run_input.output), ignore_errors=True)
        self._refresh_artifacts(manifest, run_input.output)
        self._write_manifest(manifest_path, manifest)
        return manifest

    def _set_stage(self, name: str, message: str) -> None:
        self._stage = name
        self.progress(message)

    def _current_stage_message(self) -> str:
        return self._stage

    def _validate_input(self, run_input: RunInput) -> None:
        if not run_input.video.is_file():
            raise PipelineError(f"未找到视频文件：{run_input.video}")
        if run_input.srt is not None and not run_input.srt.is_file():
            raise PipelineError(f"未找到 SRT 文件：{run_input.srt}")
        if run_input.glossary is not None and not run_input.glossary.is_file():
            raise PipelineError(f"未找到术语表：{run_input.glossary}")

    def _create_manifest(self, run_input: RunInput) -> RunManifest:
        inputs: dict[str, dict[str, str | int | None]] = {"video": file_metadata(run_input.video)}
        if run_input.srt:
            inputs["srt"] = file_metadata(run_input.srt)
        if run_input.glossary:
            inputs["glossary"] = file_metadata(run_input.glossary)
        return RunManifest(
            tool_version=__version__,
            status="running",
            inputs=inputs,
            effective_config=safe_config_dump(self.config),
        )

    def _write_manifest(self, path: Path, manifest: RunManifest) -> None:
        atomic_write_json(path, manifest.model_dump(mode="json"))

    def _refresh_artifacts(self, manifest: RunManifest, output: Path) -> None:
        artifacts: dict[str, dict[str, str | int]] = {}
        for path in output.iterdir():
            if path.is_file() and path.name != artifact_path(output, "manifest").name:
                artifacts[path.name] = {
                    "relative_path": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
        manifest.artifacts = artifacts

    def _write_transcription_artifacts(
        self, output: Path, transcription: TranscriptionResult, write_baseline_srt: bool
    ) -> None:
        atomic_write_json(
            artifact_path(output, "word_timeline"),
            {
                "words": [word.model_dump(mode="json") for word in transcription.words],
                "runtime": transcription.runtime,
            },
        )
        if not write_baseline_srt:
            return
        artifact_path(output, "transcription_srt").write_text(
            render_srt(transcription.cues), encoding="utf-8", newline="\n"
        )
        atomic_write_json(
            artifact_path(output, "transcription_report"),
            {
                "model": transcription.runtime["model"],
                "device": transcription.runtime["device"],
                "compute_type": transcription.runtime["compute_type"],
                "device_fallback": transcription.runtime["device_fallback"],
                "language": transcription.language,
                "language_probability": transcription.language_probability,
                "caption_count": len(transcription.cues),
                "low_confidence_words": [
                    word.model_dump(mode="json") for word in transcription.low_confidence_words
                ],
                "empty_or_invalid_segment_count": 0,
            },
        )

    def _write_cleaned_artifacts(self, output: Path, cues: list[Any]) -> None:
        cleaned_source_cues = [
            cue.source.model_copy(update={"text": cue.cleaned_text}) for cue in cues
        ]
        artifact_path(output, "cleaned_srt").write_text(
            render_srt(cleaned_source_cues), encoding="utf-8", newline="\n"
        )
        write_cleaning_report(artifact_path(output, "clean_report"), cues)

    def _write_final_artifacts(
        self,
        output: Path,
        ordered_cues: list[Any],
        groups: list[SemanticGroup],
        terms: tuple[str, ...],
    ) -> None:
        final_cues = [
            SourceCue(
                source_id=str(index),
                source_index=index - 1,
                start_ms=group.start_ms,
                end_ms=group.end_ms,
                text=group.text,
            )
            for index, group in enumerate(groups, start=1)
        ]
        artifact_path(output, "final_srt").write_text(
            render_srt(final_cues), encoding="utf-8", newline="\n"
        )
        readability_reasons = {
            group.group_id: assess_group(group, self.config.readability).reasons for group in groups
        }
        review_items = collect_review_items(groups, readability_reasons)
        write_review_report(artifact_path(output, "review"), review_items)
        write_provenance_report(artifact_path(output, "provenance"), groups)
        report = validate_pipeline(ordered_cues, groups, terms, self.config.readability)
        atomic_write_json(artifact_path(output, "validation"), report)
