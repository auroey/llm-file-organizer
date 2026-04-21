# Contributing

Thanks for your interest in improving this project.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## Before opening a pull request

Run the local quality checks:

```bash
ruff check .
pytest
```

## Contribution guidelines

- Keep changes focused and small when possible.
- Add or update tests for behavior changes.
- Avoid committing secrets, API keys, or personal paths.
- Prefer English for code, identifiers, and commit messages.
- Use Conventional Commits when creating commits, for example:
  - `feat(ui): add startup prefetch progress dialog`
  - `docs: improve quick start guide`

## Pull request checklist

- [ ] I ran `ruff check .`
- [ ] I ran `pytest`
- [ ] I updated docs if behavior or setup changed
- [ ] I did not commit `.env` or other secrets
- [ ] I tested the affected flow manually if GUI behavior changed

## Reporting bugs

Please use the GitHub issue templates and include:

- operating system
- Python version
- how to reproduce the issue
- expected behavior
- actual behavior
- screenshots or logs when helpful
