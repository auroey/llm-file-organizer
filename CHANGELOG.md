# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Open-source repository metadata, contribution docs, and GitHub templates
- `pyproject.toml` packaging metadata and development tool configuration
- GitHub Actions for CI, release packaging, CodeQL, and secret scanning

### Changed

- Default `SOURCE_DIR` now points to a generic `~/Notes` path instead of a personal local directory

## [0.1.0] - 2026-04-21

### Added

- Initial PySide6 GUI for keyboard-driven Markdown note triage
- SiliconFlow / DeepSeek suggestion engine
- Suggestion caching and startup prefetch
- Duplicate-safe file moving and session statistics
