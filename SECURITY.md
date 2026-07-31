# Security Policy

## Supported versions

Security fixes are applied to the latest released version and the default branch.

## Reporting a vulnerability

Do **not** disclose vulnerabilities, API keys, private videos, audio, word-level timings, subtitle text, or personally identifiable information in public issues.

Before accepting vulnerability reports, the maintainer should enable GitHub private vulnerability reporting for this repository. Until then, contact the maintainer privately through [@student-gps](https://github.com/student-gps) rather than using a public issue.

Please include a concise description, impact, reproduction steps that use synthetic data, and any suggested mitigation. The maintainer will acknowledge the report and coordinate a fix before public disclosure when appropriate.

## Handling secrets and media

- Copy `.env.example` to `.env`; never commit `.env`.
- Revoke a credential immediately if it was accidentally exposed.
- Use synthetic fixtures for tests and bug reports.
- The tool sends subtitle text to the configured LLM endpoint; only process content you are authorized to send to that endpoint.
