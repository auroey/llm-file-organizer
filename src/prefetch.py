from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal

from .classifier import SiliconFlowClassifier
from .scanner import NoteFile


class PrefetchWorker(QThread):
    """Fetches LLM suggestions for every note in parallel before the main loop."""

    progress = Signal(int, int, str)  # done, total, current_title
    item_done = Signal(str, bool, str)  # note_path, success, error_message
    finished_summary = Signal(int, int)  # success_count, failure_count

    def __init__(
        self,
        classifier: SiliconFlowClassifier,
        notes: list[NoteFile],
        *,
        concurrency: int = 4,
    ) -> None:
        super().__init__()
        self._classifier = classifier
        self._notes = notes
        self._concurrency = max(1, concurrency)
        self._cancel_event = threading.Event()
        self._progress_lock = threading.Lock()
        self._done = 0
        self._success = 0
        self._failed = 0

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def run(self) -> None:
        total = len(self._notes)
        if total == 0 or not self._classifier.enabled:
            self.finished_summary.emit(0, 0)
            return

        pending = [note for note in self._notes if self._classifier.peek_cached(note) is None]
        cached_count = total - len(pending)

        with self._progress_lock:
            self._done = cached_count
            self._success = cached_count

        self.progress.emit(self._done, total, "（读取已缓存建议）")

        if not pending:
            self.finished_summary.emit(self._success, 0)
            return

        with ThreadPoolExecutor(max_workers=self._concurrency) as executor:
            futures = {executor.submit(self._run_one, note): note for note in pending}
            for future in futures:
                if self._cancel_event.is_set():
                    break
                note = futures[future]
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001
                    self._record_failure(note, str(exc) or type(exc).__name__, total)
                else:
                    self._record_success(note, total)

            if self._cancel_event.is_set():
                for pending_future in futures:
                    pending_future.cancel()

        self.finished_summary.emit(self._success, self._failed)

    def _run_one(self, note: NoteFile) -> None:
        if self._cancel_event.is_set():
            return
        self._classifier.suggest(note)

    def _record_success(self, note: NoteFile, total: int) -> None:
        with self._progress_lock:
            self._done += 1
            self._success += 1
            done = self._done
        self.item_done.emit(str(note.path), True, "")
        self.progress.emit(done, total, note.title)

    def _record_failure(self, note: NoteFile, message: str, total: int) -> None:
        with self._progress_lock:
            self._done += 1
            self._failed += 1
            done = self._done
        self.item_done.emit(str(note.path), False, message)
        self.progress.emit(done, total, note.title)
