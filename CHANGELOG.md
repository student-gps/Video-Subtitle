# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - 2026-07-31

### Added

- Local-first command-line pipeline for video subtitle diagnostics, transcription, cleaning, semantic splitting, word-timing alignment, validation, provenance, and review reports.
- Existing-SRT and no-SRT input paths.
- Faster-Whisper transcription with CUDA-first and CPU INT8 fallback behavior.
- OpenAI-compatible text LLM integration for cleaning and semantic split suggestions.
- Terminology protection, SRT validation, readability checks, and structured run manifests.
- `.env`-based LLM configuration, pip and uv dependency entry points, GitHub Actions CI, and open-source project documentation.

### Not supported

- GUI, video rendering, dynamic subtitle placement, visual analysis, batch queues, ASS output, or human-review writeback workflow.
