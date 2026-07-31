from __future__ import annotations

import re
from collections.abc import Iterable

from video_subtitle_pipeline.models import CleanedCue, SemanticGroup, WordTiming
from video_subtitle_pipeline.segment import SegmentationDecision, split_text

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[㐀-鿿豈-﫿]|[^\s]")
_PUNCTUATION_RE = re.compile(r"[\s，。！？；：、,.!?;:]+")


def align_decision(
    cue: CleanedCue,
    decision: SegmentationDecision,
    words: Iterable[WordTiming],
) -> list[SemanticGroup]:
    parts = split_text(decision.text, decision.accepted_offsets)
    cue_words = tuple(
        word
        for word in words
        if word.start_ms >= cue.source.start_ms and word.end_ms <= cue.source.end_ms and word.text.strip()
    )
    groups: list[SemanticGroup] = []
    word_cursor = 0
    for number, (start_offset, end_offset, text) in enumerate(parts, start=1):
        tokens = _tokens(text)
        matched = _match_tokens(tokens, cue_words, word_cursor)
        reasons: list[str] = []
        if matched:
            first_index, last_index = matched
            word_cursor = last_index + 1
            start_ms = cue_words[first_index].start_ms
            end_ms = cue_words[last_index].end_ms
            matched_words = cue_words[first_index : last_index + 1]
            probabilities = [word.probability for word in matched_words if word.probability is not None]
            confidence = sum(probabilities) / len(probabilities) if probabilities else None
            method = "word_timing"
            if confidence is not None and confidence < 0.6:
                reasons.append("alignment_low_confidence")
        else:
            start_ms, end_ms = _interpolate_range(
                cue.source.start_ms,
                cue.source.end_ms,
                start_offset,
                end_offset,
                len(decision.text),
            )
            confidence = None
            method = "interpolation"
            reasons.extend(("interpolated_alignment", "alignment_low_confidence"))
        if end_ms <= start_ms:
            end_ms = min(cue.source.end_ms, start_ms + 1)
            if end_ms <= start_ms:
                start_ms = max(cue.source.start_ms, cue.source.end_ms - 1)
                end_ms = cue.source.end_ms
        groups.append(
            SemanticGroup(
                group_id=f"{cue.source.source_index + 1}-{number}",
                source_ids=(cue.source.source_id,),
                text=text,
                start_offset=start_offset,
                end_offset=end_offset,
                start_ms=start_ms,
                end_ms=end_ms,
                alignment_method=method,
                confidence=confidence,
                review_reasons=tuple(reasons),
            )
        )
    return groups


def ensure_monotonic_non_overlapping(groups: list[SemanticGroup]) -> list[SemanticGroup]:
    normalized: list[SemanticGroup] = []
    previous_end = -1
    for group in sorted(groups, key=lambda item: (item.start_ms, item.end_ms, item.group_id)):
        start_ms = max(group.start_ms, previous_end + 1)
        end_ms = max(group.end_ms, start_ms + 1)
        reasons = list(group.review_reasons)
        if start_ms != group.start_ms or end_ms != group.end_ms:
            reasons.append("time_boundary_adjusted_for_non_overlap")
        normalized.append(
            group.model_copy(
                update={"start_ms": start_ms, "end_ms": end_ms, "review_reasons": tuple(dict.fromkeys(reasons))}
            )
        )
        previous_end = end_ms
    return normalized


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN_RE.findall(_normalize(text)))


def _normalize(text: str) -> str:
    return _PUNCTUATION_RE.sub("", text)


def _match_tokens(
    expected_tokens: tuple[str, ...], words: tuple[WordTiming, ...], cursor: int
) -> tuple[int, int] | None:
    if not expected_tokens:
        return None
    word_tokens = tuple(_tokens(word.text) for word in words)
    flattened: list[tuple[str, int]] = [
        (token, index) for index, tokens in enumerate(word_tokens) for token in tokens
    ]
    expected = "".join(expected_tokens)
    candidate = ""
    start_index: int | None = None
    for token, word_index in flattened:
        if word_index < cursor:
            continue
        if start_index is None:
            start_index = word_index
        candidate += token
        if candidate == expected:
            return start_index, word_index
        if not expected.startswith(candidate):
            candidate = token
            start_index = word_index
            if candidate == expected:
                return start_index, word_index
    return None


def _interpolate_range(
    source_start: int,
    source_end: int,
    start_offset: int,
    end_offset: int,
    text_length: int,
) -> tuple[int, int]:
    duration = source_end - source_start
    start = source_start + round(duration * start_offset / text_length)
    end = source_start + round(duration * end_offset / text_length)
    return start, end
