from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


_COLORS = {
    "file_create":  "#3DD68C",
    "file_update":  "#4FC1FF",
    "file_delete":  "#F44747",
    "file_move":    "#CE9178",
    "prompt_send":  "#C586C0",
    "session":      "#858585",
    "error":        "#F44747",
    "info":         "#858585",
}

_ICONS = {
    "file_create":  "✅",
    "file_update":  "✏️",
    "file_delete":  "🗑️",
    "file_move":    "➡️",
    "prompt_send":  "📤",
    "session":      "💬",
    "error":        "❌",
    "info":         "ℹ️",
}


class ActivityLog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QHBoxLayout()
        lbl = QLabel("  LOG DE ATIVIDADE")
        lbl.setStyleSheet("font-size: 10px; font-weight: bold; padding: 6px 4px;")
        hdr.addWidget(lbl)
        hdr.addStretch()

        btn_clear = QPushButton("Limpar")
        btn_clear.setFixedHeight(22)
        btn_clear.clicked.connect(self._list.clear if hasattr(self, '_list') else lambda: None)
        hdr.addWidget(btn_clear)

        hdr_w = QWidget()
        hdr_w.setLayout(hdr)
        layout.addWidget(hdr_w)

        self._list = QListWidget()
        self._list.setWordWrap(True)
        self._list.setUniformItemSizes(False)
        layout.addWidget(self._list, stretch=1)

        btn_clear.clicked.disconnect()
        btn_clear.clicked.connect(self._list.clear)

    def log(self, event_type: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        icon = _ICONS.get(event_type, "•")
        color = _COLORS.get(event_type, "#D4D4D4")
        text = f"{ts}  {icon}  {message}"
        item = QListWidgetItem(text)
        item.setForeground(QColor(color))
        item.setToolTip(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {message}")
        self._list.addItem(item)
        self._list.scrollToBottom()

    def apply_theme(self, theme: dict):
        bg = theme.get("editor_bg", "#1E1E1E")
        fg = theme.get("editor_fg", "#D4D4D4")
        side = theme.get("sidebar_bg", "#252526")
        tab = theme.get("tab_bg", "#2D2D2D")
        sel = theme.get("selection_bg", "#264F78")
        self.setStyleSheet(f"""
            QWidget {{ background-color: {side}; color: {fg}; }}
            QListWidget {{ background: {bg}; color: {fg}; border: none; font-family: Consolas; font-size: 9pt; }}
            QListWidget::item {{ padding: 2px 4px; }}
            QListWidget::item:selected {{ background: {sel}; }}
            QPushButton {{ background: {tab}; color: {fg}; border: none; border-radius: 3px; padding: 3px 8px; }}
            QPushButton:hover {{ background: {sel}; color: white; }}
            QLabel {{ background: transparent; color: {fg}; }}
        """)
