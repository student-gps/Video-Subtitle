# Contributing

Thank you for contributing to Video Subtitle Pipeline.

## Development setup

Use Python 3.12. You can use either dependency workflow.

### uv (recommended)

```bash
uv sync --group dev
uv run ruff check src tests
uv run pytest --cov=video_subtitle_pipeline
uv run python -m build
```

### pip

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . -r requirements-dev.txt
ruff check src tests
pytest --cov=video_subtitle_pipeline
python -m build
```

## Contribution expectations

- Keep video, audio, frames, word timings, API keys, and private subtitle text out of commits, fixtures, issues, and pull requests.
- Add or update tests for behavior changes. Tests must not require an API key, a real model download, GPU hardware, or a real video.
- Run the lint and test commands above before opening a pull request.
- Keep public documentation in both [README.md](README.md) and [README.zh-CN.md](README.zh-CN.md) when changing user-facing behavior.
- Use concise, descriptive commits and explain user-visible changes in the pull request.

## Reporting bugs and proposing changes

Use the GitHub issue templates. Do not attach sensitive media or credentials. See [SECURITY.md](SECURITY.md) for private vulnerability reporting guidance.
