import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLineEdit, QPushButton, QLabel, QComboBox
)
from PyQt5.QtCore import Qt, QProcess, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QTextCursor


class TerminalPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cwd = os.path.expanduser("~")
        self._process: QProcess | None = None
        self._history: list[str] = []
        self._hist_idx = -1
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("  TERMINAL")
        lbl.setStyleSheet("font-size: 10px; font-weight: bold; padding: 4px;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        self._shell_combo = QComboBox()
        self._shell_combo.addItems(["cmd", "powershell", "bash"])
        self._shell_combo.setFixedWidth(110)
        self._shell_combo.setFixedHeight(22)
        hdr.addWidget(self._shell_combo)

        btn_clear = QPushButton("Limpar")
        btn_clear.setFixedHeight(22)
        btn_clear.clicked.connect(self._output.clear if hasattr(self, '_output') else lambda: None)
        hdr.addWidget(btn_clear)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(22, 22)
        btn_close.setToolTip("Fechar terminal  (Ctrl+`)")
        btn_close.setStyleSheet(
            "QPushButton { background: transparent; color: #858585; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #F44747; }"
        )
        btn_close.clicked.connect(self.hide)
        hdr.addWidget(btn_close)

        hdr_w = QWidget()
        hdr_w.setLayout(hdr)
        layout.addWidget(hdr_w)

        # Output
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 10))
        self._output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._output.setMaximumBlockCount(2000)
        layout.addWidget(self._output, stretch=1)

        # Fix clear button now that _output exists
        btn_clear.clicked.disconnect()
        btn_clear.clicked.connect(self._output.clear)

        # Input row
        inp = QHBoxLayout()
        inp.setSpacing(4)
        inp.setContentsMargins(4, 4, 4, 4)

        self._prompt_lbl = QLabel("$")
        self._prompt_lbl.setStyleSheet("font-family: Consolas; font-size: 10pt; color: #3DD68C;")
        inp.addWidget(self._prompt_lbl)

        self._input = QLineEdit()
        self._input.setFont(QFont("Consolas", 10))
        self._input.setPlaceholderText("comando...")
        self._input.returnPressed.connect(self._run_command)
        self._input.installEventFilter(self)
        inp.addWidget(self._input, stretch=1)

        btn_run = QPushButton("▶")
        btn_run.setFixedWidth(30)
        btn_run.setFixedHeight(26)
        btn_run.clicked.connect(self._run_command)
        inp.addWidget(btn_run)

        inp_w = QWidget()
        inp_w.setLayout(inp)
        layout.addWidget(inp_w)

        self._write_line("DevSeek Terminal — pronto.", "#858585")

    def set_cwd(self, path: str):
        self._cwd = path
        self._write_line(f"Diretório: {path}", "#4FC1FF")

    def run_command(self, cmd: str):
        """Execute a command programmatically (called by DevSeek protocol RUN action)."""
        self.setVisible(True)
        self._input.setText(cmd)
        self._run_command()

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QKeyEvent
        if obj is self._input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Up:
                self._hist_idx = min(self._hist_idx + 1, len(self._history) - 1)
                if self._history and self._hist_idx >= 0:
                    self._input.setText(self._history[-(self._hist_idx + 1)])
                return True
            if key == Qt.Key_Down:
                self._hist_idx = max(self._hist_idx - 1, -1)
                if self._hist_idx >= 0:
                    self._input.setText(self._history[-(self._hist_idx + 1)])
                else:
                    self._input.clear()
                return True
        return super().eventFilter(obj, event)

    def _run_command(self):
        cmd = self._input.text().strip()
        if not cmd:
            return
        self._history.append(cmd)
        self._hist_idx = -1
        self._input.clear()

        self._write_line(f"$ {cmd}", "#D4D4D4")

        shell = self._shell_combo.currentText()
        if shell == "cmd":
            program, args = "cmd.exe", ["/C", cmd]
        elif shell == "powershell":
            program, args = "powershell.exe", ["-NoProfile", "-Command", cmd]
        else:
            program, args = "bash", ["-c", cmd]

        proc = QProcess(self)
        proc.setWorkingDirectory(self._cwd)
        proc.readyReadStandardOutput.connect(lambda: self._read_stdout(proc))
        proc.readyReadStandardError.connect(lambda: self._read_stderr(proc))
        proc.finished.connect(lambda code, _: self._write_line(f"[saiu com código {code}]", "#858585") if code != 0 else None)
        proc.start(program, args)
        self._process = proc

    def _read_stdout(self, proc: QProcess):
        data = proc.readAllStandardOutput().data()
        try:
            text = data.decode("cp1252", errors="replace")
        except Exception:
            text = data.decode("utf-8", errors="replace")
        self._write_line(text.rstrip(), "#D4D4D4")

    def _read_stderr(self, proc: QProcess):
        data = proc.readAllStandardError().data()
        try:
            text = data.decode("cp1252", errors="replace")
        except Exception:
            text = data.decode("utf-8", errors="replace")
        self._write_line(text.rstrip(), "#F44747")

    def _write_line(self, text: str, color: str = "#D4D4D4"):
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        self._output.setTextCursor(cursor)
        self._output.verticalScrollBar().setValue(
            self._output.verticalScrollBar().maximum()
        )

    def apply_theme(self, theme: dict):
        bg = theme.get("editor_bg", "#1E1E1E")
        fg = theme.get("editor_fg", "#D4D4D4")
        side = theme.get("sidebar_bg", "#252526")
        tab = theme.get("tab_bg", "#2D2D2D")
        sel = theme.get("selection_bg", "#264F78")
        self.setStyleSheet(f"""
            QWidget {{ background-color: {side}; color: {fg}; }}
            QPlainTextEdit {{ background: {bg}; color: {fg}; border: none; }}
            QLineEdit {{ background: {bg}; color: {fg}; border: 1px solid {tab}; border-radius: 3px; padding: 3px 6px; }}
            QPushButton {{ background: {tab}; color: {fg}; border: none; border-radius: 3px; padding: 3px 8px; }}
            QPushButton:hover {{ background: {sel}; color: white; }}
            QComboBox {{ background: {tab}; color: {fg}; border: 1px solid {tab}; padding: 2px 4px; border-radius: 3px; }}
            QComboBox QAbstractItemView {{ background: {tab}; color: {fg}; selection-background-color: {sel}; }}
        """)
