from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class NoteFile:
    path: Path
    title: str
    content: str
    modified_at: datetime


@dataclass(frozen=True)
class MoveResult:
    source_path: Path
    destination_path: Path
    renamed: bool


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def extract_title(content: str, fallback_name: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback_name
    return fallback_name


def load_note(path: Path) -> NoteFile:
    content = read_text_with_fallback(path)
    modified_at = datetime.fromtimestamp(path.stat().st_mtime)
    fallback_name = path.stem
    title = extract_title(content, fallback_name)
    return NoteFile(path=path, title=title, content=content, modified_at=modified_at)


def ensure_category_dirs(root: Path, category_names: list[str]) -> None:
    for category_name in category_names:
        (root / category_name).mkdir(parents=True, exist_ok=True)


def scan_markdown_files(root: Path) -> list[NoteFile]:
    if not root.exists():
        raise FileNotFoundError(f"Source directory does not exist: {root}")

    files = [
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() == ".md" and not path.name.startswith(".")
    ]
    files.sort(key=lambda path: (path.stat().st_mtime, path.name.lower()))
    return [load_note(path) for path in files]


def build_conflict_free_path(target_dir: Path, original_name: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    candidate = target_dir / original_name
    if not candidate.exists():
        return candidate

    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    index = 1
    while index <= 9999:
        renamed = target_dir / f"{stem}_dup{index}{suffix}"
        if not renamed.exists():
            return renamed
        index += 1
    raise RuntimeError("Unable to find a conflict-free filename after 9999 attempts.")


def move_note_file(note_path: Path, target_dir: Path) -> MoveResult:
    destination = build_conflict_free_path(target_dir, note_path.name)
    renamed = destination.name != note_path.name
    shutil.move(note_path, destination)
    return MoveResult(source_path=note_path, destination_path=destination, renamed=renamed)
