import shutil
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeView, QLabel, QMenu, QAction,
    QInputDialog, QMessageBox, QFileSystemModel, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QDir, QFileInfo
from PyQt5.QtGui import QColor


class FileExplorer(QWidget):
    file_opened = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._root_path = ""
        self._copy_path: str | None = None
        self._cut_mode = False
        self._git_status: dict[str, str] = {}   # rel_path -> status letter
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title = QLabel("  EXPLORER")
        self.title.setStyleSheet("font-size: 10px; font-weight: bold; padding: 6px 5px;")
        layout.addWidget(self.title)

        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.Hidden)
        self.model.directoryLoaded.connect(self._apply_git_colors)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.setUniformRowHeights(True)
        layout.addWidget(self.tree)

        # Shortcuts scoped to the tree only — WidgetWithChildrenShortcut prevents
        # these from intercepting Ctrl+C/X/V in the code editor or other widgets.
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        for key, slot in [
            ("F2",     self._rename_selected),
            ("Ctrl+C", self._copy_selected),
            ("Ctrl+X", self._cut_selected),
            ("Ctrl+V", self._paste),
            ("Delete", self._delete_selected),
        ]:
            sc = QShortcut(QKeySequence(key), self.tree)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)

    # ── Public ────────────────────────────────────────────────────────────────

    def set_root(self, path: str):
        self._root_path = path
        self.model.setRootPath(path)
        self.tree.setRootIndex(self.model.index(path))
        self.title.setText(f"  {Path(path).name.upper()}")
        self._refresh_git()

    def refresh_git(self):
        self._refresh_git()

    # ── Git status ────────────────────────────────────────────────────────────

    def _refresh_git(self):
        if not self._root_path:
            return
        self._git_status = {}
        try:
            result = subprocess.run(
                ["git", "status", "--short", "--porcelain"],
                cwd=self._root_path,
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if len(line) > 3:
                        status = line[:2].strip()
                        rel = line[3:].strip().strip('"')
                        self._git_status[rel] = status
        except Exception:
            pass
        self._apply_git_colors()

    def _apply_git_colors(self, *_):
        if not self._git_status:
            return
        root = Path(self._root_path)
        _STATUS_COLORS = {
            "M":  "#E5C07B",   # modified
            "MM": "#E5C07B",
            "A":  "#98C379",   # added
            "??": "#98C379",   # untracked
            "D":  "#E06C75",   # deleted
            "R":  "#56B6C2",   # renamed
        }
        for rel, st in self._git_status.items():
            color = _STATUS_COLORS.get(st, None)
            if not color:
                continue
            full = str(root / rel)
            idx = self.model.index(full)
            if idx.isValid():
                self.model.setData(idx, QColor(color), Qt.ForegroundRole)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_double_click(self, index: QModelIndex):
        path = self.model.filePath(index)
        if Path(path).is_file():
            self.file_opened.emit(path)

    def _selected_path(self) -> str | None:
        idx = self.tree.currentIndex()
        if idx.isValid():
            return self.model.filePath(idx)
        return None

    def _rename_selected(self):
        path = self._selected_path()
        if not path:
            return
        self._rename(path)

    def _copy_selected(self):
        path = self._selected_path()
        if path:
            self._copy_path = path
            self._cut_mode = False

    def _cut_selected(self):
        path = self._selected_path()
        if path:
            self._copy_path = path
            self._cut_mode = True

    def _delete_selected(self):
        path = self._selected_path()
        if path:
            self._delete(path)

    def _paste(self):
        if not self._copy_path:
            return
        target_path = self._selected_path() or self._root_path
        target_dir = Path(target_path) if Path(target_path).is_dir() else Path(target_path).parent
        src = Path(self._copy_path)
        dest = target_dir / src.name

        # Avoid collision
        if dest.exists():
            base = dest.stem
            ext = dest.suffix
            i = 1
            while dest.exists():
                dest = target_dir / f"{base}_cópia{i}{ext}"
                i += 1

        try:
            if self._cut_mode:
                shutil.move(str(src), str(dest))
                self._copy_path = None
                self._cut_mode = False
            else:
                if src.is_dir():
                    shutil.copytree(str(src), str(dest))
                else:
                    shutil.copy2(str(src), str(dest))
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))

    def _context_menu(self, pos):
        index = self.tree.indexAt(pos)
        menu = QMenu(self)

        if index.isValid():
            path = self.model.filePath(index)
            p = Path(path)

            if p.is_file():
                a = QAction("Abrir", self)
                a.triggered.connect(lambda: self.file_opened.emit(path))
                menu.addAction(a)
                menu.addSeparator()

            rename_a = QAction("Renomear  F2", self)
            rename_a.triggered.connect(lambda: self._rename(path))
            menu.addAction(rename_a)

            copy_a = QAction("Copiar  Ctrl+C", self)
            copy_a.triggered.connect(lambda: self._copy(path))
            menu.addAction(copy_a)

            cut_a = QAction("Recortar  Ctrl+X", self)
            cut_a.triggered.connect(lambda: self._cut(path))
            menu.addAction(cut_a)

            if self._copy_path:
                paste_a = QAction("Colar  Ctrl+V", self)
                paste_a.triggered.connect(self._paste)
                menu.addAction(paste_a)

            menu.addSeparator()

            new_file = QAction("Novo Arquivo...", self)
            new_file.triggered.connect(lambda: self._new_file(path if p.is_dir() else str(p.parent)))
            menu.addAction(new_file)

            new_folder = QAction("Nova Pasta...", self)
            new_folder.triggered.connect(lambda: self._new_folder(path if p.is_dir() else str(p.parent)))
            menu.addAction(new_folder)

            menu.addSeparator()

            delete_action = QAction("Excluir  Del", self)
            delete_action.triggered.connect(lambda: self._delete(path))
            menu.addAction(delete_action)

            menu.addSeparator()

            copy_path_a = QAction("Copiar caminho", self)
            copy_path_a.triggered.connect(lambda: QApplication.clipboard().setText(path))
            menu.addAction(copy_path_a)
        else:
            new_file = QAction("Novo Arquivo...", self)
            new_file.triggered.connect(lambda: self._new_file(self._root_path))
            menu.addAction(new_file)

            new_folder = QAction("Nova Pasta...", self)
            new_folder.triggered.connect(lambda: self._new_folder(self._root_path))
            menu.addAction(new_folder)

            if self._copy_path:
                paste_a = QAction("Colar  Ctrl+V", self)
                paste_a.triggered.connect(self._paste)
                menu.addAction(paste_a)

        if not menu.isEmpty():
            menu.exec_(self.tree.viewport().mapToGlobal(pos))

    # ── File operations ───────────────────────────────────────────────────────

    def _rename(self, path: str):
        p = Path(path)
        new_name, ok = QInputDialog.getText(self, "Renomear", "Novo nome:", text=p.name)
        if ok and new_name.strip() and new_name.strip() != p.name:
            dest = p.parent / new_name.strip()
            try:
                p.rename(dest)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def _copy(self, path: str):
        self._copy_path = path
        self._cut_mode = False

    def _cut(self, path: str):
        self._copy_path = path
        self._cut_mode = True

    def _new_file(self, directory: str):
        name, ok = QInputDialog.getText(self, "Novo Arquivo", "Nome do arquivo:")
        if ok and name.strip():
            fp = Path(directory) / name.strip()
            try:
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.touch()
                self.file_opened.emit(str(fp))
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def _new_folder(self, directory: str):
        name, ok = QInputDialog.getText(self, "Nova Pasta", "Nome da pasta:")
        if ok and name.strip():
            fp = Path(directory) / name.strip()
            try:
                fp.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def _delete(self, path: str):
        p = Path(path)
        confirm = QMessageBox.question(
            self, "Confirmar exclusão",
            f"Excluir '{p.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            try:
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    shutil.rmtree(str(p))
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self, theme: dict):
        sidebar_bg = theme.get("sidebar_bg", "#252526")
        sidebar_fg = theme.get("sidebar_fg", "#CCCCCC")
        sel = theme.get("selection_bg", "#264F78")
        tab = theme.get("tab_bg", "#3C3C3C")

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {sidebar_bg};
                color: {sidebar_fg};
            }}
            QTreeView {{
                background-color: {sidebar_bg};
                color: {sidebar_fg};
                border: none;
                outline: none;
            }}
            QTreeView::item:hover {{
                background-color: rgba(255,255,255,0.05);
            }}
            QTreeView::item:selected {{
                background-color: {sel};
                color: white;
            }}
            QLabel {{
                background-color: {sidebar_bg};
                color: {sidebar_fg};
                font-size: 10px;
                font-weight: bold;
            }}
            QMenu {{
                background-color: {sidebar_bg};
                color: {sidebar_fg};
                border: 1px solid {tab};
            }}
            QMenu::item:selected {{
                background-color: {sel};
            }}
        """)
