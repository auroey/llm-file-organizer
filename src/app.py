from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QProgressDialog

from .cache import SuggestionCache, default_cache_path
from .classifier import ClassificationSuggestion, SiliconFlowClassifier
from .config import CATEGORY_LABELS, CATEGORY_MAP, load_config
from .prefetch import PrefetchWorker
from .scanner import (
    MoveResult,
    NoteFile,
    delete_note_file,
    ensure_category_dirs,
    move_note_file,
    scan_markdown_files,
)
from .viewer import MainWindow, SuggestionViewModel, create_application

PREFETCH_MAX_CONCURRENCY = 4


@dataclass
class SessionStats:
    moved: int = 0
    renamed: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    accepted: int = 0


class SuggestionWorker(QThread):
    suggestion_ready = Signal(int, str, object)
    suggestion_failed = Signal(int, str, str)

    def __init__(
        self,
        request_id: int,
        classifier: SiliconFlowClassifier,
        note: NoteFile,
        *,
        bypass_cache: bool = False,
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._classifier = classifier
        self._note = note
        self._bypass_cache = bypass_cache

    def run(self) -> None:
        note_path = str(self._note.path)
        try:
            suggestion = self._classifier.suggest(self._note, bypass_cache=self._bypass_cache)
        except Exception as exc:  # noqa: BLE001
            message = str(exc).strip() or type(exc).__name__
            self.suggestion_failed.emit(self._request_id, note_path, message)
            return
        self.suggestion_ready.emit(self._request_id, note_path, suggestion)


class AppController(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        ensure_category_dirs(self.config.source_dir, list(CATEGORY_MAP.values()))

        self.window = MainWindow()
        self.window.category_selected.connect(self.on_category_selected)
        self.window.accept_suggestion_requested.connect(self.on_accept_suggestion)
        self.window.retry_suggestion_requested.connect(self.on_retry_suggestion)
        self.window.skip_requested.connect(self.on_skip)
        self.window.delete_requested.connect(self.on_delete_requested)
        self.window.exit_requested.connect(self.on_exit_requested)

        self.cache = SuggestionCache(default_cache_path(self.config.source_dir))
        self.classifier = SiliconFlowClassifier(self.config, persistent_cache=self.cache)
        self.stats = SessionStats()
        self.notes = scan_markdown_files(self.config.source_dir)
        self.current_index = 0
        self.current_suggestion: ClassificationSuggestion | None = None
        self._suggestion_worker: SuggestionWorker | None = None
        self._suggestion_request_id = 0
        self._prefetch_worker: PrefetchWorker | None = None
        self._prefetch_dialog: QProgressDialog | None = None
        self._prefetch_failures: dict[str, str] = {}
        self._is_shutting_down = False

    def start(self) -> None:
        self.window.show()
        if not self.notes:
            self.window.show_empty_state(str(self.config.source_dir))
            return
        if self._should_run_prefetch():
            self._start_prefetch()
        else:
            self.load_current_note()

    def _shutdown_wait_ms(self) -> int:
        total_attempts = self.config.llm_max_retry + 1
        wait_seconds = (self.config.llm_timeout_sec * total_attempts) + 3
        return max(1000, wait_seconds * 1000)

    def _should_run_prefetch(self) -> bool:
        return (
            self.config.prefetch_enabled
            and self.classifier.enabled
            and len(self.notes) > 0
        )

    def _start_prefetch(self) -> None:
        total = len(self.notes)
        dialog = QProgressDialog(
            f"正在后台预取 LLM 建议（最多 {PREFETCH_MAX_CONCURRENCY} 并发）…",
            "取消（改为按需请求）",
            0,
            total,
            self.window,
        )
        dialog.setWindowTitle("预请求建议")
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setValue(0)
        dialog.setLabelText(f"0 / {total}  正在准备（最多 {PREFETCH_MAX_CONCURRENCY} 并发）…")

        worker = PrefetchWorker(
            self.classifier,
            self.notes,
            concurrency=PREFETCH_MAX_CONCURRENCY,
        )
        worker.progress.connect(self._on_prefetch_progress)
        worker.item_done.connect(self._on_prefetch_item_done)
        worker.finished_summary.connect(self._on_prefetch_finished)
        dialog.canceled.connect(worker.cancel)

        self._prefetch_worker = worker
        self._prefetch_dialog = dialog
        self._prefetch_failures = {}

        dialog.show()
        worker.start()

    def _on_prefetch_progress(self, done: int, total: int, current_title: str) -> None:
        if self._prefetch_dialog is None:
            return
        self._prefetch_dialog.setMaximum(total)
        self._prefetch_dialog.setValue(done)
        self._prefetch_dialog.setLabelText(f"{done} / {total}  {current_title}")

    def _on_prefetch_item_done(self, note_path: str, success: bool, message: str) -> None:
        if not success:
            self._prefetch_failures[note_path] = message

    def _on_prefetch_finished(self, success_count: int, failure_count: int) -> None:
        if self._prefetch_dialog is not None:
            self._prefetch_dialog.close()
            self._prefetch_dialog = None
        if self._prefetch_worker is not None:
            self._prefetch_worker = None

        if failure_count:
            self.window.set_status(
                "后台预取完成："
                f"成功 {success_count}，失败 {failure_count}"
                "（失败的文件仍可手动分类或按 R 重试）"
            )
        else:
            self.window.set_status(
                f"后台预取完成：已缓存 {success_count} 条建议，下面会继续即时展示"
            )
        self.load_current_note()

    def load_current_note(self) -> None:
        if self.current_index >= len(self.notes):
            self.window.show_completion(
                "\n".join(
                    [
                        f"成功移动：{self.stats.moved}",
                        f"自动重命名：{self.stats.renamed}",
                        f"跳过：{self.stats.skipped}",
                        f"移到回收站：{self.stats.deleted}",
                        f"失败：{self.stats.failed}",
                        f"采纳建议：{self.stats.accepted}",
                    ]
                )
            )
            return

        note = self.notes[self.current_index]
        self.current_suggestion = None
        self.window.show_note(note, self.current_index + 1, len(self.notes))

        if not self.classifier.enabled:
            self.window.set_suggestion(
                SuggestionViewModel(
                    title="LLM 未配置，已禁用",
                    detail="可直接按 1-7 手动分类。",
                    accepted_key=None,
                )
            )
            return

        cached = self.classifier.peek_cached(note)
        if cached is not None:
            self._apply_suggestion(note, cached, from_cache=True)
            return

        prior_failure = self._prefetch_failures.pop(str(note.path), None)
        if prior_failure:
            self.current_suggestion = None
            self.window.set_suggestion(
                SuggestionViewModel(
                    title="建议不可用",
                    detail=prior_failure,
                    accepted_key=None,
                    is_error=True,
                )
            )
            self.window.set_status("预请求时失败，你可以按 R 重试或 1-7 手动分类。")
            return

        self.request_suggestion(note)

    def request_suggestion(self, note: NoteFile, *, bypass_cache: bool = False) -> None:
        if not self.classifier.enabled:
            self.window.set_suggestion(
                SuggestionViewModel(
                    title="LLM 未配置，已禁用",
                    detail="可直接按 1-7 手动分类。",
                    accepted_key=None,
                )
            )
            return
        if self._prefetch_worker is not None and self._prefetch_worker.isRunning():
            self.window.set_status("后台预取进行中，请稍候或先取消预取。")
            return

        self.window.set_suggestion_loading()
        self._suggestion_request_id += 1
        self._suggestion_worker = SuggestionWorker(
            self._suggestion_request_id,
            self.classifier,
            note,
            bypass_cache=bypass_cache,
        )
        self._suggestion_worker.suggestion_ready.connect(self.on_suggestion_ready)
        self._suggestion_worker.suggestion_failed.connect(self.on_suggestion_failed)
        self._suggestion_worker.start()

    def _apply_suggestion(
        self,
        note: NoteFile,
        suggestion: ClassificationSuggestion,
        *,
        from_cache: bool,
    ) -> None:
        self.current_suggestion = suggestion
        self.window.set_suggestion(
            SuggestionViewModel(
                title="建议分类",
                folder=suggestion.folder,
                confidence_pct=round(suggestion.confidence * 100),
                reason=suggestion.reason,
                accepted_key=suggestion.category_key,
            )
        )
        if from_cache:
            hint = "缓存命中，按 Enter 直接采纳。"
        else:
            hint = "建议已生成，可按 Enter 直接采纳。"
        self.window.set_status(hint)

    def on_suggestion_ready(
        self,
        request_id: int,
        note_path: str,
        suggestion: ClassificationSuggestion,
    ) -> None:
        if self.current_index >= len(self.notes):
            return
        if request_id != self._suggestion_request_id:
            return
        if str(self.notes[self.current_index].path) != note_path:
            return

        self._apply_suggestion(self.notes[self.current_index], suggestion, from_cache=False)

    def on_suggestion_failed(self, request_id: int, note_path: str, error_message: str) -> None:
        if self.current_index >= len(self.notes):
            return
        if request_id != self._suggestion_request_id:
            return
        if str(self.notes[self.current_index].path) != note_path:
            return
        self.current_suggestion = None
        self.window.set_suggestion(
            SuggestionViewModel(
                title="建议不可用",
                detail=error_message,
                accepted_key=None,
                is_error=True,
            )
        )
        self.window.set_status("你仍然可以直接按 1-7 手动分类。")

    def on_category_selected(self, category_key: str) -> None:
        if self.current_index >= len(self.notes):
            return
        target_folder = CATEGORY_MAP[category_key]
        self.move_current_note(target_folder, accepted=False)

    def on_accept_suggestion(self) -> None:
        if self.current_index >= len(self.notes):
            return
        if not self.current_suggestion:
            self.window.set_status("当前没有可采纳的建议。")
            return

        self.move_current_note(self.current_suggestion.folder, accepted=True)

    def on_retry_suggestion(self) -> None:
        if self.current_index >= len(self.notes):
            return
        if self._suggestion_worker and self._suggestion_worker.isRunning():
            self.window.set_status("建议仍在生成中，请稍候后再按 R 重试。")
            return
        note = self.notes[self.current_index]
        self.classifier.clear_cache_for(note)
        self.request_suggestion(note, bypass_cache=True)

    def on_skip(self) -> None:
        if self.current_index >= len(self.notes):
            return
        self.stats.skipped += 1
        self.current_index += 1
        self.load_current_note()

    def on_delete_requested(self) -> None:
        if self.current_index >= len(self.notes):
            return
        self.delete_current_note()

    def on_exit_requested(self) -> None:
        if self.window.confirm_exit() and self.shutdown():
            self.window.request_close()

    def shutdown(self) -> bool:
        if self._is_shutting_down:
            return True
        self._is_shutting_down = True
        wait_ms = self._shutdown_wait_ms()
        if self._prefetch_worker is not None and self._prefetch_worker.isRunning():
            self.window.set_status("正在等待后台任务结束…")
            self._prefetch_worker.cancel()
            if not self._prefetch_worker.wait(wait_ms):
                self.window.set_status("后台预请求仍在结束，请稍后再试。")
                self._is_shutting_down = False
                return False
        self._prefetch_worker = None
        if self._prefetch_dialog is not None:
            self._prefetch_dialog.close()
            self._prefetch_dialog = None
        if self._suggestion_worker and self._suggestion_worker.isRunning():
            try:
                self._suggestion_worker.suggestion_ready.disconnect(self.on_suggestion_ready)
                self._suggestion_worker.suggestion_failed.disconnect(self.on_suggestion_failed)
            except (RuntimeError, TypeError, ValueError):
                pass
            self.window.set_status("正在等待当前 LLM 请求结束…")
            if not self._suggestion_worker.wait(wait_ms):
                self.window.set_status("当前 LLM 请求仍未结束，请稍后再试。")
                self._is_shutting_down = False
                return False
        self._suggestion_worker = None
        return True

    def move_current_note(self, target_folder: str, accepted: bool) -> None:
        note = self.notes[self.current_index]
        try:
            result = move_note_file(note.path, self.config.source_dir / target_folder)
        except Exception as exc:
            self.stats.failed += 1
            message = str(exc).strip() or type(exc).__name__
            self.window.set_status(f"移动失败：{message}")
            return

        self._record_move_result(result, accepted)
        self.current_index += 1
        self.load_current_note()

    def delete_current_note(self) -> None:
        note = self.notes[self.current_index]
        try:
            delete_note_file(note.path)
        except Exception as exc:
            self.stats.failed += 1
            message = str(exc).strip() or type(exc).__name__
            self.window.set_status(f"移到回收站失败：{message}")
            return

        self.stats.deleted += 1
        self.window.set_status(f"已移到回收站：{note.path.name}")
        self.current_index += 1
        self.load_current_note()

    def _record_move_result(self, result: MoveResult, accepted: bool) -> None:
        self.stats.moved += 1
        if result.renamed:
            self.stats.renamed += 1
        if accepted:
            self.stats.accepted += 1
        accepted_text = "，已采纳建议" if accepted else ""
        category_hint = next(
            (
                CATEGORY_LABELS[key]
                for key, folder in CATEGORY_MAP.items()
                if folder == result.destination_path.parent.name
            ),
            result.destination_path.parent.name,
        )
        self.window.set_status(
            f"已移动到 {category_hint}：{result.destination_path.name}{accepted_text}"
        )


def main() -> int:
    app = create_application()
    controller = AppController()
    app.aboutToQuit.connect(controller.shutdown)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
