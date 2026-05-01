from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QPlainTextEdit, QSplitter, QListWidget, QListWidgetItem, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter

from core.command_parser import CommandResult


class _DiffHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str):
        fmt_add = QTextCharFormat()
        fmt_add.setBackground(QColor("#1a3a1a"))
        fmt_add.setForeground(QColor("#3DD68C"))

        fmt_del = QTextCharFormat()
        fmt_del.setBackground(QColor("#3a1a1a"))
        fmt_del.setForeground(QColor("#F44747"))

        fmt_hdr = QTextCharFormat()
        fmt_hdr.setForeground(QColor("#4FC1FF"))

        if text.startswith("+") and not text.startswith("+++"):
            self.setFormat(0, len(text), fmt_add)
        elif text.startswith("-") and not text.startswith("---"):
            self.setFormat(0, len(text), fmt_del)
        elif text.startswith("@@") or text.startswith("+++") or text.startswith("---"):
            self.setFormat(0, len(text), fmt_hdr)


class DiffDialog(QDialog):
    """Review dialog for file changes.

    preview=True  — shown BEFORE applying (interactive mode).
                    List items have checkboxes; buttons are "Aplicar selecionados" / "Cancelar".
                    Call accepted_indices() after exec_() == Accepted to get which to apply.

    preview=False — shown AFTER applying (auto mode) or for dry-run.
                    Read-only summary with a single "Fechar" button.
    """

    def __init__(self, results: list[CommandResult], theme: dict,
                 parent=None, preview: bool = False):
        super().__init__(parent)
        self._results = results
        self._theme = theme
        self._preview = preview
        self._accepted: list[int] = []

        verb = "Pré-visualizar" if preview else "Resultado"
        self.setWindowTitle(f"{verb} alterações ({len(results)}) — DevSeek")
        self.setMinimumSize(860, 540)
        self._build_ui()
        self._apply_theme()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ── public ────────────────────────────────────────────────────────────────

    def accepted_indices(self) -> list[int]:
        """Indices of commands the user checked (only valid when preview=True)."""
        return self._accepted

    # ── build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        if self._preview:
            root.addWidget(QLabel(
                "Revise as alterações propostas e marque as que deseja aplicar:"
            ))
        else:
            root.addWidget(QLabel("Resultado das alterações aplicadas:"))

        splitter = QSplitter(Qt.Horizontal)

        # Left: command list
        self._list = QListWidget()
        for r in self._results:
            if r.success is None:          # preview pending
                icon = "📝"
            elif r.success:                # applied ok
                icon = "✅"
            else:                          # error
                icon = "❌"

            item = QListWidgetItem(f"{icon}  {r.command.action}  {r.command.path}")
            item.setToolTip(r.message)

            if self._preview:
                # Errors cannot be applied — leave them unchecked and disabled
                if r.success is False:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)

            self._list.addItem(item)

        self._list.currentRowChanged.connect(self._on_select)
        self._list.setMaximumWidth(280)
        splitter.addWidget(self._list)

        # Right: diff / content view
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)

        self._detail_label = QLabel("")
        self._detail_label.setStyleSheet("font-size: 10px; color: #858585; padding: 2px;")
        rl.addWidget(self._detail_label)

        self._diff_view = QPlainTextEdit()
        self._diff_view.setReadOnly(True)
        self._diff_view.setFont(QFont("Consolas", 9))
        self._diff_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._hl = _DiffHighlighter(self._diff_view.document())
        rl.addWidget(self._diff_view)

        splitter.addWidget(right)
        splitter.setSizes([260, 580])
        root.addWidget(splitter, stretch=1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if self._preview:
            btn_cancel = QPushButton("Cancelar tudo")
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

            btn_apply = QPushButton("✅ Aplicar selecionados")
            btn_apply.setDefault(True)
            btn_apply.clicked.connect(self._on_apply)
            btn_row.addWidget(btn_apply)
        else:
            btn_close = QPushButton("Fechar")
            btn_close.clicked.connect(self.accept)
            btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

    def _on_apply(self):
        self._accepted = [
            i for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.Checked
        ]
        self.accept()

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._results):
            return
        r = self._results[row]
        self._detail_label.setText(
            f"{r.command.action}  →  {r.command.path}  |  {r.message}"
        )
        if r.diff:
            self._diff_view.setPlainText(r.diff)
        elif r.command.content:
            self._diff_view.setPlainText(r.command.content)
        else:
            self._diff_view.setPlainText("(sem diff disponível)")

    def _apply_theme(self):
        bg  = self._theme.get("editor_bg", "#1E1E1E")
        fg  = self._theme.get("editor_fg", "#D4D4D4")
        side = self._theme.get("sidebar_bg", "#252526")
        tab  = self._theme.get("tab_bg", "#2D2D2D")
        sel  = self._theme.get("selection_bg", "#264F78")
        self.setStyleSheet(f"""
            QDialog, QWidget {{ background-color: {bg}; color: {fg}; }}
            QListWidget {{ background: {side}; color: {fg}; border: 1px solid {tab}; border-radius: 4px; }}
            QListWidget::item:selected {{ background: {sel}; color: white; }}
            QPlainTextEdit {{ background: {side}; color: {fg}; border: 1px solid {tab}; border-radius: 4px; }}
            QPushButton {{ background: {tab}; color: {fg}; border: none; border-radius: 4px; padding: 6px 14px; }}
            QPushButton:hover {{ background: {sel}; color: white; }}
            QLabel {{ background: transparent; color: {fg}; }}
        """)
