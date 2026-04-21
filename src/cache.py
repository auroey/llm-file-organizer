from __future__ import annotations

import json
import threading
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from .classifier import ClassificationSuggestion
from .config import CATEGORY_MAP

CACHE_FILE_NAME = ".llm_cache.json"
CACHE_SCHEMA_VERSION = 1


class SuggestionCache:
    """Persistent, thread-safe cache of LLM suggestions keyed by content hash.

    The cache file lives next to the notes (inside ``source_dir``), using the
    content hash as the key so that renaming/moving a note never invalidates
    its cached suggestion.
    """

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._lock = threading.Lock()
        self._entries: dict[str, ClassificationSuggestion] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(raw, dict):
            return
        entries = raw.get("entries", {})
        if not isinstance(entries, dict):
            return
        for key, value in entries.items():
            suggestion = _try_build_suggestion(value)
            if suggestion is not None:
                self._entries[key] = suggestion

    def _dump_locked(self) -> None:
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "entries": {key: asdict(value) for key, value in self._entries.items()},
        }
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._path)

    def get(self, content_hash: str) -> ClassificationSuggestion | None:
        with self._lock:
            return self._entries.get(content_hash)

    def has(self, content_hash: str) -> bool:
        with self._lock:
            return content_hash in self._entries

    def set(self, content_hash: str, suggestion: ClassificationSuggestion) -> None:
        with self._lock:
            self._entries[content_hash] = suggestion
            self._dump_locked()

    def pop(self, content_hash: str) -> None:
        with self._lock:
            if content_hash in self._entries:
                self._entries.pop(content_hash)
                self._dump_locked()

    def prune(self, keep_hashes: Iterable[str]) -> int:
        keep = set(keep_hashes)
        with self._lock:
            dropped = [key for key in self._entries if key not in keep]
            for key in dropped:
                self._entries.pop(key, None)
            if dropped:
                self._dump_locked()
            return len(dropped)


def _try_build_suggestion(payload: object) -> ClassificationSuggestion | None:
    if not isinstance(payload, dict):
        return None
    try:
        category_key = str(payload["category_key"])
        folder = str(payload["folder"])
        confidence = float(payload["confidence"])
        reason = str(payload.get("reason", ""))
    except (KeyError, TypeError, ValueError):
        return None
    if category_key not in CATEGORY_MAP:
        return None
    if folder != CATEGORY_MAP[category_key]:
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return ClassificationSuggestion(
        category_key=category_key,
        folder=folder,
        confidence=confidence,
        reason=reason[:15],
    )


def default_cache_path(source_dir: Path) -> Path:
    return source_dir / CACHE_FILE_NAME
