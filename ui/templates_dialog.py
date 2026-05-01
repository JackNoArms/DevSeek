from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPlainTextEdit, QLineEdit, QPushButton, QLabel, QSplitter, QWidget,
    QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from core.prompt_templates import TemplateManager, PromptTemplate


class TemplatesDialog(QDialog):
    template_selected = pyqtSignal(str)   # emits template text

    def __init__(self, manager: TemplateManager, theme: dict, parent=None):
        super().__init__(parent)
        self._mgr = manager
        self._theme = theme
        self.setWindowTitle("Templates de prompt — DevSeek")
        self.setMinimumSize(680, 440)
        self._build_ui()
        self._apply_theme()
        self._refresh_list()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _build_ui(self):
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # Left: list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.addWidget(QLabel("Templates:"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        ll.addWidget(self._list)

        btn_new = QPushButton("＋ Novo")
        btn_new.clicked.connect(self._new_template)
        ll.addWidget(btn_new)

        left.setMaximumWidth(200)
        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nome:"))
        self._name_field = QLineEdit()
        name_row.addWidget(self._name_field, stretch=1)
        rl.addLayout(name_row)

        rl.addWidget(QLabel("Texto do template:"))
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Consolas", 10))
        rl.addWidget(self._editor, stretch=1)

        btn_row = QHBoxLayout()
        self._btn_save = QPushButton("Salvar template")
        self._btn_save.clicked.connect(self._save_template)
        btn_row.addWidget(self._btn_save)

        self._btn_delete = QPushButton("Excluir")
        self._btn_delete.clicked.connect(self._delete_template)
        btn_row.addWidget(self._btn_delete)

        btn_row.addStretch()

        self._btn_use = QPushButton("Usar este template  ▶")
        self._btn_use.setDefault(True)
        self._btn_use.clicked.connect(self._use_template)
        btn_row.addWidget(self._btn_use)

        rl.addLayout(btn_row)
        splitter.addWidget(right)
        splitter.setSizes([180, 500])

        root.addWidget(splitter, stretch=1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.reject)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

    def _refresh_list(self):
        self._list.clear()
        for t in self._mgr.get_all():
            self._list.addItem(QListWidgetItem(t.name))

    def _on_select(self, row: int):
        templates = self._mgr.get_all()
        if row < 0 or row >= len(templates):
            return
        t = templates[row]
        self._name_field.setText(t.name)
        self._editor.setPlainText(t.text)

    def _new_template(self):
        name, ok = QInputDialog.getText(self, "Novo template", "Nome:")
        if ok and name.strip():
            self._mgr.add(PromptTemplate(name=name.strip(), text=""))
            self._refresh_list()
            self._list.setCurrentRow(self._list.count() - 1)

    def _save_template(self):
        row = self._list.currentRow()
        if row < 0:
            return
        t = PromptTemplate(name=self._name_field.text().strip(), text=self._editor.toPlainText())
        self._mgr.update(row, t)
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _delete_template(self):
        row = self._list.currentRow()
        if row < 0:
            return
        answer = QMessageBox.question(self, "Excluir", "Excluir este template?",
                                      QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._mgr.delete(row)
            self._refresh_list()

    def _use_template(self):
        text = self._editor.toPlainText()
        if text:
            self.template_selected.emit(text)
            self.accept()

    def _apply_theme(self):
        bg = self._theme.get("editor_bg", "#1E1E1E")
        fg = self._theme.get("editor_fg", "#D4D4D4")
        side = self._theme.get("sidebar_bg", "#252526")
        tab = self._theme.get("tab_bg", "#2D2D2D")
        sel = self._theme.get("selection_bg", "#264F78")
        self.setStyleSheet(f"""
            QDialog, QWidget {{ background: {bg}; color: {fg}; }}
            QListWidget {{ background: {side}; color: {fg}; border: 1px solid {tab}; border-radius: 4px; }}
            QListWidget::item:selected {{ background: {sel}; color: white; }}
            QPlainTextEdit {{ background: {side}; color: {fg}; border: 1px solid {tab}; border-radius: 4px; }}
            QLineEdit {{ background: {tab}; color: {fg}; border: 1px solid {tab}; border-radius: 4px; padding: 3px 6px; }}
            QPushButton {{ background: {tab}; color: {fg}; border: none; border-radius: 4px; padding: 5px 12px; }}
            QPushButton:hover {{ background: {sel}; color: white; }}
            QLabel {{ background: transparent; color: {fg}; }}
            QSplitter::handle {{ background: {tab}; }}
        """)
