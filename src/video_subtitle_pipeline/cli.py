from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from video_subtitle_pipeline.config import load_config
from video_subtitle_pipeline.errors import PipelineError
from video_subtitle_pipeline.ffmpeg import executable_path
from video_subtitle_pipeline.llm import OpenAICompatibleClient
from video_subtitle_pipeline.models import RunInput
from video_subtitle_pipeline.paths import prepare_output_directory
from video_subtitle_pipeline.pipeline import SubtitlePipeline
from video_subtitle_pipeline.transcribe import cuda_status

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="本地优先的视频字幕精修工具。视频、音频与词级时间轴不会上传。",
)
console = Console()


def _print_progress(message: str) -> None:
    console.print(f"[cyan]→[/cyan] {message}")


@app.command()
def doctor(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="覆盖默认设置的 YAML 配置文件。"),
    ] = None,
) -> None:
    """检查 FFmpeg、Python、GPU 转写策略和 LLM 配置。"""
    try:
        settings = load_config(config)
    except PipelineError as exc:
        _exit_with_error(str(exc))
        return
    table = Table(title="字幕处理环境检查")
    table.add_column("项目")
    table.add_column("状态")
    table.add_column("说明")
    for name in ("ffmpeg", "ffprobe"):
        found = executable_path(name)
        table.add_row(
            name,
            "[green]可用[/green]" if found else "[red]缺失[/red]",
            found or "运行 winget install Gyan.FFmpeg，然后重开终端。",
        )
    cuda_available, cuda_detail = cuda_status()
    table.add_row(
        "GPU 策略",
        "[green]CUDA 可用[/green]" if cuda_available else "[yellow]将回退 CPU[/yellow]",
        (
            f"{cuda_detail}；auto 模式优先 CUDA + float16。"
            if cuda_available
            else f"{cuda_detail}；auto 模式将使用 CPU + int8。"
        ),
    )
    api_key_present = bool(os.environ.get(settings.llm.api_key_env))
    llm_ready = bool(settings.llm.base_url and settings.llm.model and api_key_present)
    table.add_row(
        "OpenAI 兼容 LLM",
        "[green]已配置[/green]" if llm_ready else "[red]未配置[/red]",
        (
            "base_url、模型和 API Key 均可用。"
            if llm_ready
            else (
                "需要 base URL、模型和 API Key。可复制 .env.example 为 .env，"
                f"并设置 {settings.llm.base_url_env}、{settings.llm.model_env} 和 "
                f"{settings.llm.api_key_env}。"
            )
        ),
    )
    table.add_row("默认转写模型", settings.transcription.model, f"语言：{settings.transcription.language}")
    console.print(table)


@app.command()
def process(
    video: Annotated[Path, typer.Argument(help="待处理的视频文件。")],
    output: Annotated[Path, typer.Option("--output", "-o", help="保存阶段产物和最终字幕的目录。")],
    srt: Annotated[Path | None, typer.Option("--srt", help="可选的原始 SRT 文本基线。")] = None,
    glossary: Annotated[Path | None, typer.Option("--glossary", help="可选 TXT 或 JSON 术语表。")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="覆盖默认设置的 YAML 配置文件。")] = None,
    language: Annotated[str | None, typer.Option("--language", help="转写语言，如 zh、en 或 auto。")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Faster-Whisper 模型名称。")] = None,
    device: Annotated[str | None, typer.Option("--device", help="auto、cuda 或 cpu。")] = None,
    llm_base_url: Annotated[str | None, typer.Option("--llm-base-url", help="OpenAI 兼容 API 基础地址。")] = None,
    llm_model: Annotated[str | None, typer.Option("--llm-model", help="OpenAI 兼容模型名称。")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="允许覆盖本工具生成的输出产物。")] = False,
    keep_workdir: Annotated[bool, typer.Option("--keep-workdir", help="保留临时音频，供调试使用。")] = False,
) -> None:
    """处理一个视频并输出最终 SRT、报告与复核清单。"""
    overrides: dict[str, dict[str, object]] = {}
    transcription: dict[str, object] = {}
    llm: dict[str, object] = {}
    if language is not None:
        transcription["language"] = language
    if model is not None:
        transcription["model"] = model
    if device is not None:
        if device not in {"auto", "cuda", "cpu"}:
            _exit_with_error("--device 只能是 auto、cuda 或 cpu。")
            return
        transcription["device"] = device
    if llm_base_url is not None:
        llm["base_url"] = llm_base_url
    if llm_model is not None:
        llm["model"] = llm_model
    if transcription:
        overrides["transcription"] = transcription
    if llm:
        overrides["llm"] = llm
    try:
        settings = load_config(config, overrides)
        output = prepare_output_directory(output, overwrite)
        llm_client = OpenAICompatibleClient.create(settings.llm)
        try:
            pipeline = SubtitlePipeline(settings, llm_client, progress=_print_progress)
            manifest = pipeline.process(
                RunInput(
                    video=video.resolve(),
                    output=output,
                    srt=srt.resolve() if srt else None,
                    glossary=glossary.resolve() if glossary else None,
                ),
                keep_workdir=keep_workdir,
            )
        finally:
            llm_client.close()
    except PipelineError as exc:
        _exit_with_error(str(exc))
        return
    console.print(f"[green]完成。[/green] 已生成 {len(manifest.artifacts)} 个产物：{output}")


def _exit_with_error(message: str) -> None:
    console.print(f"[red]错误：[/red]{message}")
    raise typer.Exit(code=1)
