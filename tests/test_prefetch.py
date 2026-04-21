import time
import unittest
from datetime import datetime
from pathlib import Path

from src.prefetch import PrefetchWorker
from src.scanner import NoteFile


class _TimedClassifier:
    enabled = True

    def __init__(self, delays: dict[str, float]) -> None:
        self._delays = delays

    def peek_cached(self, _note: NoteFile) -> None:
        return None

    def suggest(self, note: NoteFile) -> None:
        time.sleep(self._delays[note.title])


class PrefetchWorkerTests(unittest.TestCase):
    def _sample_note(self, name: str) -> NoteFile:
        return NoteFile(
            path=Path(f"D:/notes/{name}.md"),
            title=name,
            content="# title\nbody",
            modified_at=datetime(2026, 4, 21, 12, 0, 0),
        )

    def test_run_reports_progress_in_completion_order(self) -> None:
        notes = [
            self._sample_note("slow"),
            self._sample_note("fast"),
            self._sample_note("medium"),
        ]
        classifier = _TimedClassifier(
            {
                "slow": 0.08,
                "fast": 0.01,
                "medium": 0.03,
            }
        )
        worker = PrefetchWorker(classifier, notes, concurrency=3)

        progress_titles: list[str] = []
        worker.progress.connect(lambda _done, _total, title: progress_titles.append(title))

        worker.run()

        self.assertEqual(
            progress_titles[1:],
            ["fast", "medium", "slow"],
        )


if __name__ == "__main__":
    unittest.main()
