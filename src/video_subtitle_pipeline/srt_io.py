from __future__ import annotations

import re
from collections.abc import Iterable

from video_subtitle_pipeline.errors import ValidationError
from video_subtitle_pipeline.models import SourceCue

_TIMESTAMP_RE = re.compile(
    r"^(?P<hours>\d{2,}):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d)[,.](?P<milliseconds>\d{3})$"
)
_TIME_RANGE_RE = re.compile(r"^\s*(.+?)\s+-->\s+(.+?)(?:\s+.*)?$")


def parse_timestamp(value: str) -> int:
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:
        raise ValidationError(f"无效 SRT 时间戳：{value!r}")
    parts = {key: int(raw) for key, raw in match.groupdict().items()}
    return (
        parts["hours"] * 3_600_000
        + parts["minutes"] * 60_000
        + parts["seconds"] * 1_000
        + parts["milliseconds"]
    )


def format_timestamp(milliseconds: int) -> str:
    if milliseconds < 0:
        raise ValueError("时间不能为负数")
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, ms = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def parse_srt(content: str) -> list[SourceCue]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    blocks = re.split(r"\n{2,}", normalized.strip()) if normalized.strip() else []
    cues: list[SourceCue] = []
    for index, block in enumerate(blocks):
        lines = block.split("\n")
        if len(lines) < 2:
            raise ValidationError(f"第 {index + 1} 个 SRT 条目不完整")
        source_id = lines[0].strip()
        if not source_id:
            raise ValidationError(f"第 {index + 1} 个 SRT 条目缺少编号")
        range_match = _TIME_RANGE_RE.match(lines[1])
        if not range_match:
            raise ValidationError(f"第 {index + 1} 个 SRT 条目缺少时间范围")
        start_ms = parse_timestamp(range_match.group(1))
        end_ms = parse_timestamp(range_match.group(2))
        if end_ms <= start_ms:
            raise ValidationError(f"第 {index + 1} 个 SRT 条目的结束时间必须晚于开始时间")
        cues.append(
            SourceCue(
                source_id=source_id,
                source_index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text="\n".join(lines[2:]).strip(),
            )
        )
    return cues


def read_srt(path: str) -> list[SourceCue]:
    from pathlib import Path

    try:
        return parse_srt(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ValidationError(f"无法读取 SRT 文件：{path}") from exc


def render_srt(cues: Iterable[SourceCue]) -> str:
    rendered: list[str] = []
    for number, cue in enumerate(cues, start=1):
        rendered.extend(
            [
                str(number),
                f"{format_timestamp(cue.start_ms)} --> {format_timestamp(cue.end_ms)}",
                cue.text,
                "",
            ]
        )
    return "\n".join(rendered).rstrip() + "\n" if rendered else ""
