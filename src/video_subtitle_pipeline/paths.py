from __future__ import annotations

import shutil
from pathlib import Path

from video_subtitle_pipeline.errors import PipelineError

ARTIFACT_FILENAMES = {
    "diagnostic": "01_输入诊断.json",
    "word_timeline": "02_词级时间轴.json",
    "transcription_srt": "02_原始转写.srt",
    "transcription_report": "02_转写基础报告.json",
    "cleaned_srt": "03_清洗校对.srt",
    "clean_report": "03_清洗修改报告.json",
    "semantic_breaks": "04_语义切点.json",
    "final_srt": "05_意群逐句对齐.srt",
    "provenance": "05_溯源报告.json",
    "validation": "05_校验报告.json",
    "review": "05_人工复核清单.json",
    "manifest": "pipeline_manifest.json",
}


def artifact_path(output: Path, name: str) -> Path:
    return output / ARTIFACT_FILENAMES[name]


def prepare_output_directory(output: Path, overwrite: bool) -> Path:
    output = output.resolve()
    if output.exists() and not output.is_dir():
        raise PipelineError(f"输出路径不是目录：{output}")
    if output.exists() and any(output.iterdir()):
        if not overwrite:
            raise PipelineError(
                f"输出目录已存在且非空：{output}。请使用新的目录，或明确传入 --overwrite。"
            )
        known_names = {*ARTIFACT_FILENAMES.values(), ".work"}
        unknown = [path.name for path in output.iterdir() if path.name not in known_names]
        if unknown:
            raise PipelineError(
                "输出目录包含非本工具产物，拒绝覆盖：" + ", ".join(sorted(unknown))
            )
        for path in output.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    output.mkdir(parents=True, exist_ok=True)
    return output


def work_directory(output: Path) -> Path:
    return output / ".work"
