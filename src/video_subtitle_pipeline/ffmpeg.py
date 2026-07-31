from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from video_subtitle_pipeline.errors import DependencyError, PipelineError


def executable_path(name: str) -> str | None:
    return shutil.which(name)


def require_executable(name: str) -> str:
    executable = executable_path(name)
    if executable is None:
        if name in {"ffmpeg", "ffprobe"}:
            raise DependencyError(
                f"未找到 {name}。请在 Windows PowerShell 中运行 "
                "winget install Gyan.FFmpeg，然后重开终端后再执行 subtitle-pipeline doctor。"
            )
        raise DependencyError(f"未找到外部工具：{name}")
    return executable


def run_command(arguments: list[str], description: str) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise PipelineError(f"无法执行 {description}：{exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "未返回错误详情"
        raise PipelineError(f"{description}失败：{detail}")
    return completed


def probe_video(video: Path) -> dict[str, Any]:
    ffprobe = require_executable("ffprobe")
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(video),
        ],
        "读取视频元数据",
    )
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PipelineError("FFprobe 未返回有效 JSON") from exc
    streams = metadata.get("streams", [])
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    return {
        "duration_seconds": _as_float(metadata.get("format", {}).get("duration")),
        "format_name": metadata.get("format", {}).get("format_name"),
        "audio_stream_count": len(audio_streams),
        "audio_streams": [
            {
                "codec_name": stream.get("codec_name"),
                "sample_rate": stream.get("sample_rate"),
                "channels": stream.get("channels"),
                "language": stream.get("tags", {}).get("language"),
            }
            for stream in audio_streams
        ],
    }


def extract_audio(video: Path, output_wav: Path) -> Path:
    ffmpeg = require_executable("ffmpeg")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ],
        "提取本地音频",
    )
    return output_wav


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
