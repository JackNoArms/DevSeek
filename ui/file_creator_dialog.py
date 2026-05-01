from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QPlainTextEdit, QSplitter,
    QWidget, QFileDialog, QMessageBox, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush

from core.code_extractor import DetectedFile
from ui.syntax_highlighter import SyntaxHighlighter


class FileCreatorDialog(QDialog):
    """
    Shows files detected in an AI response and lets the user
    review, rename, and create them in the project directory.
    """

    def __init__(self, files: list[DetectedFile], project_path: str | None, theme: dict, parent=None):
        super().__init__(parent)
        self._files = files
        self._project_path = project_path or str(Path.home())
        self._theme = theme
        self._save_dir = self._project_path
        self._editors: list[QPlainTextEdit] = []
        self._checks:  list[QCheckBox]      = []
        self._names:   list[QLineEdit]      = []

        self.setWindowTitle(f"Criar arquivos detectados ({len(files)}) — DevSeek")
        self.setMinimumSize(860, 560)
        self._build_ui()
        self._apply_theme()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # Save-to directory row
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Salvar em:"))
        self._dir_field = QLineEdit(self._save_dir)
        self._dir_field.setReadOnly(True)
        dir_row.addWidget(self._dir_field, stretch=1)
        btn_browse = QPushButton("Escolher...")
        btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(btn_browse)
        root.addLayout(dir_row)

        splitter = QSplitter(Qt.Horizontal)

        # Left: file list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        lbl = QLabel("Arquivos detectados")
        lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
        left_layout.addWidget(lbl)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["", "Arquivo", "Linguagem"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tree.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self._tree)

        for i, f in enumerate(self._files):
            item = QTreeWidgetItem(["✓", f.filename, f.language])
            item.setData(0, Qt.UserRole, i)
            item.setCheckState(0, Qt.Checked)
            self._tree.addTopLevelItem(item)

        self._tree.resizeColumnToContents(0)
        left.setMinimumWidth(200)
        left.setMaximumWidth(300)
        splitter.addWidget(left)

        # Right: editor preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nome:"))
        self._name_field = QLineEdit()
        self._name_field.setPlaceholderText("nome-do-arquivo.ext")
        name_row.addWidget(self._name_field, stretch=1)
        right_layout.addLayout(name_row)

        self._preview = QPlainTextEdit()
        self._preview.setFont(QFont("Consolas", 10))
        self._preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._hl = None
        right_layout.addWidget(self._preview)

        splitter.addWidget(right)
        splitter.setSizes([240, 620])
        root.addWidget(splitter, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()

        self._chk_all = QCheckBox("Selecionar todos")
        self._chk_all.setChecked(True)
        self._chk_all.toggled.connect(self._toggle_all)
        btn_row.addWidget(self._chk_all)

        btn_row.addStretch()

        self._lbl_status = QLabel("")
        btn_row.addWidget(self._lbl_status)

        self._btn_create = QPushButton("Criar selecionados")
        self._btn_create.setDefault(True)
        self._btn_create.clicked.connect(self._create_files)
        btn_row.addWidget(self._btn_create)

        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

        # Select first item
        if self._tree.topLevelItemCount() > 0:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Escolher diretório", self._save_dir)
        if path:
            self._save_dir = path
            self._dir_field.setText(path)

    def _on_select(self, current, _):
        if not current:
            return
        idx = current.data(0, Qt.UserRole)
        if idx is None:
            return
        f = self._files[idx]
        self._name_field.setText(f.filename)
        self._preview.setPlainText(f.content)

        # Update name field change → live rename
        try:
            self._name_field.textChanged.disconnect()
        except Exception:
            pass
        self._name_field.textChanged.connect(
            lambda text, item=current, i=idx: self._rename(item, i, text)
        )

        # Apply syntax highlighting
        if self._hl:
            self._hl.setDocument(None)
        self._hl = SyntaxHighlighter(self._preview.document(), f.language, self._theme)

        self._preview.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {self._theme.get('editor_bg', '#1E1E1E')};
                color: {self._theme.get('editor_fg', '#D4D4D4')};
                border: none;
                selection-background-color: {self._theme.get('selection_bg', '#264F78')};
            }}
        """)

    def _rename(self, item: QTreeWidgetItem, idx: int, text: str):
        self._files[idx].filename = text
        item.setText(1, text)

    def _toggle_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setCheckState(0, state)

    def _create_files(self):
        save_dir = Path(self._save_dir)
        created, skipped, errors = [], [], []

        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) != Qt.Checked:
                skipped.append(item.text(1))
                continue

            idx = item.data(0, Qt.UserRole)
            f = self._files[idx]
            dest = save_dir / f.filename

            if dest.exists():
                answer = QMessageBox.question(
                    self, "Arquivo existente",
                    f"'{f.filename}' já existe. Sobrescrever?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    skipped.append(f.filename)
                    continue

            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(f.content, encoding="utf-8")
                item.setText(0, "✅")
                item.setForeground(1, QBrush(QColor("#3DD68C")))
                created.append(f.filename)
            except Exception as e:
                item.setText(0, "❌")
                item.setForeground(1, QBrush(QColor("#F44747")))
                errors.append(f"{f.filename}: {e}")

        parts = []
        if created:
            parts.append(f"{len(created)} criado(s)")
        if skipped:
            parts.append(f"{len(skipped)} ignorado(s)")
        if errors:
            parts.append(f"{len(errors)} erro(s)")
        self._lbl_status.setText("  ".join(parts))

        if errors:
            QMessageBox.warning(self, "Erros", "\n".join(errors))

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        bg   = self._theme.get("editor_bg",  "#1E1E1E")
        fg   = self._theme.get("editor_fg",  "#D4D4D4")
        side = self._theme.get("sidebar_bg", "#252526")
        tab  = self._theme.get("tab_bg",     "#2D2D2D")
        sel  = self._theme.get("selection_bg", "#264F78")

        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background-color: {bg};
                color: {fg};
            }}
            QTreeWidget {{
                background-color: {side};
                color: {fg};
                border: 1px solid {tab};
                border-radius: 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {sel};
                color: white;
            }}
            QTreeWidget::item:hover:!selected {{
                background-color: rgba(255,255,255,0.04);
            }}
            QHeaderView::section {{
                background-color: {tab};
                color: {fg};
                border: none;
                padding: 4px;
            }}
            QLineEdit {{
                background-color: {tab};
                color: {fg};
                border: 1px solid {tab};
                border-radius: 4px;
                padding: 4px 6px;
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
            QCheckBox {{
                color: {fg};
            }}
            QSplitter::handle {{
                background: {tab};
            }}
        """)
