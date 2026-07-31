from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from video_subtitle_pipeline.errors import ConfigurationError, LLMResponseError
from video_subtitle_pipeline.models import LLMConfig

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass
class OpenAICompatibleClient:
    config: LLMConfig
    client: httpx.Client

    @classmethod
    def create(cls, config: LLMConfig) -> OpenAICompatibleClient:
        if not config.base_url:
            raise ConfigurationError("LLM 必须启用：请通过 --llm-base-url 或配置文件设置 llm.base_url。")
        if not config.model:
            raise ConfigurationError("LLM 必须启用：请通过 --llm-model 或配置文件设置 llm.model。")
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"LLM 必须启用：请设置环境变量 {config.api_key_env}，其值不会写入任何产物。"
            )
        return cls(
            config=config,
            client=httpx.Client(
                timeout=config.timeout_seconds,
                headers={"Authorization": f"Bearer {api_key}"},
            ),
        )

    def close(self) -> None:
        self.client.close()

    def request_json(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        base_url = self.config.base_url.rstrip("/")
        endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        request_body = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                },
            ],
        }
        try:
            response = self.client.post(endpoint, json=request_body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"LLM 调用失败：{exc}") from exc
        try:
            raw = response.json()
            content = raw["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
                )
            if not isinstance(content, str):
                raise TypeError("message.content 不是字符串")
            fence_match = _JSON_FENCE_RE.match(content)
            decoded = json.loads(fence_match.group(1) if fence_match else content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMResponseError("LLM 未返回可解析的 JSON 对象。") from exc
        if not isinstance(decoded, dict):
            raise LLMResponseError("LLM JSON 根节点必须是对象。")
        return decoded


CLEANING_SYSTEM_PROMPT = """你是严格的字幕文本清洗器。只处理用户提供的字幕文本，绝不接收或推断音视频、时间轴或画面内容。
你必须返回一个 JSON 对象，格式为 {\"cues\":[{\"cue_key\":\"...\",\"cleaned_text\":\"...\"}]}。
逐条保留 cue_key，不能遗漏、重复或新增。只可删除无意义语气词、明显口头重复、在不影响逻辑时的冗余口头连接词，并可修正由全文上下文明确确认的转写错误。
绝不能合并、拆分、重排 cue，不能编造、总结、扩写、改变原意或事实。所有受保护术语必须逐字保留。"""

SEGMENTATION_SYSTEM_PROMPT = """你是严格的字幕语义切点建议器。只处理用户提供的单条字幕文本；绝不接收或推断音视频、时间轴或画面内容。
返回 JSON 对象，格式为 {\"break_after_character_offsets\":[整数,...]}。每个整数表示从文本开头计数、在该字符之后切分，因此必须大于 0 且小于文本总字符数。
只建议自然语义意群边界。不得改写、删除、增加、重排任何字符。不得在给定的受保护字符范围内部切分。若不应切分，返回空数组。"""


def expect_cleaning_response(
    response: dict[str, Any], expected_keys: Sequence[str]
) -> dict[str, str]:
    items = response.get("cues")
    if not isinstance(items, list):
        raise LLMResponseError("LLM 清洗响应缺少 cues 数组。")
    result: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise LLMResponseError("LLM 清洗响应中存在非对象条目。")
        key = item.get("cue_key")
        text = item.get("cleaned_text")
        if not isinstance(key, str) or not isinstance(text, str):
            raise LLMResponseError("LLM 清洗条目必须包含字符串 cue_key 和 cleaned_text。")
        if key in result:
            raise LLMResponseError(f"LLM 清洗响应重复了 cue_key：{key}")
        result[key] = text.strip()
    if set(result) != set(expected_keys):
        raise LLMResponseError("LLM 清洗响应的 cue_key 集合与输入不一致。")
    return result


def expect_offsets(response: dict[str, Any], text_length: int) -> tuple[int, ...]:
    offsets = response.get("break_after_character_offsets")
    if not isinstance(offsets, list) or not all(isinstance(offset, int) for offset in offsets):
        raise LLMResponseError("LLM 切分响应必须包含整数数组 break_after_character_offsets。")
    if offsets != sorted(set(offsets)):
        raise LLMResponseError("LLM 切分边界必须严格递增且不可重复。")
    if any(offset <= 0 or offset >= text_length for offset in offsets):
        raise LLMResponseError("LLM 切分边界超出文本范围。")
    return tuple(offsets)
