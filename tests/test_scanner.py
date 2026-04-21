import unittest
from pathlib import Path

from src.scanner import build_conflict_free_path, extract_title


class ScannerTests(unittest.TestCase):
    def test_extract_title_prefers_first_h1(self) -> None:
        content = "intro\n# 真正标题\n正文"
        self.assertEqual(extract_title(content, "fallback"), "真正标题")

    def test_extract_title_falls_back_to_file_name(self) -> None:
        self.assertEqual(extract_title("没有标题", "fallback"), "fallback")

    def test_build_conflict_free_path_appends_dup_suffix(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            (tmp_path / "notes.md").write_text("a", encoding="utf-8")
            (tmp_path / "notes_dup1.md").write_text("b", encoding="utf-8")

            destination = build_conflict_free_path(tmp_path, "notes.md")

            self.assertEqual(destination.name, "notes_dup2.md")


if __name__ == "__main__":
    unittest.main()
