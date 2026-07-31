from __future__ import annotations

import json
from pathlib import Path

from video_subtitle_pipeline.errors import ValidationError


def load_glossary(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    if not path.is_file():
        raise ValidationError(f"未找到术语表：{path}")
    try:
        if path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            values = raw.get("terms", []) if isinstance(raw, dict) else raw
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValidationError("JSON 术语表必须是字符串数组或包含 terms 字符串数组")
        else:
            values = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"无法读取术语表：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"术语表 JSON 格式无效：{path}") from exc
    return tuple(sorted({item.strip() for item in values if item.strip()}, key=lambda item: (-len(item), item)))


def protected_terms_in_text(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def protected_spans(text: str, terms: tuple[str, ...]) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    occupied = [False] * len(text)
    for term in sorted(terms, key=lambda item: (-len(item), item)):
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            end = index + len(term)
            if not any(occupied[index:end]):
                spans.append((index, end))
                for position in range(index, end):
                    occupied[position] = True
            start = index + 1
    return tuple(sorted(spans))
