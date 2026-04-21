from __future__ import annotations

import html
from dataclasses import dataclass

import markdown
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .config import CATEGORY_LABELS, CATEGORY_MAP
from .scanner import NoteFile


@dataclass(frozen=True)
class SuggestionViewModel:
    title: str
    detail: str = ""
    folder: str | None = None
    confidence_pct: int | None = None
    reason: str | None = None
    accepted_key: str | None = None
    is_loading: bool = False
    is_error: bool = False


class MainWindow(QMainWindow):
    category_selected = Signal(str)
    accept_suggestion_requested = Signal()
    retry_suggestion_requested = Signal()
    skip_requested = Signal()
    delete_requested = Signal()
    exit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._allow_close = False
        self._current_suggestion_key: str | None = None
        self.setWindowTitle("Markdown 文件分类移动工具")
        self.resize(1220, 820)
        self.setStyleSheet(self._build_stylesheet())

        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(16, 16, 16, 12)
        root_layout.setSpacing(12)

        content_row = QHBoxLayout()
        content_row.setSpacing(12)

        left_panel = QWidget(container)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        right_panel = QWidget(container)
        right_panel.setObjectName("rightPanel")
        right_panel.setMinimumWidth(340)
        right_panel.setMaximumWidth(420)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.header_label = QLabel("未加载文件")
        self.header_label.setObjectName("headerCard")
        self.header_label.setWordWrap(True)
        self.header_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.header_label.setTextFormat(Qt.TextFormat.RichText)

        self.suggestion_label = QLabel("建议：等待加载")
        self.suggestion_label.setObjectName("suggestionCard")
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.suggestion_label.setTextFormat(Qt.TextFormat.RichText)

        self.category_label = QLabel(self._build_category_html())
        self.category_label.setObjectName("categoryCard")
        self.category_label.setWordWrap(True)
        self.category_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.category_label.setTextFormat(Qt.TextFormat.RichText)

        self.shortcuts_label = QLabel(self._build_shortcuts_html())
        self.shortcuts_label.setObjectName("shortcutCard")
        self.shortcuts_label.setWordWrap(True)
        self.shortcuts_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.shortcuts_label.setTextFormat(Qt.TextFormat.RichText)

        self.content_browser = QTextBrowser()
        self.content_browser.setObjectName("contentBrowser")
        self.content_browser.setOpenExternalLinks(False)

        self.status_label = QLabel("准备就绪")
        self.status_label.setObjectName("statusBar")
        self.status_label.setWordWrap(True)

        left_layout.addWidget(self.content_browser, stretch=1)
        right_layout.addWidget(self.header_label)
        right_layout.addWidget(self.suggestion_label)
        right_layout.addWidget(self.category_label, stretch=1)
        right_layout.addWidget(self.shortcuts_label)

        content_row.addWidget(left_panel, stretch=7)
        content_row.addWidget(right_panel, stretch=3)

        root_layout.addLayout(content_row, stretch=1)
        root_layout.addWidget(self.status_label)
        self.setCentralWidget(container)

    def _build_stylesheet(self) -> str:
        return """
QMainWindow {
    background-color: #f4f7f4;
}
QWidget#rightPanel {
    background: transparent;
}
QLabel#headerCard, QLabel#suggestionCard, QLabel#categoryCard, QLabel#shortcutCard {
    background-color: #ffffff;
    border: 1px solid #d9e8dc;
    border-radius: 10px;
    padding: 10px 12px;
    color: #1f2933;
}
QLabel#suggestionCard {
    border-left: 4px solid #1f8f55;
}
QTextBrowser#contentBrowser {
    background-color: #ffffff;
    border: 1px solid #d9e8dc;
    border-radius: 10px;
    padding: 12px;
}
QLabel#statusBar {
    background-color: #eaf4ec;
    border: 1px solid #cde2d1;
    border-radius: 8px;
    color: #236942;
    padding: 8px 12px;
}
"""

    def _build_category_html(self) -> str:
        emoji_map = {
            "1": "🍚",
            "2": "💰",
            "3": "🎮",
            "4": "👥",
            "5": "🏆",
            "6": "📝",
            "7": "📚",
        }
        lines = ["<b>分类快捷键</b><br/><table width='100%' cellspacing='2' cellpadding='4'>"]
        for key, folder in CATEGORY_MAP.items():
            is_selected = key == self._current_suggestion_key
            bg = "#e6f4ea" if is_selected else "#ffffff"
            text = html.escape(f"[{key}] {emoji_map[key]} {folder} / {CATEGORY_LABELS[key]}")
            if is_selected:
                row_text = f"✅ <b>{text}</b>"
            else:
                row_text = text
            lines.append(
                f"<tr><td bgcolor='{bg}'>{row_text}</td></tr>"
            )
        lines.append("</table>")
        return "".join(lines)

    def _build_shortcuts_html(self) -> str:
        return (
            "<b>快捷操作</b><br/>"
            "<code>[Enter]</code> 接受建议&nbsp;&nbsp;"
            "<code>[S]</code> 跳过&nbsp;&nbsp;"
            "<code>[D]</code> 移到回收站<br/>"
            "<code>[R]</code> 重试建议&nbsp;&nbsp;"
            "<code>[Esc]</code> 退出"
        )

    def _build_header_html(self, note: NoteFile, current_index: int, total: int) -> str:
        file_name = html.escape(note.path.name)
        title = html.escape(note.title)
        return (
            f"<span style='display:inline-block; padding:2px 8px; border-radius:999px; "
            f"background:#eaf4ec; color:#236942; font-weight:700;'>{current_index} / {total}</span>"
            f"<br/><span style='font-size:12px; color:#5b6672;'>{file_name} · "
            f"{note.modified_at:%Y-%m-%d %H:%M:%S}</span>"
            f"<br/><span style='font-size:26px; font-weight:700; color:#0f172a;'>{title}</span>"
        )

    def _wrap_markdown_html(self, body_html: str) -> str:
        return f"""
<html>
  <head>
    <style>
      body {{
        font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
        font-size: 15px;
        line-height: 1.7;
        color: #1f2933;
      }}
      h1 {{ font-size: 28px; margin: 0.5em 0 0.35em 0; color: #0f172a; }}
      h2 {{ font-size: 22px; margin: 0.7em 0 0.4em 0; color: #0f172a; }}
      h3 {{ font-size: 18px; margin: 0.8em 0 0.45em 0; color: #111827; }}
      p {{ margin: 0.45em 0; }}
      ul, ol {{ margin: 0.45em 0 0.45em 1.2em; }}
      li {{ margin: 0.25em 0; }}
      blockquote {{
        margin: 0.75em 0;
        padding: 0.45em 0.8em;
        border-left: 4px solid #8bc5a3;
        background: #f4fbf6;
        color: #4b5563;
      }}
      code {{
        font-family: "JetBrains Mono", "Consolas", monospace;
        background: #f3f4f6;
        border-radius: 4px;
        padding: 1px 4px;
      }}
      pre {{
        background: #f3f4f6;
        border-radius: 8px;
        padding: 10px;
        overflow-x: auto;
      }}
      a {{
        color: #1f8f55;
        text-decoration: none;
      }}
    </style>
  </head>
  <body>
    {body_html}
  </body>
</html>
"""

    def show_note(self, note: NoteFile, current_index: int, total: int) -> None:
        self.header_label.setText(self._build_header_html(note, current_index, total))
        rendered = markdown.markdown(note.content, extensions=["extra", "sane_lists"])
        self.content_browser.setHtml(self._wrap_markdown_html(rendered))
        self.content_browser.moveCursor(QTextCursor.MoveOperation.Start)
        self.status_label.setText("等待分类操作")
        self.set_suggestion_loading()

    def set_suggestion_loading(self) -> None:
        self._current_suggestion_key = None
        self.suggestion_label.setText(
            "<b>💡 建议分类</b><br/>"
            "<span style='color:#236942;'>正在生成中…</span><br/>"
            "<span style='font-size:12px; color:#5b6672;'>稍后可按 Enter 直接采纳建议</span>"
        )
        self.category_label.setText(self._build_category_html())

    def set_suggestion(self, view_model: SuggestionViewModel) -> None:
        self._current_suggestion_key = view_model.accepted_key
        if view_model.is_loading:
            self.set_suggestion_loading()
            return

        if view_model.is_error:
            detail = html.escape(view_model.detail or view_model.title)
            error_html = (
                "<b>⚠ 建议分类不可用</b><br/>"
                f"<span style='color:#b42318;'>{detail}</span><br/>"
                "<span style='font-size:12px; color:#5b6672;'>你仍可按 1-7 手动分类</span>"
            )
            self.suggestion_label.setText(error_html)
            self.category_label.setText(self._build_category_html())
            return

        if view_model.accepted_key and view_model.folder and view_model.confidence_pct is not None:
            filled = max(0, min(100, int(view_model.confidence_pct)))
            block_count = int(filled / 10)
            bar = "█" * block_count + "░" * (10 - block_count)
            accepted_key = html.escape(view_model.accepted_key)
            folder = html.escape(view_model.folder)
            reason = html.escape(view_model.reason or "无")
            suggestion_html = (
                "<b>💡 建议分类</b><br/>"
                f"<span style='display:inline-block; padding:1px 8px; border-radius:999px; "
                f"background:#1f8f55; color:white; font-weight:700;'>[{accepted_key}]</span> "
                f"<b>{folder}</b><br/>"
                "<span style='font-size:12px; color:#5b6672;'>置信度</span> "
                f"<span style='font-weight:700; color:#236942;'>{filled}%</span><br/>"
                f"<span style='color:#236942;'>{bar}</span><br/>"
                f"<span style='font-size:12px; color:#5b6672;'>理由：{reason}</span>"
            )
            self.suggestion_label.setText(suggestion_html)
        else:
            title = html.escape(view_model.title)
            self.suggestion_label.setText(
                f"<b>💡 建议分类</b><br/><span style='color:#236942;'>{title}</span>"
            )
        self.category_label.setText(self._build_category_html())

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def show_completion(self, summary: str) -> None:
        self.header_label.setText(
            "<span style='font-size:26px; font-weight:700; color:#0f172a;'>全部分类完成</span>"
        )
        self.suggestion_label.setText(
            "<b>💡 建议分类</b><br/><span style='color:#5b6672;'>已结束</span>"
        )
        self.category_label.setText(self._build_category_html())
        summary_html = "<br/>".join(summary.splitlines())
        self.content_browser.setHtml(
            self._wrap_markdown_html(
                "<h2>本次统计</h2>"
                f"<blockquote>{summary_html}</blockquote>"
            )
        )
        self.status_label.setText("本轮处理完成，可按 Esc 或直接关闭窗口。")

    def show_empty_state(self, source_dir: str) -> None:
        escaped_dir = html.escape(source_dir)
        self._current_suggestion_key = None
        self.header_label.setText(
            "<span style='font-size:26px; font-weight:700; color:#0f172a;'>无待分类文件</span>"
        )
        self.suggestion_label.setText(
            "<b>💡 建议分类</b><br/><span style='color:#5b6672;'>当前没有可请求的文件</span>"
        )
        self.category_label.setText(self._build_category_html())
        self.content_browser.setHtml(
            self._wrap_markdown_html(
                "<h2>当前扫描结果为空</h2>"
                f"<p>扫描目录：<code>{escaped_dir}</code></p>"
                "<p>仅会读取该目录根目录下的 <code>.md</code> 文件。</p>"
            )
        )
        self.status_label.setText("未发现待分类文件，请检查目录或把文件放回根目录。")

    def confirm_exit(self) -> bool:
        answer = QMessageBox.question(self, "退出确认", "确定要退出吗？")
        return answer == QMessageBox.StandardButton.Yes

    def request_close(self) -> None:
        self._allow_close = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            self._allow_close = False
            super().closeEvent(event)
            return
        self.exit_requested.emit()
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        text = event.text()
        if text in CATEGORY_MAP:
            self.category_selected.emit(text)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept_suggestion_requested.emit()
            return
        if event.key() == Qt.Key_S:
            self.skip_requested.emit()
            return
        if event.key() == Qt.Key_D:
            self.delete_requested.emit()
            return
        if event.key() == Qt.Key_R:
            self.retry_suggestion_requested.emit()
            return
        if event.key() == Qt.Key_Escape:
            self.exit_requested.emit()
            return
        super().keyPressEvent(event)


def create_application() -> QApplication:
    return QApplication.instance() or QApplication([])
