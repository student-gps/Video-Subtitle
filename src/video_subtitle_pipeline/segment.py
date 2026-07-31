from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from video_subtitle_pipeline.errors import LLMResponseError
from video_subtitle_pipeline.glossary import protected_spans
from video_subtitle_pipeline.llm import SEGMENTATION_SYSTEM_PROMPT, expect_offsets
from video_subtitle_pipeline.models import CleanedCue, SegmentationConfig


class JsonRequester(Protocol):
    def request_json(self, system_prompt: str, payload: dict) -> dict: ...


_BREAK_CHARS = set("，。！？；：、,.!?;:\n ")
_CJK_RE = re.compile(r"[㐀-鿿豈-﫿]")


@dataclass(frozen=True)
class SegmentationDecision:
    source_id: str
    source_index: int
    text: str
    protected_spans: tuple[tuple[int, int], ...]
    llm_offsets: tuple[int, ...]
    accepted_offsets: tuple[int, ...]
    fallback_offsets: tuple[int, ...]


def segment_cue(
    cue: CleanedCue,
    terms: tuple[str, ...],
    config: SegmentationConfig,
    llm: JsonRequester,
) -> SegmentationDecision:
    text = cue.cleaned_text
    spans = protected_spans(text, terms)
    if len(text) < 2:
        return SegmentationDecision(
            source_id=cue.source.source_id,
            source_index=cue.source.source_index,
            text=text,
            protected_spans=spans,
            llm_offsets=(),
            accepted_offsets=(),
            fallback_offsets=(),
        )
    response = llm.request_json(
        SEGMENTATION_SYSTEM_PROMPT,
        {
            "task": "suggest_semantic_breaks",
            "text": text,
            "protected_character_ranges": [list(span) for span in spans],
            "maximum_preferred_chinese_characters": 26,
        },
    )
    llm_offsets = expect_offsets(response, len(text))
    if any(_inside_protected_span(offset, spans) for offset in llm_offsets):
        raise LLMResponseError(f"LLM 在受保护术语内部建议切分：源 cue {cue.source.source_id}")
    accepted = set(llm_offsets)
    fallback: list[int] = []
    boundaries = [0, *sorted(accepted), len(text)]
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
        for offset in _fallback_offsets(text, start, end, spans):
            accepted.add(offset)
            fallback.append(offset)
    return SegmentationDecision(
        source_id=cue.source.source_id,
        source_index=cue.source.source_index,
        text=text,
        protected_spans=spans,
        llm_offsets=llm_offsets,
        accepted_offsets=tuple(sorted(accepted)),
        fallback_offsets=tuple(sorted(fallback)),
    )


def split_text(text: str, offsets: tuple[int, ...]) -> list[tuple[int, int, str]]:
    positions = [0, *offsets, len(text)]
    return [
        (start, end, text[start:end])
        for start, end in zip(positions[:-1], positions[1:], strict=True)
        if text[start:end]
    ]


def _fallback_offsets(
    text: str,
    start: int,
    end: int,
    spans: tuple[tuple[int, int], ...],
    max_chinese_chars: int = 26,
) -> tuple[int, ...]:
    offsets: list[int] = []
    current_start = start
    while _cjk_count(text[current_start:end]) > max_chinese_chars:
        candidate_end = _offset_after_nth_cjk(text, current_start, end, max_chinese_chars)
        candidate = _find_best_boundary(text, current_start, candidate_end, spans)
        if candidate is None or candidate <= current_start:
            break
        offsets.append(candidate)
        current_start = candidate
    return tuple(offsets)


def _offset_after_nth_cjk(text: str, start: int, end: int, count: int) -> int:
    seen = 0
    for offset in range(start, end):
        if _CJK_RE.fullmatch(text[offset]):
            seen += 1
            if seen == count:
                return offset + 1
    return end


def _find_best_boundary(
    text: str,
    start: int,
    preferred_end: int,
    spans: tuple[tuple[int, int], ...],
) -> int | None:
    for offset in range(preferred_end, start, -1):
        if not _inside_protected_span(offset, spans) and text[offset - 1] in _BREAK_CHARS:
            return offset
    for offset in range(preferred_end, start, -1):
        if not _inside_protected_span(offset, spans):
            return offset
    return None


def _inside_protected_span(offset: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(start < offset < end for start, end in spans)


def _cjk_count(text: str) -> int:
    return len(_CJK_RE.findall(text))
