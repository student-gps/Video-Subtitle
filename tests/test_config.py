from __future__ import annotations

import os
from pathlib import Path

from video_subtitle_pipeline.config import load_config, safe_config_dump


def test_load_config_uses_dotenv_values_when_explicit_values_are_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_BASE_URL=https://example.test/v1\nOPENAI_MODEL=test-model\n",
        encoding="utf-8",
    )

    config = load_config(env_path=env_path)

    assert config.llm.base_url == "https://example.test/v1"
    assert config.llm.model == "test-model"


def test_system_environment_overrides_dotenv_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://system.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "system-model")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_BASE_URL=https://dotenv.test/v1\nOPENAI_MODEL=dotenv-model\n",
        encoding="utf-8",
    )

    config = load_config(env_path=env_path)

    assert config.llm.base_url == "https://system.test/v1"
    assert config.llm.model == "system-model"


def test_explicit_config_values_override_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://system.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "system-model")
    custom = tmp_path / "config.yaml"
    custom.write_text(
        "llm:\n  base_url: https://config.test/v1\n  model: config-model\n",
        encoding="utf-8",
    )

    config = load_config(config_path=custom, env_path=tmp_path / "missing.env")

    assert config.llm.base_url == "https://config.test/v1"
    assert config.llm.model == "config-model"


def test_safe_config_dump_never_contains_api_key_value(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-key")
    config = load_config(env_path=Path("missing.env"))

    dumped = safe_config_dump(config)

    assert "super-secret-key" not in str(dumped)
    assert dumped["llm"]["api_key_env"] == "OPENAI_API_KEY"
    assert os.environ["OPENAI_API_KEY"] == "super-secret-key"
