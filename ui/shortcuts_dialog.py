from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QHeaderView,
    QKeySequenceEdit
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QKeySequence

# Default shortcut definitions: (action_id, display_name, default_key)
DEFAULT_SHORTCUTS = [
    ("send_message",      "Enviar mensagem",         "Ctrl+Return"),
    ("new_session",       "Nova sessão de chat",     ""),
    ("open_project",      "Abrir projeto",           "Ctrl+Shift+O"),
    ("open_file",         "Abrir arquivo",           "Ctrl+O"),
    ("save_file",         "Salvar arquivo",          "Ctrl+S"),
    ("toggle_explorer",   "Mostrar/ocultar Explorer","Ctrl+Shift+E"),
    ("toggle_chat",       "Mostrar/ocultar Chat",    "Ctrl+Shift+C"),
    ("toggle_terminal",   "Mostrar/ocultar Terminal","Ctrl+`"),
    ("search_files",      "Buscar nos arquivos",     "Ctrl+Shift+F"),
    ("zoom_in",           "Aumentar fonte editor",   "Ctrl++"),
    ("zoom_out",          "Diminuir fonte editor",   "Ctrl+-"),
    ("toggle_wrap",       "Quebra de linha",         ""),
]


def load_shortcuts() -> dict[str, str]:
    settings = QSettings("DevSeek", "DevSeek")
    result = {}
    for action_id, _, default in DEFAULT_SHORTCUTS:
        result[action_id] = settings.value(f"shortcut/{action_id}", default)
    return result


def save_shortcuts(shortcuts: dict[str, str]):
    settings = QSettings("DevSeek", "DevSeek")
    for action_id, seq in shortcuts.items():
        settings.setValue(f"shortcut/{action_id}", seq)


class ShortcutsDialog(QDialog):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._current = load_shortcuts()
        self.setWindowTitle("Atalhos de teclado — DevSeek")
        self.setMinimumSize(580, 420)
        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        root.addWidget(QLabel("Clique em uma célula de atalho para editar. Deixe vazio para desativar."))

        self._table = QTableWidget(len(DEFAULT_SHORTCUTS), 2)
        self._table.setHorizontalHeaderLabels(["Ação", "Atalho"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)

        self._editors: list[QKeySequenceEdit] = []

        for row, (action_id, display, default) in enumerate(DEFAULT_SHORTCUTS):
            name_item = QTableWidgetItem(display)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row, 0, name_item)

            editor = QKeySequenceEdit(QKeySequence(self._current.get(action_id, default)))
            self._table.setCellWidget(row, 1, editor)
            self._editors.append(editor)

        root.addWidget(self._table, stretch=1)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Restaurar padrões")
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Salvar")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._save)
        btn_row.addWidget(btn_ok)

        root.addLayout(btn_row)

    def _reset(self):
        for row, (action_id, _, default) in enumerate(DEFAULT_SHORTCUTS):
            self._editors[row].setKeySequence(QKeySequence(default))

    def _save(self):
        for row, (action_id, _, _) in enumerate(DEFAULT_SHORTCUTS):
            seq = self._editors[row].keySequence().toString()
            self._current[action_id] = seq
        save_shortcuts(self._current)
        self.accept()

    def _apply_theme(self):
        bg = self._theme.get("editor_bg", "#1E1E1E")
        fg = self._theme.get("editor_fg", "#D4D4D4")
        tab = self._theme.get("tab_bg", "#2D2D2D")
        sel = self._theme.get("selection_bg", "#264F78")
        self.setStyleSheet(f"""
            QDialog, QWidget {{ background: {bg}; color: {fg}; }}
            QTableWidget {{ background: {bg}; color: {fg}; border: 1px solid {tab}; gridline-color: {tab}; }}
            QHeaderView::section {{ background: {tab}; color: {fg}; border: none; padding: 4px; }}
            QTableWidget::item:selected {{ background: {sel}; color: white; }}
            QPushButton {{ background: {tab}; color: {fg}; border: none; border-radius: 4px; padding: 6px 14px; }}
            QPushButton:hover {{ background: {sel}; color: white; }}
            QKeySequenceEdit {{ background: {tab}; color: {fg}; border: 1px solid {sel}; border-radius: 3px; padding: 2px 4px; }}
            QLabel {{ background: transparent; color: {fg}; }}
        """)
