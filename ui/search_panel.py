import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt5.QtGui import QFont


IGNORED = {"__pycache__", "node_modules", ".git", "venv", ".venv", "dist", "build", ".devseek"}
TEXT_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss",
    ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sh", ".bat", ".sql", ".xml", ".java", ".cs", ".cpp", ".c", ".h",
    ".go", ".rs", ".rb", ".php",
}


class _SearchWorker(QThread):
    result_found = pyqtSignal(str, int, str)   # file_path, line_no, line_text
    finished_search = pyqtSignal(int)           # total matches

    def __init__(self, root: str, query: str, use_regex: bool, case_sensitive: bool):
        super().__init__()
        self.root = root
        self.query = query
        self.use_regex = use_regex
        self.case_sensitive = case_sensitive
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = 0
        root = Path(self.root)
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            if self.use_regex:
                pattern = re.compile(self.query, flags)
            else:
                pattern = re.compile(re.escape(self.query), flags)
        except re.error:
            self.finished_search.emit(0)
            return

        for path in root.rglob("*"):
            if self._cancelled:
                break
            if any(part in IGNORED for part in path.parts):
                continue
            if path.suffix.lower() not in TEXT_EXTS:
                continue
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if self._cancelled:
                    break
                if pattern.search(line):
                    rel = str(path.relative_to(root))
                    self.result_found.emit(rel, lineno, line.rstrip())
                    total += 1
                    if total > 2000:
                        self.finished_search.emit(total)
                        return
        self.finished_search.emit(total)


class SearchPanel(QWidget):
    file_match_selected = pyqtSignal(str, int)  # path, line

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: str = ""
        self._worker: _SearchWorker | None = None
        self._file_items: dict[str, QTreeWidgetItem] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        hdr = QLabel("  BUSCAR NOS ARQUIVOS")
        hdr.setStyleSheet("font-size: 10px; font-weight: bold; padding: 6px 4px 2px;")
        layout.addWidget(hdr)

        # Search bar
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 0, 4, 0)
        bar.setSpacing(4)

        self._query = QLineEdit()
        self._query.setPlaceholderText("Buscar... (mín. 3 letras)")
        self._query.setFont(QFont("Consolas", 10))
        self._query.returnPressed.connect(self._start_search)
        self._query.textChanged.connect(self._on_query_changed)
        bar.addWidget(self._query, stretch=1)

        # Debounce timer: waits 400 ms of inactivity before firing the search
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._start_search)

        self._btn_search = QPushButton("🔍")
        self._btn_search.setFixedWidth(30)
        self._btn_search.setFixedHeight(26)
        self._btn_search.clicked.connect(self._start_search)
        bar.addWidget(self._btn_search)

        layout.addLayout(bar)

        # Options
        opts = QHBoxLayout()
        opts.setContentsMargins(4, 0, 4, 0)
        opts.setSpacing(10)
        self._chk_regex = QCheckBox("Regex")
        self._chk_case = QCheckBox("Aa")
        self._chk_case.setToolTip("Sensível a maiúsculas")
        opts.addWidget(self._chk_regex)
        opts.addWidget(self._chk_case)
        opts.addStretch()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 9px; color: #858585;")
        opts.addWidget(self._status_lbl)
        layout.addLayout(opts)

        # Results tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setUniformRowHeights(True)
        self._tree.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self._tree, stretch=1)

    def set_root(self, path: str):
        self._root = path

    def focus_query(self):
        self._query.setFocus()
        self._query.selectAll()

    def _on_query_changed(self, text: str):
        if len(text.strip()) >= 3:
            self._debounce.start()   # restart timer on each keystroke
        else:
            self._debounce.stop()
            self._clear_results()

    def _clear_results(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self._tree.clear()
        self._file_items.clear()
        self._status_lbl.setText("")
        self._btn_search.setEnabled(True)

    def _start_search(self):
        query = self._query.text().strip()
        if len(query) < 3 or not self._root:
            return
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self._tree.clear()
        self._file_items.clear()
        self._status_lbl.setText("Buscando...")
        self._btn_search.setEnabled(False)

        self._worker = _SearchWorker(
            self._root, query,
            self._chk_regex.isChecked(),
            self._chk_case.isChecked(),
        )
        self._worker.result_found.connect(self._on_result)
        self._worker.finished_search.connect(self._on_done)
        self._worker.start()

    @pyqtSlot(str, int, str)
    def _on_result(self, rel_path: str, lineno: int, line: str):
        if rel_path not in self._file_items:
            parent = QTreeWidgetItem([rel_path])
            parent.setData(0, Qt.UserRole, ("file", rel_path))
            self._tree.addTopLevelItem(parent)
            self._file_items[rel_path] = parent
        else:
            parent = self._file_items[rel_path]

        display = f"  {lineno}:  {line[:120]}"
        child = QTreeWidgetItem([display])
        child.setData(0, Qt.UserRole, ("line", rel_path, lineno))
        child.setToolTip(0, line)
        parent.addChild(child)
        parent.setExpanded(True)

    @pyqtSlot(int)
    def _on_done(self, total: int):
        self._btn_search.setEnabled(True)
        suffix = "  (limite atingido)" if total >= 2000 else ""
        self._status_lbl.setText(f"{total} correspondência(s){suffix}")

    def _on_item_activated(self, item: QTreeWidgetItem, _col: int):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data[0] == "line":
            _, rel_path, lineno = data
            full = str(Path(self._root) / rel_path)
            self.file_match_selected.emit(full, lineno)

    def apply_theme(self, theme: dict):
        bg = theme.get("editor_bg", "#1E1E1E")
        fg = theme.get("editor_fg", "#D4D4D4")
        side = theme.get("sidebar_bg", "#252526")
        tab = theme.get("tab_bg", "#2D2D2D")
        sel = theme.get("selection_bg", "#264F78")
        self.setStyleSheet(f"""
            QWidget {{ background-color: {side}; color: {fg}; }}
            QLineEdit {{ background: {bg}; color: {fg}; border: 1px solid {tab}; border-radius: 3px; padding: 3px 6px; }}
            QPushButton {{ background: {tab}; color: {fg}; border: none; border-radius: 3px; padding: 2px 6px; }}
            QPushButton:hover {{ background: {sel}; color: white; }}
            QCheckBox {{ color: {fg}; spacing: 4px; }}
            QTreeWidget {{ background: {bg}; color: {fg}; border: none; outline: none; }}
            QTreeWidget::item:selected {{ background: {sel}; color: white; }}
            QTreeWidget::item:hover {{ background: rgba(255,255,255,0.05); }}
            QLabel {{ background: transparent; color: {fg}; }}
        """)
