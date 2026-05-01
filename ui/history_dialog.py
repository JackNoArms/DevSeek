from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QTextBrowser, QSplitter, QWidget,
    QMessageBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from core.history_manager import HistoryManager


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y  %H:%M")
    except Exception:
        return iso


class HistoryDialog(QDialog):
    session_selected = pyqtSignal(str)   # emits session_id to load

    def __init__(self, history: HistoryManager, current_id: str | None, theme: dict, parent=None):
        super().__init__(parent)
        self.history = history
        self.current_id = current_id
        self.theme = theme
        self._selected_id: str | None = None

        self.setWindowTitle("Histórico de Conversas — DevSeek")
        self.setMinimumSize(720, 480)
        self._build_ui()
        self._apply_theme()
        self._load_sessions()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        # Left: session list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        lbl = QLabel("Sessões")
        lbl.setStyleSheet("font-weight: bold; font-size: 11px; padding-bottom: 4px;")
        left_layout.addWidget(lbl)

        self.session_list = QListWidget()
        self.session_list.setFont(QFont("Segoe UI", 10))
        self.session_list.currentItemChanged.connect(self._on_session_changed)
        left_layout.addWidget(self.session_list)

        left.setMinimumWidth(220)
        left.setMaximumWidth(280)
        splitter.addWidget(left)

        # Right: message preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        lbl2 = QLabel("Mensagens")
        lbl2.setStyleSheet("font-weight: bold; font-size: 11px; padding-bottom: 4px;")
        right_layout.addWidget(lbl2)

        self.preview = QTextBrowser()
        self.preview.setFont(QFont("Segoe UI", 10))
        self.preview.setOpenExternalLinks(False)
        right_layout.addWidget(self.preview)
        splitter.addWidget(right)

        splitter.setSizes([250, 470])
        root.addWidget(splitter)

        # Buttons
        btn_row = QHBoxLayout()

        self.btn_delete = QPushButton("Excluir sessão")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_session)
        btn_row.addWidget(self.btn_delete)

        btn_row.addStretch()

        self.btn_load = QPushButton("Carregar no chat")
        self.btn_load.setEnabled(False)
        self.btn_load.setDefault(True)
        self.btn_load.clicked.connect(self._load_session)
        btn_row.addWidget(self.btn_load)

        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

        root.addLayout(btn_row)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_sessions(self):
        self.session_list.clear()
        sessions = self.history.get_sessions()

        if not sessions:
            item = QListWidgetItem("Nenhuma conversa salva")
            item.setFlags(Qt.NoItemFlags)
            self.session_list.addItem(item)
            return

        for s in sessions:
            label = _fmt_date(s["date"])
            n = s["message_count"]
            preview = s["preview"]
            text = f"{label}\n{n} msg{'s' if n != 1 else ''}  •  {preview[:40]}{'…' if len(preview) > 40 else ''}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s["id"])

            if s["id"] == self.current_id:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
                item.setText(text + "  ◀ atual")

            self.session_list.addItem(item)

    def _on_session_changed(self, current: QListWidgetItem, _):
        if not current:
            return
        sid = current.data(Qt.UserRole)
        if not sid:
            return
        self._selected_id = sid
        self.btn_load.setEnabled(True)
        self.btn_delete.setEnabled(True)
        self._show_preview(sid)

    def _show_preview(self, sid: str):
        self.preview.clear()
        messages = self.history.get_messages(sid)
        if not messages:
            self.preview.setPlainText("Sessão vazia.")
            return

        for msg in messages:
            sender = msg.get("sender", "?")
            text = msg.get("text", "")
            color = msg.get("color", "#D4D4D4")
            ts = msg.get("timestamp", "")
            try:
                ts_fmt = datetime.fromisoformat(ts).strftime("%H:%M:%S")
            except Exception:
                ts_fmt = ts

            escaped = (
                text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br/>")
            )
            html = (
                f'<div style="margin-bottom:10px;">'
                f'<b style="color:{color};">{sender}</b>'
                f'<span style="color:#666; font-size:9px;"> {ts_fmt}</span><br/>'
                f'{escaped}'
                f'</div><hr style="border:none;border-top:1px solid #333;"/>'
            )
            self.preview.append(html)

    def _load_session(self):
        if self._selected_id:
            self.session_selected.emit(self._selected_id)
            self.accept()

    def _delete_session(self):
        if not self._selected_id:
            return
        confirm = QMessageBox.question(
            self, "Confirmar",
            "Excluir esta sessão permanentemente?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.history.delete_session(self._selected_id)
            self._selected_id = None
            self.btn_load.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.preview.clear()
            self._load_sessions()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        bg = self.theme.get("editor_bg", "#1E1E1E")
        fg = self.theme.get("editor_fg", "#D4D4D4")
        side = self.theme.get("sidebar_bg", "#252526")
        tab = self.theme.get("tab_bg", "#2D2D2D")
        sel = self.theme.get("selection_bg", "#264F78")

        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background-color: {bg};
                color: {fg};
            }}
            QListWidget {{
                background-color: {side};
                color: {fg};
                border: 1px solid {tab};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {tab};
            }}
            QListWidget::item:selected {{
                background-color: {sel};
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: rgba(255,255,255,0.05);
            }}
            QTextBrowser {{
                background-color: {side};
                color: {fg};
                border: 1px solid {tab};
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {tab};
                color: {fg};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {sel};
                color: white;
            }}
            QPushButton:disabled {{
                color: #555;
            }}
            QSplitter::handle {{
                background: {tab};
            }}
        """)
