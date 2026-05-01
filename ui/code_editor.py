from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTabBar, QLabel, QShortcut, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence, QFont

from ui.editor_widget import EditorWidget
from ui.syntax_highlighter import SyntaxHighlighter

LANG_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".jsx": "javascript", ".tsx": "typescript",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css",
    ".json": "json", ".jsonc": "json",
}


class CodeEditor(QWidget):
    file_saved = pyqtSignal(str)

    def __init__(self, theme: dict = None, parent=None):
        super().__init__(parent)
        self.theme = theme or {}
        # path -> (EditorWidget, SyntaxHighlighter)
        self._open: dict = {}
        self._word_wrap = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        layout.addWidget(self.tabs)

        self._welcome = QLabel(
            "DevSeek\n\nAbra um projeto via  Arquivo → Abrir Projeto\nou um arquivo via  Ctrl+O"
        )
        self._welcome.setAlignment(Qt.AlignCenter)
        self._welcome.setStyleSheet("color: #858585; font-size: 14px;")
        self.tabs.addTab(self._welcome, "Início")
        self.tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)

        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self._zoom_out)
        QShortcut(QKeySequence("Alt+Z"), self).activated.connect(self.toggle_word_wrap)

    # ── Public API ────────────────────────────────────────────────────────────

    def open_file(self, file_path: str):
        resolved = str(Path(file_path).resolve())

        if resolved in self._open:
            editor, _ = self._open[resolved]
            self.tabs.setCurrentIndex(self.tabs.indexOf(editor))
            return

        self._remove_welcome()

        try:
            content = Path(resolved).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"# Erro ao abrir arquivo\n# {e}"

        editor = EditorWidget()
        editor.apply_theme(self.theme)
        editor.setPlainText(content)
        editor.document().setModified(False)

        ext = Path(resolved).suffix.lower()
        lang = LANG_MAP.get(ext, "text")
        hl = SyntaxHighlighter(editor.document(), lang, self.theme)

        idx = self.tabs.addTab(editor, Path(resolved).name)
        self.tabs.setCurrentIndex(idx)
        self.tabs.setTabToolTip(idx, resolved)

        self._open[resolved] = (editor, hl)

        editor.modificationChanged.connect(self._refresh_tab_titles)

        # Update all titles now that a new file was added (may cause disambiguations)
        self._refresh_tab_titles()

    def save_current(self):
        current = self.tabs.currentWidget()
        for path, (editor, _) in self._open.items():
            if editor is current:
                try:
                    Path(path).write_text(editor.toPlainText(), encoding="utf-8")
                    editor.document().setModified(False)
                    self.file_saved.emit(path)
                except Exception as e:
                    print(f"[DevSeek] Erro ao salvar {path}: {e}")
                return

    def current_file_path(self) -> str | None:
        current = self.tabs.currentWidget()
        for path, (editor, _) in self._open.items():
            if editor is current:
                return path
        return None

    def _zoom_in(self):
        self._change_font_size(1)

    def _zoom_out(self):
        self._change_font_size(-1)

    def _change_font_size(self, delta: int):
        current = self.tabs.currentWidget()
        for path, (editor, _) in self._open.items():
            if editor is current:
                font = editor.font()
                new_size = max(6, min(36, font.pointSize() + delta))
                font.setPointSize(new_size)
                editor.setFont(font)
                from PyQt5.QtGui import QFontMetrics
                editor.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
                return

    def toggle_word_wrap(self):
        from PyQt5.QtWidgets import QPlainTextEdit
        self._word_wrap = not self._word_wrap
        mode = QPlainTextEdit.WidgetWidth if self._word_wrap else QPlainTextEdit.NoWrap
        for _, (editor, _) in self._open.items():
            editor.setLineWrapMode(mode)

    def apply_theme(self, theme: dict):
        self.theme = theme
        editor_bg = theme.get("editor_bg", "#1E1E1E")
        tab_bg = theme.get("tab_bg", "#2D2D2D")
        tab_active = theme.get("tab_active_bg", "#1E1E1E")
        tab_fg = theme.get("tab_fg", "#CCCCCC")

        self.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {editor_bg};
            }}
            QTabBar::tab {{
                background: {tab_bg};
                color: {tab_fg};
                padding: 6px 14px;
                border: none;
                border-right: 1px solid {editor_bg};
                min-width: 80px;
            }}
            QTabBar::tab:selected {{
                background: {tab_active};
                color: white;
                border-top: 2px solid #007ACC;
            }}
            QTabBar::tab:hover:!selected {{
                background: {editor_bg};
            }}
        """)
        self._welcome.setStyleSheet(f"color: {theme.get('sidebar_fg', '#858585')}; font-size: 14px; background: {editor_bg};")

        for path, (editor, hl) in self._open.items():
            editor.apply_theme(theme)
            hl.update_theme(theme)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _remove_welcome(self):
        if self.tabs.count() == 1 and self.tabs.widget(0) is self._welcome:
            self.tabs.removeTab(0)

    def _refresh_tab_titles(self):
        """Recompute all tab labels, disambiguating files that share the same name.

        When two open files have the same filename (e.g. two `models.py`), each
        tab gets the immediate parent folder appended: `models.py — auth/`.
        If that's still ambiguous, we walk up one more level: `models.py — app/auth/`.
        """
        from collections import defaultdict

        # filename -> [absolute paths]
        by_name: dict[str, list[str]] = defaultdict(list)
        for path in self._open:
            by_name[Path(path).name].append(path)

        for path, (editor, _) in self._open.items():
            idx = self.tabs.indexOf(editor)
            if idx < 0:
                continue

            name = Path(path).name
            modified = editor.document().isModified()
            prefix = "● " if modified else ""

            siblings = by_name[name]
            if len(siblings) > 1:
                # Build shortest unique parent suffix to distinguish among siblings
                parts = Path(path).parts  # absolute path parts
                # Start from immediate parent and extend until label is unique
                for depth in range(1, len(parts)):
                    parent_suffix = "/".join(parts[-(depth + 1):-1])
                    candidate = f"{name} — {parent_suffix}/"
                    # Check that no other sibling would produce the same candidate
                    def _label_for(p: str, d: int) -> str:
                        pp = Path(p).parts
                        ps = "/".join(pp[-(d + 1):-1])
                        return f"{Path(p).name} — {ps}/"
                    if len({_label_for(s, depth) for s in siblings}) == len(siblings):
                        label = f"{prefix}{candidate}"
                        break
                else:
                    label = f"{prefix}{name}"
            else:
                label = f"{prefix}{name}"

            self.tabs.setTabText(idx, label)

    def _close_tab(self, index: int):
        widget = self.tabs.widget(index)
        to_remove = next((p for p, (e, _) in self._open.items() if e is widget), None)
        if to_remove:
            del self._open[to_remove]
        self.tabs.removeTab(index)

        if self.tabs.count() == 0:
            self.tabs.addTab(self._welcome, "Início")
            self.tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
        else:
            # A file was removed — siblings may no longer need disambiguation
            self._refresh_tab_titles()
