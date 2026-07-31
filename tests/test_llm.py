from __future__ import annotations

import json

import httpx
import pytest

from video_subtitle_pipeline.errors import LLMResponseError
from video_subtitle_pipeline.llm import OpenAICompatibleClient
from video_subtitle_pipeline.models import LLMConfig


def test_llm_request_contains_only_messages_and_returns_json(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"break_after_character_offsets": []}'}}]},
        )

    monkeypatch.setenv("TEST_KEY", "secret")
    client = OpenAICompatibleClient(
        LLMConfig(base_url="https://example.test/v1", model="test", api_key_env="TEST_KEY"),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        result = client.request_json("system", {"text": "仅字幕文本", "protected_terms": ["BMAD"]})
    finally:
        client.close()

    assert result == {"break_after_character_offsets": []}
    assert "audio" not in json.dumps(captured, ensure_ascii=False).lower()
    assert "video" not in json.dumps(captured, ensure_ascii=False).lower()


def test_llm_rejects_invalid_response(monkeypatch) -> None:
    monkeypatch.setenv("TEST_KEY", "secret")
    client = OpenAICompatibleClient(
        LLMConfig(base_url="https://example.test/v1", model="test", api_key_env="TEST_KEY"),
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": []}))),
    )
    try:
        with pytest.raises(LLMResponseError):
            client.request_json("system", {"text": "测试"})
    finally:
        client.close()
