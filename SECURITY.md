# Security Policy

## Supported versions

This project is early-stage. Security fixes are applied to the latest development state first.

## Reporting a vulnerability

Please avoid filing public issues for undisclosed vulnerabilities.

Instead, contact the maintainer privately with:

- a clear description of the issue
- reproduction steps or proof of concept
- impact assessment
- any suggested remediation

If you cannot reach the maintainer privately, open a GitHub issue with only a minimal description and no exploit details.

## Secret handling

- Never commit `.env` files or real API keys.
- Treat any accidentally exposed key as compromised and rotate it immediately.
- Review screenshots, logs, and recordings before sharing them publicly.
- Do not paste private local paths or personal note contents into public issues unless they are sanitized.

## Disclosure expectations

- Please give the maintainer reasonable time to investigate and fix the issue before public disclosure.
- Once a fix is available, a changelog entry should reference the security update at a high level.
