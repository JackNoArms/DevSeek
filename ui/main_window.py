import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QMenuBar, QMenu, QAction, QFileDialog, QToolBar,
    QComboBox, QLabel, QStatusBar, QMessageBox, QTabWidget
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QKeySequence

from ui.file_explorer import FileExplorer
from ui.code_editor import CodeEditor
from ui.chat_panel import ChatPanel
from ui.terminal_panel import TerminalPanel
from ui.search_panel import SearchPanel
from ui.activity_log import ActivityLog
from ui.theme_dialog import ThemeDialog
from core.context_manager import ContextManager

THEMES_DIR = Path(__file__).parent.parent / "themes"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._themes: dict = {}
        self._current_theme: dict = {}
        self._project_path: str | None = None
        self._context_manager: ContextManager | None = None
        self._settings = QSettings("DevSeek", "DevSeek")

        self.setWindowTitle("DevSeek")
        self.setMinimumSize(1100, 650)
        self.resize(1400, 820)

        self._shortcut_actions: dict = {}   # action_id -> QAction (populated by _build_menu)
        self._load_themes()
        self._build_ui()
        self._build_menu()
        self._apply_shortcuts()             # load saved shortcuts from QSettings
        self._build_toolbar()
        self._build_statusbar()
        self._restore_state()

        saved_theme = self._settings.value("theme", "Dark")
        self._apply_theme_by_name(saved_theme)

    # ── Init helpers ──────────────────────────────────────────────────────────

    def _load_themes(self):
        for fp in THEMES_DIR.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                self._themes[data["name"]] = data
            except Exception:
                pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Main horizontal splitter: explorer | center | chat
        self._splitter = QSplitter(Qt.Horizontal)
        vbox.addWidget(self._splitter)

        # Left panel: file explorer + search (tabbed)
        self._left_tabs = QTabWidget()
        self._left_tabs.setTabPosition(QTabWidget.South)
        self._left_tabs.setDocumentMode(True)

        self._explorer = FileExplorer()
        self._explorer.setMinimumWidth(140)
        self._explorer.file_opened.connect(self._open_file)
        self._left_tabs.addTab(self._explorer, "Explorer")

        self._search = SearchPanel()
        self._search.file_match_selected.connect(self._open_file_at_line)
        self._left_tabs.addTab(self._search, "Buscar")

        self._left_tabs.setMaximumWidth(420)
        self._splitter.addWidget(self._left_tabs)

        # Center: code editor + terminal (vertical splitter)
        self._center_splitter = QSplitter(Qt.Vertical)

        self._editor = CodeEditor(self._current_theme)
        self._editor.file_saved.connect(lambda p: self._status(f"Salvo: {p}"))
        self._center_splitter.addWidget(self._editor)

        self._terminal = TerminalPanel()
        self._terminal.setVisible(False)
        self._terminal.setMinimumHeight(80)
        self._terminal.setMaximumHeight(300)
        self._center_splitter.addWidget(self._terminal)
        self._center_splitter.setSizes([700, 200])

        self._splitter.addWidget(self._center_splitter)

        # Right panel: chat + activity log (tabbed)
        self._right_tabs = QTabWidget()
        self._right_tabs.setTabPosition(QTabWidget.South)
        self._right_tabs.setDocumentMode(True)

        self._chat = ChatPanel()
        self._chat.setMinimumWidth(260)
        self._right_tabs.addTab(self._chat, "Chat")

        self._activity = ActivityLog()
        self._right_tabs.addTab(self._activity, "Atividade")
        self._chat.set_activity_log(self._activity)
        self._chat.run_command_requested.connect(self._run_in_terminal)

        self._right_tabs.setMaximumWidth(620)
        self._splitter.addWidget(self._right_tabs)

        self._splitter.setSizes([220, 820, 360])
        self._splitter.setHandleWidth(1)

    def _build_menu(self):
        mb = self.menuBar()

        # ── Arquivo ───────────────────────────────────────────────────────────
        file_m = mb.addMenu("&Arquivo")

        a = QAction("&Abrir Projeto...", self)
        a.triggered.connect(self._open_project)
        file_m.addAction(a)
        self._shortcut_actions["open_project"] = a

        a = QAction("Abrir &Arquivo...", self)
        a.triggered.connect(self._open_file_dialog)
        file_m.addAction(a)
        self._shortcut_actions["open_file"] = a

        file_m.addSeparator()

        a = QAction("&Salvar", self)
        a.triggered.connect(self._editor.save_current)
        file_m.addAction(a)
        self._shortcut_actions["save_file"] = a

        file_m.addSeparator()

        a = QAction("Sair", self, shortcut="Ctrl+Q")
        a.triggered.connect(self.close)
        file_m.addAction(a)

        # ── View ──────────────────────────────────────────────────────────────
        view_m = mb.addMenu("&View")

        a = QAction("&Personalizar Tema...", self)
        a.triggered.connect(self._open_theme_dialog)
        view_m.addAction(a)

        view_m.addSeparator()

        a = QAction("Explorer", self)
        a.triggered.connect(lambda: self._toggle_panel(self._left_tabs))
        view_m.addAction(a)
        self._shortcut_actions["toggle_explorer"] = a

        a = QAction("Chat", self)
        a.triggered.connect(lambda: self._toggle_panel(self._right_tabs))
        view_m.addAction(a)
        self._shortcut_actions["toggle_chat"] = a

        a = QAction("Terminal", self)
        a.triggered.connect(self._toggle_terminal)
        view_m.addAction(a)
        self._shortcut_actions["toggle_terminal"] = a

        view_m.addSeparator()

        a = QAction("Buscar nos arquivos", self)
        a.triggered.connect(self._focus_search)
        view_m.addAction(a)
        self._shortcut_actions["search_files"] = a

        view_m.addSeparator()

        a = QAction("Quebra de linha", self)
        a.triggered.connect(self._editor.toggle_word_wrap)
        view_m.addAction(a)
        self._shortcut_actions["toggle_wrap"] = a

        a = QAction("Aumentar fonte", self)
        a.triggered.connect(self._editor._zoom_in)
        view_m.addAction(a)
        self._shortcut_actions["zoom_in"] = a

        a = QAction("Diminuir fonte", self)
        a.triggered.connect(self._editor._zoom_out)
        view_m.addAction(a)
        self._shortcut_actions["zoom_out"] = a

        # ── Contexto ──────────────────────────────────────────────────────────
        ctx_m = mb.addMenu("&Contexto")

        a = QAction("&Inicializar / Reinicializar", self)
        a.triggered.connect(self._init_context)
        ctx_m.addAction(a)

        a = QAction("&Atualizar Estrutura", self)
        a.triggered.connect(self._update_structure)
        ctx_m.addAction(a)

        ctx_m.addSeparator()

        a = QAction("Editar &Instruções (.devseek/instructions.md)", self)
        a.triggered.connect(self._edit_instructions)
        ctx_m.addAction(a)

        a = QAction("Editar &Contexto (.devseek/context.json)", self)
        a.triggered.connect(self._edit_context_json)
        ctx_m.addAction(a)

        ctx_m.addSeparator()

        a = QAction("Atualizar indicadores &Git", self)
        a.triggered.connect(lambda: self._explorer.refresh_git())
        ctx_m.addAction(a)

        # ── Configurações ─────────────────────────────────────────────────────
        cfg_m = mb.addMenu("Con&figurações")

        a = QAction("&Atalhos de teclado...", self)
        a.triggered.connect(self._open_shortcuts)
        cfg_m.addAction(a)

        cfg_m.addSeparator()

        self._act_show_browser = QAction("&Mostrar Chrome durante automação", self)
        self._act_show_browser.setCheckable(True)
        _show_browser_saved = self._settings.value("show_browser", False, type=bool)
        self._act_show_browser.setChecked(_show_browser_saved)
        self._act_show_browser.toggled.connect(self._toggle_show_browser)
        cfg_m.addAction(self._act_show_browser)

        # Apply saved value to the bot module right away
        from core.deepseek_bot import set_keep_browser_visible
        set_keep_browser_visible(_show_browser_saved)

    def _build_toolbar(self):
        tb = QToolBar("main")
        tb.setMovable(False)
        tb.setStyleSheet("spacing: 4px; padding: 2px;")
        self.addToolBar(tb)

        tb.addWidget(QLabel("  Tema: "))
        self._theme_combo = QComboBox()
        for name in sorted(self._themes):
            self._theme_combo.addItem(name)
        self._theme_combo.currentTextChanged.connect(self._apply_theme_by_name)
        tb.addWidget(self._theme_combo)

        tb.addSeparator()
        self._project_label = QLabel("  Nenhum projeto aberto")
        tb.addWidget(self._project_label)

    def _build_statusbar(self):
        self._sb = QStatusBar()
        self.setStatusBar(self._sb)
        self._sb.showMessage("Bem-vindo ao DevSeek  —  Abra um projeto para começar")

    # ── Project / file actions ────────────────────────────────────────────────

    def _open_project(self):
        path = QFileDialog.getExistingDirectory(self, "Abrir Projeto", "")
        if path:
            self._load_project(path)

    def _load_project(self, path: str):
        self._project_path = path
        self._explorer.set_root(path)
        self._search.set_root(path)
        self._terminal.set_cwd(path)

        self._context_manager = ContextManager(path)

        name = Path(path).name
        self._project_label.setText(f"  📁 {name}")
        self.setWindowTitle(f"DevSeek — {name}")

        if not self._context_manager.is_initialized:
            self._context_manager.initialize()
            self._status("Contexto DevSeek criado em .devseek/  —  edite as instruções em Contexto → Editar Instruções")
        else:
            self._context_manager.update_structure()
            self._status(f"Projeto '{name}' carregado  —  estrutura atualizada")

        # Set context AFTER initialize() so is_initialized is always True
        self._chat.set_context_manager(self._context_manager)
        self._chat.set_project_path(path)

        self._activity.log("session", f"Projeto '{name}' aberto")
        self._settings.setValue("last_project", path)

    def _open_file(self, path: str):
        self._editor.open_file(path)

    def _open_file_at_line(self, path: str, line: int):
        self._editor.open_file(path)
        # Jump to line after file is opened
        for p, (editor, _) in self._editor._open.items():
            if p == str(Path(path).resolve()):
                from PyQt5.QtGui import QTextCursor
                doc = editor.document()
                block = doc.findBlockByLineNumber(max(0, line - 1))
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.centerCursor()
                break

    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir Arquivo", self._project_path or "")
        if path:
            self._editor.open_file(path)

    # ── Panel toggles ─────────────────────────────────────────────────────────

    def _toggle_panel(self, panel: QWidget):
        panel.setVisible(not panel.isVisible())

    def _toggle_terminal(self):
        self._terminal.setVisible(not self._terminal.isVisible())

    def _run_in_terminal(self, cmd: str):
        """Show terminal and execute a command dispatched by [DEVSEEK_RUN: ...]."""
        self._terminal.setVisible(True)
        self._terminal.run_command(cmd)

    def _focus_search(self):
        self._left_tabs.setCurrentWidget(self._search)
        self._left_tabs.setVisible(True)
        self._search.focus_query()

    # ── Context actions ───────────────────────────────────────────────────────

    def _init_context(self):
        if not self._project_path:
            QMessageBox.information(self, "DevSeek", "Abra um projeto primeiro.")
            return
        self._context_manager.initialize()
        self._status("Contexto DevSeek reinicializado em .devseek/")

    def _update_structure(self):
        if not self._context_manager:
            return
        self._context_manager.update_structure()
        self._status("Estrutura do projeto atualizada em .devseek/structure.txt")

    def _edit_instructions(self):
        if not self._context_manager:
            QMessageBox.information(self, "DevSeek", "Abra um projeto primeiro.")
            return
        if not self._context_manager.is_initialized:
            self._context_manager.initialize()
        self._editor.open_file(str(self._context_manager.instructions_path))

    def _edit_context_json(self):
        if not self._context_manager:
            QMessageBox.information(self, "DevSeek", "Abra um projeto primeiro.")
            return
        if not self._context_manager.is_initialized:
            self._context_manager.initialize()
        self._editor.open_file(str(self._context_manager.context_path))

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _toggle_show_browser(self, checked: bool):
        self._settings.setValue("show_browser", checked)
        from core.deepseek_bot import set_keep_browser_visible
        set_keep_browser_visible(checked)
        self._status(
            "Chrome visível durante automação ✓" if checked
            else "Chrome ocultado durante automação"
        )

    def _apply_shortcuts(self):
        """Read saved shortcuts from QSettings and apply to all registered QActions."""
        from ui.shortcuts_dialog import load_shortcuts
        shortcuts = load_shortcuts()
        for action_id, seq in shortcuts.items():
            if action_id in self._shortcut_actions:
                self._shortcut_actions[action_id].setShortcut(
                    QKeySequence(seq) if seq else QKeySequence()
                )
            elif action_id == "send_message":
                self._chat._send_shortcut.setKey(
                    QKeySequence(seq) if seq else QKeySequence()
                )
        # Update menu text to show current shortcuts
        for action_id, action in self._shortcut_actions.items():
            seq = action.shortcut().toString()
            base = action.text().split("  ")[0]
            action.setText(f"{base}  {seq}" if seq else base)

    def _open_shortcuts(self):
        from ui.shortcuts_dialog import ShortcutsDialog
        dlg = ShortcutsDialog(self._current_theme, self)
        if dlg.exec_():
            self._apply_shortcuts()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _open_theme_dialog(self):
        dlg = ThemeDialog(self._current_theme, self)
        if dlg.exec_():
            custom = dlg.get_theme()
            theme_name = custom.get("name", "Custom")
            # Safe filename from theme name
            safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in theme_name).strip() or "custom"
            custom_path = THEMES_DIR / f"{safe}.json"
            custom_path.write_text(json.dumps(custom, indent=2, ensure_ascii=False), encoding="utf-8")
            self._themes[theme_name] = custom
            if self._theme_combo.findText(theme_name) < 0:
                self._theme_combo.addItem(theme_name)
            self._apply_theme_data(custom)
            self._theme_combo.blockSignals(True)
            self._theme_combo.setCurrentText(theme_name)
            self._theme_combo.blockSignals(False)

    def _apply_theme_by_name(self, name: str):
        if name in self._themes:
            self._apply_theme_data(self._themes[name])
            self._settings.setValue("theme", name)
            idx = self._theme_combo.findText(name)
            if idx >= 0:
                self._theme_combo.blockSignals(True)
                self._theme_combo.setCurrentIndex(idx)
                self._theme_combo.blockSignals(False)

    def _apply_theme_data(self, theme: dict):
        self._current_theme = theme
        bg = theme.get("editor_bg", "#1E1E1E")
        fg = theme.get("editor_fg", "#D4D4D4")
        side = theme.get("sidebar_bg", "#252526")
        side_fg = theme.get("sidebar_fg", "#CCCCCC")
        tab = theme.get("tab_bg", "#2D2D2D")
        sel = theme.get("selection_bg", "#264F78")

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {fg};
            }}
            QMenuBar {{
                background-color: {side};
                color: {side_fg};
            }}
            QMenuBar::item:selected {{
                background-color: {tab};
            }}
            QMenu {{
                background-color: {side};
                color: {side_fg};
                border: 1px solid {tab};
            }}
            QMenu::item:selected {{
                background-color: {sel};
                color: white;
            }}
            QToolBar {{
                background-color: {side};
                border: none;
            }}
            QLabel {{
                background: transparent;
                color: {side_fg};
            }}
            QComboBox {{
                background-color: {tab};
                color: {fg};
                border: 1px solid {tab};
                padding: 2px 6px;
                border-radius: 3px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {tab};
                color: {fg};
                selection-background-color: {sel};
            }}
            QStatusBar {{
                background-color: {side};
                color: {side_fg};
            }}
            QSplitter::handle {{
                background-color: {tab};
            }}
            QTabWidget::pane {{
                border: none;
                background: {bg};
            }}
            QTabBar::tab {{
                background: {tab};
                color: {side_fg};
                padding: 4px 12px;
                border: none;
            }}
            QTabBar::tab:selected {{
                background: {bg};
                color: white;
                border-top: 2px solid #007ACC;
            }}
            QTabBar::tab:hover:!selected {{
                background: {bg};
            }}
            QScrollBar:vertical {{
                background: {side};
                width: 10px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {tab};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar:horizontal {{
                background: {side};
                height: 10px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {tab};
                border-radius: 5px;
                min-width: 20px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: none;
                border: none;
            }}
        """)

        self._explorer.apply_theme(theme)
        self._search.apply_theme(theme)
        self._editor.apply_theme(theme)
        self._chat.apply_theme(theme)
        self._terminal.apply_theme(theme)
        self._activity.apply_theme(theme)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._sb.showMessage(msg, 8000)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _restore_state(self):
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = self._settings.value("window_state")
        if state:
            self.restoreState(state)
        last = self._settings.value("last_project")
        if last and Path(last).exists():
            self._load_project(last)

    def closeEvent(self, event):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("window_state", self.saveState())
        try:
            from core.deepseek_bot import close_browser
            close_browser()
        except Exception:
            pass
        super().closeEvent(event)
