from __future__ import annotations

import re
from dataclasses import dataclass

from video_subtitle_pipeline.models import ReadabilityConfig, SemanticGroup

_CHINESE_RE = re.compile(r"[㐀-鿿豈-﫿]")
_ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")


@dataclass(frozen=True)
class ReadabilityMetrics:
    chinese_characters: int
    english_words: int
    duration_seconds: float
    load_per_second: float
    reasons: tuple[str, ...]


def assess_text(text: str, duration_ms: int, config: ReadabilityConfig) -> ReadabilityMetrics:
    duration_seconds = duration_ms / 1_000
    chinese_characters = len(_CHINESE_RE.findall(text))
    english_words = len(_ENGLISH_WORD_RE.findall(text))
    load = (chinese_characters / config.chinese_chars_per_second) + (
        english_words / config.english_words_per_second
    )
    rate = load / duration_seconds if duration_seconds > 0 else float("inf")
    reasons: list[str] = []
    if duration_seconds < config.min_duration_seconds:
        reasons.append("display_duration_below_minimum")
    if rate > 1:
        reasons.append("reading_speed_exceeded")
    if 0 < chinese_characters < config.min_chinese_chars:
        reasons.append("short_fragment")
    if chinese_characters > config.preferred_chinese_chars_max:
        reasons.append("preferred_length_exceeded")
    return ReadabilityMetrics(
        chinese_characters=chinese_characters,
        english_words=english_words,
        duration_seconds=duration_seconds,
        load_per_second=rate,
        reasons=tuple(reasons),
    )


def assess_group(group: SemanticGroup, config: ReadabilityConfig) -> ReadabilityMetrics:
    return assess_text(group.text, group.end_ms - group.start_ms, config)
