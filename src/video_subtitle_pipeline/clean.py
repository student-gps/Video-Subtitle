from __future__ import annotations

import re
from typing import Protocol

from video_subtitle_pipeline.errors import LLMResponseError
from video_subtitle_pipeline.glossary import protected_terms_in_text
from video_subtitle_pipeline.llm import CLEANING_SYSTEM_PROMPT, expect_cleaning_response
from video_subtitle_pipeline.models import CleanedCue, SourceCue


class JsonRequester(Protocol):
    def request_json(self, system_prompt: str, payload: dict) -> dict: ...


_SPEAKER_PATTERNS = (
    re.compile(r"^\s*\[[^\]\n]{1,80}\]\s*"),
    re.compile(r"^\s*[A-Za-z一-鿿][A-Za-z一-鿿 .·'’-]{0,79}\s*[:：]\s*"),
)
_DISPOSABLE_RE = re.compile(r"^[\s，,。.!！?？、…嗯啊呃哈]+$")


def remove_leading_speaker_label(text: str) -> str:
    for pattern in _SPEAKER_PATTERNS:
        match = pattern.match(text)
        if match:
            return text[match.end() :].lstrip()
    return text


def clean_cues(
    cues: list[SourceCue],
    terms: tuple[str, ...],
    llm: JsonRequester,
) -> list[CleanedCue]:
    preprocessed = [(cue, remove_leading_speaker_label(cue.text)) for cue in cues]
    non_empty = [
        {"cue_key": _cue_key(cue), "text": text}
        for cue, text in preprocessed
        if text.strip()
    ]
    cleaned_by_key: dict[str, str] = {}
    if non_empty:
        response = llm.request_json(
            CLEANING_SYSTEM_PROMPT,
            {"task": "clean_subtitles", "protected_terms": list(terms), "cues": non_empty},
        )
        cleaned_by_key = expect_cleaning_response(response, [item["cue_key"] for item in non_empty])
    cleaned: list[CleanedCue] = []
    for cue, label_removed_text in preprocessed:
        candidate = cleaned_by_key.get(_cue_key(cue), "")
        _validate_cleaned_text(cue, label_removed_text, candidate, terms)
        protected = protected_terms_in_text(label_removed_text, terms)
        cleaned.append(
            CleanedCue(
                source=cue,
                speaker_label_removed_text=label_removed_text,
                cleaned_text=candidate,
                llm_modified=candidate != label_removed_text,
                protected_terms_found=protected,
            )
        )
    return cleaned


def _validate_cleaned_text(
    cue: SourceCue,
    before: str,
    after: str,
    terms: tuple[str, ...],
) -> None:
    if not after and before.strip() and not _DISPOSABLE_RE.fullmatch(before):
        raise LLMResponseError(f"LLM 将非纯语气词字幕清空：源 cue {cue.source_id}")
    for term in protected_terms_in_text(before, terms):
        if term not in after:
            raise LLMResponseError(f"LLM 修改或删除了受保护术语 {term!r}：源 cue {cue.source_id}")


def _cue_key(cue: SourceCue) -> str:
    return f"{cue.source_index}:{cue.source_id}"
