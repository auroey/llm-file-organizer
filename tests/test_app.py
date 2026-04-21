import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent

from src.app import AppController
from src.config import AppConfig
from src.scanner import NoteFile
from src.viewer import MainWindow, create_application


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: object) -> None:
        self._callbacks.remove(callback)


class _FakeWindow:
    def __init__(self) -> None:
        self.category_selected = _FakeSignal()
        self.accept_suggestion_requested = _FakeSignal()
        self.retry_suggestion_requested = _FakeSignal()
        self.skip_requested = _FakeSignal()
        self.delete_requested = _FakeSignal()
        self.exit_requested = _FakeSignal()
        self.show_called = 0
        self.empty_state_source_dir: str | None = None
        self.completion_summary: str | None = None
        self.status_messages: list[str] = []
        self.request_close_called = 0

    def show(self) -> None:
        self.show_called += 1

    def show_empty_state(self, source_dir: str) -> None:
        self.empty_state_source_dir = source_dir

    def show_completion(self, summary: str) -> None:
        self.completion_summary = summary

    def show_note(self, *_args: object, **_kwargs: object) -> None:
        return None

    def set_suggestion(self, *_args: object, **_kwargs: object) -> None:
        return None

    def set_suggestion_loading(self) -> None:
        return None

    def set_status(self, message: str) -> None:
        self.status_messages.append(message)

    def confirm_exit(self) -> bool:
        return True

    def request_close(self) -> None:
        self.request_close_called += 1


class _FakeClassifier:
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled


class _FakeDialog:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakePrefetchWorker:
    def __init__(self) -> None:
        self.cancelled = False
        self.wait_calls: list[int] = []

    def isRunning(self) -> bool:
        return True

    def cancel(self) -> None:
        self.cancelled = True

    def wait(self, timeout_ms: int | None = None) -> bool:
        self.wait_calls.append(timeout_ms)
        return True


class _FakeSuggestionWorker:
    def __init__(self) -> None:
        self.suggestion_ready = _FakeSignal()
        self.suggestion_failed = _FakeSignal()
        self.wait_calls: list[int] = []

    def isRunning(self) -> bool:
        return True

    def wait(self, timeout_ms: int | None = None) -> bool:
        self.wait_calls.append(timeout_ms)
        return True


class _RunningWorker:
    def isRunning(self) -> bool:
        return True


class AppControllerTests(unittest.TestCase):
    def _build_config(self) -> AppConfig:
        return AppConfig(
            source_dir=Path("D:/notes"),
            siliconflow_api_key=None,
            siliconflow_base_url="https://api.siliconflow.cn/v1",
            llm_model="deepseek-ai/DeepSeek-V3",
            llm_timeout_sec=7,
            llm_max_retry=2,
            llm_content_limit=4000,
            prefetch_enabled=True,
        )

    def _sample_note(self, name: str = "sample.md") -> NoteFile:
        return NoteFile(
            path=Path(f"D:/notes/{name}"),
            title=name.removesuffix(".md"),
            content="# title\nbody",
            modified_at=datetime(2026, 4, 21, 12, 0, 0),
        )

    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier())
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files", return_value=[])
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_start_shows_empty_state_when_initial_scan_is_empty(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        _scan_mock,
        _cache_mock,
        _classifier_mock,
    ) -> None:
        fake_window = _FakeWindow()
        main_window_mock.return_value = fake_window
        config = self._build_config()
        load_config_mock.return_value = config

        controller = AppController()
        controller.start()

        self.assertEqual(fake_window.show_called, 1)
        self.assertEqual(fake_window.empty_state_source_dir, str(config.source_dir))
        self.assertIsNone(fake_window.completion_summary)

    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier())
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files", return_value=[])
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_shutdown_waits_for_background_workers_to_finish(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        _scan_mock,
        _cache_mock,
        _classifier_mock,
    ) -> None:
        main_window_mock.return_value = _FakeWindow()
        load_config_mock.return_value = self._build_config()
        controller = AppController()

        prefetch_worker = _FakePrefetchWorker()
        suggestion_worker = _FakeSuggestionWorker()
        suggestion_worker.suggestion_ready.connect(controller.on_suggestion_ready)
        suggestion_worker.suggestion_failed.connect(controller.on_suggestion_failed)
        controller._prefetch_worker = prefetch_worker
        controller._prefetch_dialog = _FakeDialog()
        controller._suggestion_worker = suggestion_worker

        self.assertTrue(controller.shutdown())
        expected_wait_ms = controller._shutdown_wait_ms()

        self.assertTrue(prefetch_worker.cancelled)
        self.assertEqual(prefetch_worker.wait_calls, [expected_wait_ms])
        self.assertEqual(suggestion_worker.wait_calls, [expected_wait_ms])
        self.assertTrue(controller._prefetch_dialog is None)
        self.assertEqual(suggestion_worker.suggestion_ready._callbacks, [])
        self.assertEqual(suggestion_worker.suggestion_failed._callbacks, [])

    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier())
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files", return_value=[])
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_on_exit_requested_closes_window_only_after_confirmation(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        _scan_mock,
        _cache_mock,
        _classifier_mock,
    ) -> None:
        fake_window = _FakeWindow()
        main_window_mock.return_value = fake_window
        load_config_mock.return_value = self._build_config()
        controller = AppController()

        controller.on_exit_requested()

        self.assertEqual(fake_window.request_close_called, 1)

    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier())
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files", return_value=[])
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_on_exit_requested_keeps_window_open_when_confirmation_is_rejected(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        _scan_mock,
        _cache_mock,
        _classifier_mock,
    ) -> None:
        class _RejectWindow(_FakeWindow):
            def confirm_exit(self) -> bool:
                return False

        fake_window = _RejectWindow()
        main_window_mock.return_value = fake_window
        load_config_mock.return_value = self._build_config()
        controller = AppController()

        controller.on_exit_requested()

        self.assertEqual(fake_window.request_close_called, 0)

    @patch("src.app.PrefetchWorker")
    @patch("src.app.QProgressDialog")
    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier(enabled=True))
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files")
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_start_prefetch_uses_fixed_max_concurrency_of_four(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        scan_mock,
        _cache_mock,
        _classifier_mock,
        _progress_dialog_mock,
        prefetch_worker_mock,
    ) -> None:
        fake_window = _FakeWindow()
        notes = [self._sample_note(f"note-{index}.md") for index in range(3)]
        main_window_mock.return_value = fake_window
        load_config_mock.return_value = self._build_config()
        scan_mock.return_value = notes

        controller = AppController()
        controller.start()

        prefetch_worker_mock.assert_called_once()
        _, passed_notes = prefetch_worker_mock.call_args.args
        self.assertEqual(passed_notes, notes)
        self.assertEqual(
            prefetch_worker_mock.call_args.kwargs["concurrency"],
            4,
        )
        prefetch_worker_mock.return_value.start.assert_called_once()
        _progress_dialog_mock.return_value.setWindowModality.assert_called_once()

    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier(enabled=True))
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files")
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_request_suggestion_is_blocked_while_prefetch_is_running(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        scan_mock,
        _cache_mock,
        _classifier_mock,
    ) -> None:
        fake_window = _FakeWindow()
        notes = [self._sample_note("note-1.md")]
        main_window_mock.return_value = fake_window
        load_config_mock.return_value = self._build_config()
        scan_mock.return_value = notes

        controller = AppController()
        controller._prefetch_worker = _RunningWorker()

        controller.request_suggestion(notes[0])

        self.assertIsNone(controller._suggestion_worker)
        self.assertIn("后台预取进行中，请稍候或先取消预取。", fake_window.status_messages)

    @patch("src.app.delete_note_file")
    @patch("src.app.SiliconFlowClassifier", return_value=_FakeClassifier())
    @patch("src.app.SuggestionCache")
    @patch("src.app.scan_markdown_files")
    @patch("src.app.ensure_category_dirs")
    @patch("src.app.load_config")
    @patch("src.app.MainWindow")
    def test_on_delete_requested_sends_current_note_to_recycle_bin(
        self,
        main_window_mock,
        load_config_mock,
        _ensure_dirs_mock,
        scan_mock,
        _cache_mock,
        _classifier_mock,
        delete_note_file_mock,
    ) -> None:
        fake_window = _FakeWindow()
        notes = [self._sample_note("delete-me.md")]
        main_window_mock.return_value = fake_window
        load_config_mock.return_value = self._build_config()
        scan_mock.return_value = notes

        controller = AppController()
        controller.on_delete_requested()

        delete_note_file_mock.assert_called_once_with(notes[0].path)
        self.assertEqual(controller.current_index, 1)
        self.assertEqual(controller.stats.deleted, 1)
        self.assertIn("已移到回收站：delete-me.md", fake_window.status_messages)


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_application()

    def test_close_event_routes_through_exit_signal_until_close_is_allowed(self) -> None:
        window = MainWindow()
        emitted: list[str] = []
        window.exit_requested.connect(lambda: emitted.append("exit"))

        blocked_event = QCloseEvent()
        window.closeEvent(blocked_event)

        self.assertEqual(emitted, ["exit"])
        self.assertFalse(blocked_event.isAccepted())

        window._allow_close = True
        allowed_event = QCloseEvent()
        window.closeEvent(allowed_event)

        self.assertTrue(allowed_event.isAccepted())

    def test_key_press_d_emits_delete_requested(self) -> None:
        window = MainWindow()
        emitted: list[str] = []
        window.delete_requested.connect(lambda: emitted.append("delete"))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_D, Qt.NoModifier, "d")
        window.keyPressEvent(event)

        self.assertEqual(emitted, ["delete"])


if __name__ == "__main__":
    unittest.main()
