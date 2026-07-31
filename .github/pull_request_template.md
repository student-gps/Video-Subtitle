## Summary

Describe the user-visible change and why it is needed.

## Validation

- [ ] `ruff check src tests`
- [ ] `pytest --cov=video_subtitle_pipeline`
- [ ] Updated English and Chinese README content when user-facing behavior changed.
- [ ] Added or updated tests for the change.

## Sensitive data check

- [ ] No API keys, `.env` files, private media, word-level timing artifacts, or private subtitle text are included.
- [ ] Fixtures and logs use synthetic or redacted content.
