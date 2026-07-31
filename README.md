# Video Subtitle Pipeline

[中文文档](README.zh-CN.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

A local-first command-line tool that turns a video and an optional baseline SRT into readable, naturally segmented, speech-aligned subtitles. It produces a final SRT plus diagnostics, provenance, validation, and manual-review reports.

## Privacy boundary

- Video, audio, frames, and word-level timings are processed locally.
- The configured LLM receives subtitle text, protected terms, and character-boundary requests only.
- Original video and SRT files remain read-only in their original locations.
- API keys are read from environment variables and never written to reports or `pipeline_manifest.json`.

Only send subtitle content to an LLM endpoint that you are authorized to use.

## Features

- Input diagnostics for malformed SRT files, duplicate IDs, time regression, overlaps, ordering defects, empty cues, and readability concerns.
- Local Faster-Whisper transcription with word timestamps when an SRT is missing.
- Existing SRT as the preferred text baseline, with local word-timing transcription still used for final re-alignment.
- CUDA-first transcription with automatic CPU INT8 fallback in `--device auto` mode.
- OpenAI-compatible text LLM cleaning and semantic split suggestions, protected by schema and terminology validation.
- Speaker-label removal, terminology protection, semantic segmentation, word-timing alignment, readability checks, final SRT output, provenance, validation, review queue, and a run manifest.

## Not in scope

This version does not provide a GUI, batch queue, video rendering, ASS output, dynamic subtitle placement, visual analysis, or a human-review writeback workflow.

## Prerequisites

- Python 3.12 (`>=3.12,<3.14`)
- FFmpeg and FFprobe on `PATH`
- An OpenAI-compatible chat-completions endpoint and API key
- Optional NVIDIA GPU/CUDA runtime; CPU remains supported

### Install FFmpeg on Windows

```powershell
winget install Gyan.FFmpeg
```

Close and reopen the terminal after installation. If Chinese output is garbled in PowerShell, run:

```powershell
$env:PYTHONUTF8 = "1"
```

## Installation

### uv (recommended)

```bash
git clone https://github.com/student-gps/Video-Subtitle.git
cd Video-Subtitle
uv sync --group dev
```

If your uv cache and project use different Windows volumes, add `--link-mode copy`.

### pip

```bash
git clone https://github.com/student-gps/Video-Subtitle.git
cd Video-Subtitle
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install . -r requirements.txt
```

For development and tests, install the project and development requirements:

```bash
python -m pip install -e . -r requirements-dev.txt
```

## Configure the LLM

Copy the committed template, then add your own values. Never commit `.env`.

```powershell
Copy-Item .env.example .env
```

```dotenv
OPENAI_API_KEY=replace_with_your_api_key
OPENAI_BASE_URL=https://your-openai-compatible-api/v1
OPENAI_MODEL=your-model-name
```

The application loads `.env` from the current working directory. Existing system environment variables take precedence. You may instead use a YAML configuration file or CLI flags; precedence is:

1. CLI flags (`--llm-base-url`, `--llm-model`)
2. Explicit YAML values
3. System environment variables
4. `.env` values
5. Built-in defaults

`OPENAI_API_KEY` is always read from the environment variable named by `llm.api_key_env`; it is never read from YAML.

## Check your environment

```bash
uv run subtitle-pipeline doctor
# or, after pip installation:
subtitle-pipeline doctor
```

The command reports FFmpeg/FFprobe availability, CUDA fallback status, and whether the LLM configuration is complete without revealing secrets.

## Usage

### Process a video with an existing SRT

```powershell
uv run subtitle-pipeline process .\video.mp4 `
  --srt .\raw.srt `
  --glossary .\terms.txt `
  --output .\output\video-001
```

### Process a video without an SRT

```powershell
uv run subtitle-pipeline process .\video.mp4 `
  --output .\output\video-001
```

### Force CPU or choose a transcription model

```powershell
uv run subtitle-pipeline process .\video.mp4 `
  --output .\output\video-001 `
  --device cpu `
  --model medium
```

Use `--language zh|en|auto`, `--config path/to/config.yaml`, `--llm-base-url`, `--llm-model`, `--keep-workdir`, and `--overwrite` as needed. A non-empty output directory is rejected unless `--overwrite` is explicit; then only known tool artifacts can be replaced.

## Glossary

A glossary can be a UTF-8 text file with one term per line:

```text
Claude Code
BMAD
GitLab
C++
Spec-Driven Design
```

Or a JSON array / object containing a `terms` array:

```json
{"terms": ["Claude Code", "BMAD", "GitLab"]}
```

Terms are sent as transcription hints and LLM constraints. LLM output is rejected when it removes an existing protected term or proposes a split inside one.

## Output

```text
<output>/
├── 01_输入诊断.json
├── 02_词级时间轴.json
├── 02_原始转写.srt               # only without --srt
├── 02_转写基础报告.json           # only without --srt
├── 03_清洗校对.srt
├── 03_清洗修改报告.json
├── 04_语义切点.json
├── 05_意群逐句对齐.srt            # final mountable SRT
├── 05_溯源报告.json
├── 05_校验报告.json
├── 05_人工复核清单.json
└── pipeline_manifest.json
```

The manifest records file hashes, effective non-secret configuration, selected transcription device/model, fallback information, artifact hashes, and run status. It never copies source media or the original SRT.

## Default readability rules

- Prefer approximately 10–26 Chinese characters per caption; avoid fragments under about five Chinese characters unless they are independent responses.
- Minimum display duration: one second.
- Chinese warning threshold: six Chinese characters per second.
- English warning threshold: 2.5 words per second.
- Mixed text uses the combined reading load.

When a rule cannot be satisfied without changing spoken content or inventing time, the result is preserved and added to the review queue.

## Development

```bash
uv run ruff check src tests
uv run pytest --cov=video_subtitle_pipeline
uv run python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and pull-request requirements.

## Security

Never publish API keys, private videos, audio, word timings, or private subtitle text. See [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

Released under the [MIT License](LICENSE).
