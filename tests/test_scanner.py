import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.scanner import build_conflict_free_path, delete_note_file, extract_title


class ScannerTests(unittest.TestCase):
    def test_extract_title_prefers_first_h1(self) -> None:
        content = "intro\n# 真正标题\n正文"
        self.assertEqual(extract_title(content, "fallback"), "真正标题")

    def test_extract_title_falls_back_to_file_name(self) -> None:
        self.assertEqual(extract_title("没有标题", "fallback"), "fallback")

    def test_build_conflict_free_path_appends_dup_suffix(self) -> None:
        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            (tmp_path / "notes.md").write_text("a", encoding="utf-8")
            (tmp_path / "notes_dup1.md").write_text("b", encoding="utf-8")

            destination = build_conflict_free_path(tmp_path, "notes.md")

            self.assertEqual(destination.name, "notes_dup2.md")

    def test_delete_note_file_uses_windows_recycle_bin_helper(self) -> None:
        with TemporaryDirectory() as directory:
            note_path = Path(directory) / "notes.md"
            note_path.write_text("hello", encoding="utf-8")

            with patch("src.scanner._send_to_windows_recycle_bin") as recycle_mock:
                delete_note_file(note_path)

            recycle_mock.assert_called_once_with(note_path)


if __name__ == "__main__":
    unittest.main()
