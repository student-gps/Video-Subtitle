from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SourceCue(BaseModel, frozen=True):
    source_id: str
    source_index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str

    @model_validator(mode="after")
    def validate_interval(self) -> SourceCue:
        if self.end_ms <= self.start_ms:
            raise ValueError("字幕结束时间必须晚于开始时间")
        return self


class WordTiming(BaseModel, frozen=True):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    probability: float | None = Field(default=None, ge=0, le=1)
    segment_id: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_interval(self) -> WordTiming:
        if self.end_ms < self.start_ms:
            raise ValueError("词级时间结束不得早于开始")
        return self


class CleanedCue(BaseModel, frozen=True):
    source: SourceCue
    speaker_label_removed_text: str
    cleaned_text: str
    llm_modified: bool
    protected_terms_found: tuple[str, ...] = ()


class SemanticGroup(BaseModel, frozen=True):
    group_id: str
    source_ids: tuple[str, ...]
    text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    alignment_method: Literal["word_timing", "interpolation"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_interval(self) -> SemanticGroup:
        if self.end_ms <= self.start_ms:
            raise ValueError("意群结束时间必须晚于开始时间")
        return self


class ReviewItem(BaseModel, frozen=True):
    final_cue_number: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    reasons: tuple[str, ...]


class TranscriptionConfig(BaseModel, frozen=True):
    model: str = "small"
    language: str | None = "zh"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    compute_type: str = "auto"
    vad_filter: bool = True


class LLMConfig(BaseModel, frozen=True):
    base_url: str | None = None
    base_url_env: str = "OPENAI_BASE_URL"
    api_key_env: str = "OPENAI_API_KEY"
    model: str | None = None
    model_env: str = "OPENAI_MODEL"
    timeout_seconds: float = Field(default=90, gt=0)


class ReadabilityConfig(BaseModel, frozen=True):
    min_duration_seconds: float = Field(default=1.0, gt=0)
    chinese_chars_per_second: float = Field(default=6.0, gt=0)
    english_words_per_second: float = Field(default=2.5, gt=0)
    min_chinese_chars: int = Field(default=5, ge=1)
    preferred_chinese_chars_min: int = Field(default=10, ge=1)
    preferred_chinese_chars_max: int = Field(default=26, ge=1)


class SegmentationConfig(BaseModel, frozen=True):
    max_lines: int = Field(default=2, ge=1)
    pause_threshold_seconds: float = Field(default=0.35, ge=0)


class PipelineConfig(BaseModel, frozen=True):
    transcription: TranscriptionConfig = TranscriptionConfig()
    llm: LLMConfig = LLMConfig()
    readability: ReadabilityConfig = ReadabilityConfig()
    segmentation: SegmentationConfig = SegmentationConfig()


class RunInput(BaseModel, frozen=True):
    video: Path
    output: Path
    srt: Path | None = None
    glossary: Path | None = None


class RunManifest(BaseModel):
    tool_version: str
    status: Literal["running", "completed", "failed"]
    inputs: dict[str, dict[str, str | int | None]]
    effective_config: dict
    artifacts: dict[str, dict[str, str | int]] = Field(default_factory=dict)
    transcription: dict[str, str | bool | None] = Field(default_factory=dict)
    failed_stage: str | None = None
    error: str | None = None
