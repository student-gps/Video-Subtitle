from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from video_subtitle_pipeline.errors import ConfigurationError
from video_subtitle_pipeline.models import PipelineConfig

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
ENV_FILE_NAME = ".env"


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"无法读取配置文件：{path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"配置文件不是有效 YAML：{path}") from exc
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ConfigurationError(f"配置文件根节点必须是对象：{path}")
    return content


def _load_environment(env_path: Path | None = None) -> None:
    candidate = env_path or Path.cwd() / ENV_FILE_NAME
    if candidate.is_file():
        load_dotenv(candidate, override=False)


def _apply_environment_defaults(config: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(config)
    llm = dict(resolved.get("llm", {}))
    base_url_env = llm.get("base_url_env", "OPENAI_BASE_URL")
    model_env = llm.get("model_env", "OPENAI_MODEL")
    if not llm.get("base_url"):
        llm["base_url"] = os.environ.get(base_url_env) or None
    if not llm.get("model"):
        llm["model"] = os.environ.get(model_env) or None
    resolved["llm"] = llm
    return resolved


def load_config(
    config_path: Path | None = None,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
    env_path: Path | None = None,
) -> PipelineConfig:
    _load_environment(env_path)
    base = _read_yaml(DEFAULT_CONFIG_PATH)
    if config_path is not None:
        if not config_path.is_file():
            raise ConfigurationError(f"未找到配置文件：{config_path}")
        base = _deep_merge(base, _read_yaml(config_path))
    if overrides:
        base = _deep_merge(base, overrides)
    try:
        return PipelineConfig.model_validate(_apply_environment_defaults(base))
    except ValueError as exc:
        raise ConfigurationError(f"配置值不合法：{exc}") from exc


def safe_config_dump(config: PipelineConfig) -> dict[str, Any]:
    return config.model_dump(mode="json")
