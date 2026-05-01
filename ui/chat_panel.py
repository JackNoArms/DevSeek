import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QPlainTextEdit, QPushButton, QCheckBox, QLabel,
    QFrame, QSizePolicy, QShortcut, QProgressBar, QRadioButton,
    QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QKeySequence

from core.deepseek_bot import DeepSeekWorker, DeepSeekStatusWorker, DeepSeekLoginWorker, FINISH_MARKER
from core.file_searcher import FileSearcher
from core.history_manager import HistoryManager
from core.code_extractor import md_to_html, extract_files, DetectedFile
from core.command_parser import parse_commands, apply_command, preview_command, extract_chat_text

# ── Response display cleaner ──────────────────────────────────────────────────

# Pass 1: remove complete [DEVSEEK_CREATE/UPDATE/REPLACE: ...] blocks (with content)
_RE_CMD_BLOCK = re.compile(
    r'\[DEVSEEK_(?:CREATE|UPDATE|REPLACE):[^\]]*\].*?\[/DEVSEEK_(?:CREATE|UPDATE|REPLACE)\]\n?',
    re.DOTALL,
)
# Pass 2: remove any remaining single-line markers (opening, closing, or bare like DEVSEEK_MAIS/FIM)
_RE_CMD_MARKER = re.compile(r'\[/?DEVSEEK_\w+[^\]]*\]\n?')
# Pass 3: remove UI button labels that appear as bare lines in extracted text
_RE_UI_NOISE = re.compile(
    r'^(Copiar|Baixar|Executar|Copy|Download|Run)\s*$',
    re.MULTILINE,
)


def _clean_for_display(text: str) -> str:
    """Strip DEVSEEK markers and DeepSeek UI noise before rendering in chat.

    The original text must be kept intact for parse_commands() — this function
    only operates on the copy used for display.
    """
    text = _RE_CMD_BLOCK.sub('', text)
    text = _RE_CMD_MARKER.sub('', text)
    text = _RE_UI_NOISE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# Instruction appended to every prompt so DeepSeek signals end-of-response
_FINISH_INSTRUCTION = (
    "\n\n---\n"
    "**INSTRUÇÃO DO SISTEMA (DevSeek):** Ao terminar completamente esta resposta, "
    f"escreva exatamente `{FINISH_MARKER}` na última linha — sem nada depois."
)

# Connection status presets: (dot_color, label_text)
_ST_UNKNOWN  = ("gray",    "Não verificado")
_ST_CHECKING = ("#F0B429", "Verificando...")
_ST_LOGIN    = ("#F0B429", "Abrindo login...")
_ST_OK       = ("#3DD68C", "Conectado")
_ST_FAIL     = ("#F44747", "Não autenticado")
_ST_ERROR    = ("#F44747", "Erro de conexão")

# Rough token estimate (4 chars/token)
_TOKEN_LIMIT = 64_000


class _Dot(QLabel):
    def __init__(self):
        super().__init__()
        self.setFixedSize(12, 12)
        self.set_color("gray")

    def set_color(self, color: str):
        self.setStyleSheet(
            f"background-color:{color}; border-radius:6px;"
            f"border:1px solid rgba(255,255,255,0.2);"
        )


class ChatPanel(QWidget):
    run_command_requested = pyqtSignal(str)   # emitted when [DEVSEEK_RUN: cmd] is applied

    def __init__(self):
        super().__init__()
        self.context_manager = None
        self.project_path: str | None = None
        self._history_mgr: HistoryManager | None = None
        self._template_mgr = None
        self._current_theme: dict = {}
        self._activity_log = None    # injected from main_window

        self._worker: DeepSeekWorker | None = None
        self._status_worker: DeepSeekStatusWorker | None = None
        self._login_worker: DeepSeekLoginWorker | None = None

        self._pending_files: dict[str, list[DetectedFile]] = {}
        self._pending_commands: dict[str, list] = {}  # anchor_id -> commands

        self._session_tokens = 0     # running token estimate

        self._setup_ui()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header row
        hdr_row = QHBoxLayout()
        hdr = QLabel("  DEEPSEEK  CHAT")
        hdr.setStyleSheet("font-size: 10px; font-weight: bold;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        self.btn_templates = QPushButton("📝 Templates")
        self.btn_templates.setFixedHeight(24)
        self.btn_templates.setToolTip("Inserir prompt de template")
        self.btn_templates.clicked.connect(self._open_templates)
        hdr_row.addWidget(self.btn_templates)

        self.btn_history = QPushButton("📋 Histórico")
        self.btn_history.setFixedHeight(24)
        self.btn_history.setToolTip("Ver / carregar conversas anteriores")
        self.btn_history.clicked.connect(self._open_history)
        hdr_row.addWidget(self.btn_history)

        self.btn_new = QPushButton("＋ Nova")
        self.btn_new.setFixedHeight(24)
        self.btn_new.setToolTip("Iniciar nova conversa (salva a atual)")
        self.btn_new.clicked.connect(self._new_session)
        hdr_row.addWidget(self.btn_new)

        layout.addLayout(hdr_row)
        layout.addWidget(self._sep())

        # Session label
        self._session_label = QLabel("")
        self._session_label.setStyleSheet("font-size: 9px; color: #858585; padding: 1px 2px;")
        layout.addWidget(self._session_label)

        # Connection status row
        conn = QHBoxLayout()
        conn.setSpacing(6)

        self._dot = _Dot()
        conn.addWidget(self._dot)

        self._conn_label = QLabel("Não verificado")
        self._conn_label.setStyleSheet("font-size: 10px;")
        conn.addWidget(self._conn_label, stretch=1)

        self._btn_check = QPushButton("Verificar")
        self._btn_check.setFixedHeight(24)
        self._btn_check.setToolTip("Checa silenciosamente se o DeepSeek está autenticado")
        self._btn_check.clicked.connect(self._check_status)

        self._btn_login = QPushButton("Login")
        self._btn_login.setFixedHeight(24)
        self._btn_login.setToolTip("Abre o navegador para fazer login no DeepSeek")
        self._btn_login.clicked.connect(self._do_login)

        conn.addWidget(self._btn_check)
        conn.addWidget(self._btn_login)

        conn_w = QWidget()
        conn_w.setLayout(conn)
        layout.addWidget(conn_w)
        layout.addWidget(self._sep())

        # Context flags
        flags = QHBoxLayout()
        flags.setContentsMargins(0, 2, 0, 2)
        flags.setSpacing(8)

        self.chk_structure = QCheckBox("Estrutura")
        self.chk_structure.setChecked(True)
        self.chk_structure.setToolTip("Inclui a estrutura de pastas do projeto no contexto")

        self.chk_instructions = QCheckBox("Instruções")
        self.chk_instructions.setChecked(True)
        self.chk_instructions.setToolTip("Inclui as instruções de .devseek/instructions.md")

        self.chk_search = QCheckBox("Buscar arquivos")
        self.chk_search.setChecked(True)
        self.chk_search.setToolTip("Busca arquivos relevantes no projeto e os inclui")

        flags.addWidget(self.chk_structure)
        flags.addWidget(self.chk_instructions)
        flags.addWidget(self.chk_search)
        flags.addStretch()

        flags_w = QWidget()
        flags_w.setLayout(flags)
        layout.addWidget(flags_w)

        # DeepSeek mode selector: Rápido / Especialista
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 2, 0, 2)
        mode_row.setSpacing(0)

        self._btn_rapido = QPushButton("⚡ Rápido")
        self._btn_rapido.setCheckable(True)
        self._btn_rapido.setChecked(True)
        self._btn_rapido.setFixedHeight(26)
        self._btn_rapido.setToolTip("Modo rápido (V3) — respostas mais velozes")
        self._btn_rapido.clicked.connect(lambda: self._set_ds_mode("rapido"))

        self._btn_especialista = QPushButton("🧠 Especialista")
        self._btn_especialista.setCheckable(True)
        self._btn_especialista.setChecked(False)
        self._btn_especialista.setFixedHeight(26)
        self._btn_especialista.setToolTip("Modo especialista (R1) — raciocínio profundo, mais lento")
        self._btn_especialista.clicked.connect(lambda: self._set_ds_mode("especialista"))

        mode_row.addWidget(self._btn_rapido)
        mode_row.addWidget(self._btn_especialista)

        mode_row.addSpacing(12)

        self.chk_pensamento = QCheckBox("🧩 Pensamento Profundo")
        self.chk_pensamento.setToolTip("Ativa raciocínio passo a passo antes de responder")
        mode_row.addWidget(self.chk_pensamento)

        self.chk_web_search = QCheckBox("🌐 Pesquisa inteligente")
        self.chk_web_search.setToolTip("Ativa busca na web antes de responder")
        mode_row.addWidget(self.chk_web_search)
        mode_row.addStretch()

        mode_w = QWidget()
        mode_w.setLayout(mode_row)
        layout.addWidget(mode_w)

        # Safety mode row for command application
        safety_row = QHBoxLayout()
        safety_row.setContentsMargins(0, 0, 0, 2)
        safety_row.setSpacing(6)
        safety_lbl = QLabel("Aplicar:")
        safety_lbl.setStyleSheet("font-size: 9px; color: #858585;")
        safety_row.addWidget(safety_lbl)

        self._safety_group = QButtonGroup(self)
        self._rb_interactive = QRadioButton("Interativo")
        self._rb_auto = QRadioButton("Auto")
        self._rb_dry = QRadioButton("Dry run")
        self._rb_interactive.setChecked(True)
        for rb in (self._rb_interactive, self._rb_auto, self._rb_dry):
            rb.setStyleSheet("font-size: 9px;")
            self._safety_group.addButton(rb)
            safety_row.addWidget(rb)

        help_btn = QPushButton("?")
        help_btn.setFixedSize(18, 18)
        help_btn.setStyleSheet("""
            QPushButton {
                background: #444; color: #ccc; border-radius: 9px;
                font-size: 9px; font-weight: bold; border: none; padding: 0;
            }
            QPushButton:hover { background: #007ACC; color: white; }
        """)
        help_btn.clicked.connect(self._show_mode_help)
        safety_row.addWidget(help_btn)
        safety_row.addStretch()
        safety_w = QWidget()
        safety_w.setLayout(safety_row)
        layout.addWidget(safety_w)

        layout.addWidget(self._sep())

        # Chat history view
        self.history_view = QTextBrowser()
        self.history_view.setOpenLinks(False)          # let anchorClicked reach our handler
        self.history_view.setOpenExternalLinks(False)
        self.history_view.setFont(QFont("Segoe UI", 10))
        self.history_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.history_view.anchorClicked.connect(self._on_anchor_clicked)
        layout.addWidget(self.history_view, stretch=1)

        # Token usage bar
        token_row = QHBoxLayout()
        token_row.setContentsMargins(0, 2, 0, 0)
        token_row.setSpacing(4)
        self._token_lbl = QLabel("0 tokens")
        self._token_lbl.setStyleSheet("font-size: 9px; color: #858585;")
        token_row.addWidget(self._token_lbl)
        self._token_bar = QProgressBar()
        self._token_bar.setMaximum(100)
        self._token_bar.setValue(0)
        self._token_bar.setFixedHeight(4)
        self._token_bar.setTextVisible(False)
        token_row.addWidget(self._token_bar, stretch=1)
        layout.addLayout(token_row)

        # Automation status
        self._auto_status = QLabel("")
        self._auto_status.setStyleSheet("font-size: 9px; color: #858585; padding: 1px 2px;")
        self._auto_status.setWordWrap(True)
        layout.addWidget(self._auto_status)

        # Persistent error details pane so long exceptions stay visible and easy to copy.
        error_hdr_row = QHBoxLayout()
        error_hdr_row.setContentsMargins(0, 0, 0, 0)
        error_hdr_row.setSpacing(6)

        self._error_lbl = QLabel("Detalhes do erro")
        self._error_lbl.setStyleSheet("font-size: 9px; color: #F44747; font-weight: bold;")
        error_hdr_row.addWidget(self._error_lbl)
        error_hdr_row.addStretch()

        self._btn_copy_error = QPushButton("Copiar erro")
        self._btn_copy_error.setFixedHeight(22)
        self._btn_copy_error.clicked.connect(self._copy_error_details)
        error_hdr_row.addWidget(self._btn_copy_error)

        self._btn_hide_error = QPushButton("Ocultar")
        self._btn_hide_error.setFixedHeight(22)
        self._btn_hide_error.clicked.connect(self._clear_error_details)
        error_hdr_row.addWidget(self._btn_hide_error)

        self._error_hdr = QWidget()
        self._error_hdr.setLayout(error_hdr_row)
        self._error_hdr.setVisible(False)
        layout.addWidget(self._error_hdr)

        self._error_view = QPlainTextEdit()
        self._error_view.setReadOnly(True)
        self._error_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._error_view.setMinimumHeight(90)
        self._error_view.setMaximumHeight(220)
        self._error_view.setFont(QFont("Consolas", 9))
        self._error_view.setVisible(False)
        layout.addWidget(self._error_view)

        layout.addWidget(self._sep())

        # Input
        self.input_field = QPlainTextEdit()
        self.input_field.setMaximumHeight(90)
        self.input_field.setMinimumHeight(60)
        self.input_field.setPlaceholderText("Digite sua pergunta... (Ctrl+Enter para enviar)")
        self.input_field.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.input_field)

        # Button row
        btn_row = QHBoxLayout()

        self.clear_btn = QPushButton("Limpar")
        self.clear_btn.setMaximumWidth(70)
        self.clear_btn.setToolTip("Limpa a visualização (mantém o histórico salvo)")
        self.clear_btn.clicked.connect(self._clear_view)
        btn_row.addWidget(self.clear_btn)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setMaximumWidth(80)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self.cancel_btn)

        btn_row.addStretch()

        self.send_btn = QPushButton("Enviar  ▶")
        self.send_btn.setDefault(True)
        self.send_btn.setMinimumWidth(90)
        self.send_btn.clicked.connect(self._send)
        btn_row.addWidget(self.send_btn)

        layout.addLayout(btn_row)

        # Scoped to the chat panel so it doesn't fire when the code editor has focus.
        sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc.setContext(Qt.WidgetWithChildrenShortcut)
        sc.activated.connect(self._send)
        self._send_shortcut = sc
        self._refresh_mode_buttons()

    def _sep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFrameShadow(QFrame.Sunken)
        return f

    # ── Public API ────────────────────────────────────────────────────────────

    def set_context_manager(self, ctx):
        self.context_manager = ctx
        # Always reset view when switching projects
        self.history_view.clear()
        self._history_mgr = None
        self._pending_files.clear()
        self._pending_commands.clear()
        self._clear_error_details(clear_status=False)
        self._session_tokens = 0
        self._update_token_bar(0)
        self._session_label.setText("")
        if ctx and ctx.is_initialized:
            self._init_history(ctx)
            self._init_templates(ctx)

    def set_project_path(self, path: str):
        self.project_path = path

    def set_activity_log(self, log):
        self._activity_log = log

    def _init_history(self, ctx):
        self._history_mgr = HistoryManager(ctx.devseek_path)
        self._history_mgr.resume_last_session()
        self._restore_current_session()
        self._update_session_label()

    def _init_templates(self, ctx):
        from core.prompt_templates import TemplateManager
        self._template_mgr = TemplateManager(ctx.devseek_path)

    # ── History ───────────────────────────────────────────────────────────────

    def _restore_current_session(self):
        if not self._history_mgr:
            return
        self.history_view.clear()
        self._clear_error_details(clear_status=False)
        self._session_tokens = 0
        for msg in self._history_mgr.get_current_messages():
            self._render_bubble(msg["sender"], msg["text"], msg["color"])

    def _update_session_label(self):
        if not self._history_mgr or not self._history_mgr.current_session_id:
            self._session_label.setText("")
            return
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(self._history_mgr.current_session_id)
            self._session_label.setText(f"Sessão: {dt.strftime('%d/%m/%Y  %H:%M')}")
        except Exception:
            self._session_label.setText(f"Sessão: {self._history_mgr.current_session_id}")

    def _new_session(self):
        if not self._history_mgr:
            return
        self._history_mgr.new_session()
        self.history_view.clear()
        self._clear_error_details(clear_status=False)
        self._session_tokens = 0
        self._update_token_bar(0)
        self._update_session_label()
        if self._activity_log:
            self._activity_log.log("session", "Nova sessão de chat iniciada")

    def _open_history(self):
        if not self._history_mgr:
            return
        from ui.history_dialog import HistoryDialog
        dlg = HistoryDialog(
            self._history_mgr,
            self._history_mgr.current_session_id,
            self._current_theme,
            self,
        )
        dlg.session_selected.connect(self._load_session)
        dlg.exec_()

    def _load_session(self, session_id: str):
        if not self._history_mgr:
            return
        self._history_mgr._current_id = session_id
        self._restore_current_session()
        self._update_session_label()

    def _set_ds_mode(self, mode: str):
        self._btn_rapido.setChecked(mode == "rapido")
        self._btn_especialista.setChecked(mode == "especialista")
        # Update visual style
        self._refresh_mode_buttons()

    def _refresh_mode_buttons(self):
        active_style = (
            "QPushButton { background: #007ACC; color: white; border: none; "
            "border-radius: 4px; padding: 3px 10px; font-weight: bold; }"
        )
        inactive_style = (
            "QPushButton { background: transparent; color: #858585; border: 1px solid #555; "
            "border-radius: 4px; padding: 3px 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.08); color: white; }"
        )
        self._btn_rapido.setStyleSheet(
            active_style if self._btn_rapido.isChecked() else inactive_style
        )
        self._btn_especialista.setStyleSheet(
            active_style if self._btn_especialista.isChecked() else inactive_style
        )

    def _show_mode_help(self):
        from PyQt5.QtWidgets import QMessageBox
        mb = QMessageBox(self)
        mb.setWindowTitle("Modos de Aplicação de Comandos")
        mb.setTextFormat(Qt.RichText)
        mb.setText(
            "<b>Modos de aplicação de comandos do DeepSeek:</b><br><br>"
            "<b>Interativo</b> — Pergunta antes de cada alteração.<br>"
            "Você aprova ou rejeita arquivo por arquivo.<br><br>"
            "<b>Auto</b> — Aplica tudo imediatamente, sem perguntar.<br>"
            "Um backup é salvo em <code>.devseek/backups/</code> antes de cada mudança.<br><br>"
            "<b>Dry run</b> — Nenhum arquivo é modificado.<br>"
            "Mostra apenas o que <i>seria</i> feito — ideal para revisar antes de aplicar."
        )
        mb.setIcon(QMessageBox.Information)
        mb.exec_()

    def _open_templates(self):
        if not self._template_mgr:
            return
        from ui.templates_dialog import TemplatesDialog
        dlg = TemplatesDialog(self._template_mgr, self._current_theme, self)
        dlg.template_selected.connect(self._insert_template)
        dlg.exec_()

    def _insert_template(self, text: str):
        self.input_field.setPlainText(text)
        self.input_field.setFocus()

    # ── Token usage ───────────────────────────────────────────────────────────

    def _update_token_bar(self, tokens: int):
        self._token_lbl.setText(f"~{tokens:,} tokens")
        pct = min(100, int(tokens * 100 / _TOKEN_LIMIT))
        self._token_bar.setValue(pct)
        if pct >= 90:
            self._token_bar.setStyleSheet("QProgressBar::chunk { background: #F44747; }")
        elif pct >= 70:
            self._token_bar.setStyleSheet("QProgressBar::chunk { background: #F0B429; }")
        else:
            self._token_bar.setStyleSheet("QProgressBar::chunk { background: #3DD68C; }")

    # ── Connection status ─────────────────────────────────────────────────────

    def _set_conn(self, color: str, text: str):
        self._dot.set_color(color)
        self._conn_label.setText(text)

    def _check_status(self):
        if self._status_worker and self._status_worker.isRunning():
            return
        self._set_conn(*_ST_CHECKING)
        self._btn_check.setEnabled(False)
        self._btn_login.setEnabled(False)

        self._status_worker = DeepSeekStatusWorker()
        self._status_worker.result.connect(self._on_status_result)
        self._status_worker.finished.connect(
            lambda: (self._btn_check.setEnabled(True), self._btn_login.setEnabled(True))
        )
        self._status_worker.start()

    @pyqtSlot(bool, str)
    def _on_status_result(self, ok: bool, msg: str):
        if ok:
            self._set_conn(*_ST_OK)
            return

        self._set_conn(_ST_FAIL[0], self._summarize_status(msg))
        self._show_error_details(msg, add_bubble=False)
        if self._activity_log:
            self._activity_log.log("error", msg)

    def _do_login(self):
        if self._login_worker and self._login_worker.isRunning():
            return
        self._set_conn(*_ST_LOGIN)
        self._btn_check.setEnabled(False)
        self._btn_login.setEnabled(False)

        self._login_worker = DeepSeekLoginWorker()
        self._login_worker.status_update.connect(
            lambda m: self._set_conn(_ST_LOGIN[0], self._summarize_status(m))
        )
        self._login_worker.login_success.connect(lambda: self._set_conn(*_ST_OK))
        self._login_worker.login_failed.connect(self._on_login_failed)
        self._login_worker.finished.connect(
            lambda: (self._btn_check.setEnabled(True), self._btn_login.setEnabled(True))
        )
        self._login_worker.start()

    # ── Send / receive ────────────────────────────────────────────────────────

    def _send(self):
        question = self.input_field.toPlainText().strip()
        if not question:
            return

        self._clear_error_details(clear_status=False)
        self._add_bubble("Você", question, "#007ACC")
        self.input_field.clear()

        prompt = self._build_prompt(question)
        self._session_tokens += len(prompt) // 4
        self._update_token_bar(self._session_tokens)

        if self._activity_log:
            self._activity_log.log("prompt_send", f"Prompt enviado ({len(prompt)//4} tokens)")

        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._auto_status.setText("Iniciando automação...")

        expert_mode = self._btn_especialista.isChecked()
        pensamento = self.chk_pensamento.isChecked()
        web_search = self.chk_web_search.isChecked()

        self._worker = DeepSeekWorker(
            prompt,
            deep_think=expert_mode,
            pensamento_profundo=pensamento,
            web_search=web_search,
        )
        self._worker.response_received.connect(self._on_response)
        self._worker.status_update.connect(self._auto_status.setText)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _build_prompt(self, question: str) -> str:
        if not self.context_manager:
            return question + _FINISH_INSTRUCTION

        relevant_files = []
        if self.chk_search.isChecked() and self.project_path:
            relevant_files = FileSearcher(self.project_path).search_relevant_files(question)

        base = self.context_manager.build_prompt(
            question,
            relevant_files,
            include_structure=self.chk_structure.isChecked(),
            include_instructions=self.chk_instructions.isChecked(),
        )
        return base + _FINISH_INSTRUCTION

    def _cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._auto_status.setText("Cancelando...")

    @pyqtSlot(str)
    def _on_response(self, text: str):
        self._clear_error_details(clear_status=False)
        self._add_bubble("DeepSeek", text, "#3DD68C")
        self._session_tokens += len(text) // 4
        self._update_token_bar(self._session_tokens)
        self._set_conn(*_ST_OK)

        # Build diagnostic line — persisted in status bar so the user can see it
        # even after the worker finishes.
        commands = parse_commands(text)
        n_chat   = text.count('[DEVSEEK_CHAT]')
        n_create = text.count('[DEVSEEK_CREATE:')
        n_update = text.count('[DEVSEEK_UPDATE:')
        n_run    = text.count('[DEVSEEK_RUN:')
        chars    = len(text)

        parts = [f"{chars} chars"]
        if n_chat or n_create or n_update or n_run:
            parts.append(f"CHAT:{n_chat} CREATE:{n_create} UPDATE:{n_update} RUN:{n_run}")
        else:
            parts.append("⚠️ sem blocos DEVSEEK")

        if commands:
            parts.append(f"✅ {len(commands)} ação(ões) pronta(s) para aplicar")
        elif n_create or n_update or n_run:
            parts.append("⚠️ blocos encontrados mas nenhum comando válido parseado")
        else:
            parts.append("nenhuma ação gerada")

        diagnostic = " · ".join(parts)
        self._auto_status.setText(diagnostic)

        if self._activity_log:
            self._activity_log.log("response", diagnostic)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._add_bubble("Sistema", msg, "#F44747")
        self._set_conn(*_ST_ERROR)
        self._show_error_details(msg, add_bubble=False)
        if self._activity_log:
            self._activity_log.log("error", msg)

    @pyqtSlot()
    def _on_worker_done(self):
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        # Status is intentionally NOT cleared here — the diagnostic from
        # _on_response stays visible so the user can see exactly what arrived.

    # ── Chat display ──────────────────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_login_failed(self, msg: str):
        self._set_conn(_ST_ERROR[0], self._summarize_status(msg))
        self._show_error_details(msg, add_bubble=True)
        if self._activity_log:
            self._activity_log.log("error", msg)

    def _summarize_status(self, msg: str) -> str:
        first_line = (msg or "").strip().splitlines()[0] if msg else ""
        return first_line or "Erro de conexao"

    def _show_error_details(self, msg: str, add_bubble: bool):
        text = (msg or "").strip()
        if not text:
            return
        if add_bubble:
            self._add_bubble("Sistema", text, "#F44747")
        self._auto_status.setText("Erro na automacao. Os detalhes completos estao abaixo.")
        self._error_view.setPlainText(text)
        self._error_hdr.setVisible(True)
        self._error_view.setVisible(True)
        self._error_view.verticalScrollBar().setValue(
            self._error_view.verticalScrollBar().minimum()
        )

    def _clear_error_details(self, clear_status: bool = False):
        self._error_view.clear()
        self._error_hdr.setVisible(False)
        self._error_view.setVisible(False)
        if clear_status:
            self._auto_status.clear()

    def _copy_error_details(self):
        text = self._error_view.toPlainText().strip()
        if not text:
            return
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self._auto_status.setText("Erro copiado para a area de transferencia.")

    def _add_bubble(self, sender: str, text: str, color: str):
        if self._history_mgr:
            self._history_mgr.add_message(sender, text, color)
        self._render_bubble(sender, text, color)

    def _render_bubble(self, sender: str, text: str, color: str):
        is_ai = sender == "DeepSeek"
        is_system = sender == "Sistema"

        if is_ai:
            # Prefer [DEVSEEK_CHAT] content when present (new protocol).
            # Fall back to stripping all markers from the full text (old format).
            chat_text = extract_chat_text(text)
            display_text = chat_text if chat_text is not None else _clean_for_display(text)
            body_html = md_to_html(display_text, self._current_theme)
        else:
            escaped = (
                text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br/>")
            )
            if is_system:
                body_html = (
                    f'<div style="white-space:pre-wrap;'
                    f'background:{self._current_theme.get("tab_bg","#2D2D2D")};'
                    f'color:{self._current_theme.get("chat_fg","#D4D4D4")};'
                    f'padding:8px;border-radius:4px;'
                    f'font-family:Consolas,monospace;">{escaped}</div>'
                )
            else:
                body_html = f'<span style="white-space:pre-wrap;">{escaped}</span>'

        # File creation bar
        file_bar = ""
        if is_ai:
            detected = extract_files(text)
            if detected:
                anchor_id = f"files_{id(text)}_{len(self._pending_files)}"
                self._pending_files[anchor_id] = detected
                names = ", ".join(f.filename for f in detected[:3])
                if len(detected) > 3:
                    names += f" +{len(detected) - 3}"
                file_bar = (
                    f'<div style="margin-top:6px;padding:6px 8px;'
                    f'background:{self._current_theme.get("tab_bg","#2D2D2D")};'
                    f'border-radius:4px;font-size:10pt;">'
                    f'📁 <a href="devseek://create/{anchor_id}" '
                    f'style="color:#4FC1FF;text-decoration:none;">'
                    f'Criar {len(detected)} arquivo(s): {names}</a>'
                    f'</div>'
                )

        # Command application bar
        cmd_bar = ""
        if is_ai and self.project_path:
            commands = parse_commands(text)
            if commands:
                cmd_id = f"cmds_{id(text)}_{len(self._pending_commands)}"
                self._pending_commands[cmd_id] = commands
                n_runs = sum(1 for c in commands if c.action == "run")
                n_files = len(commands) - n_runs
                if n_runs and n_files:
                    label = f"Aplicar {n_files} alteração(ões) e executar {n_runs} comando(s)"
                elif n_runs:
                    label = f"Executar {n_runs} comando(s) no terminal"
                else:
                    label = f"Aplicar {len(commands)} alteração(ões) no projeto"
                cmd_bar = (
                    f'<div style="margin-top:6px;padding:6px 8px;'
                    f'background:{self._current_theme.get("tab_bg","#2D2D2D")};'
                    f'border-radius:4px;font-size:10pt;">'
                    f'⚡ <a href="devseek://apply/{cmd_id}" '
                    f'style="color:#CE9178;text-decoration:none;">'
                    f'{label}</a>'
                    f'</div>'
                )

        html = (
            f'<div style="margin-bottom:4px;">'
            f'<b style="color:{color};">{sender}:</b>'
            f'</div>'
            f'<div style="margin-bottom:6px;padding-left:4px;">'
            f'{body_html}'
            f'{file_bar}'
            f'{cmd_bar}'
            f'</div>'
            f'<hr style="border:none;border-top:1px solid #2a2a2a;margin:6px 0;"/>'
        )
        self.history_view.append(html)
        self.history_view.verticalScrollBar().setValue(
            self.history_view.verticalScrollBar().maximum()
        )

    def _on_anchor_clicked(self, url: QUrl):
        s = url.toString()
        if s.startswith("devseek://create/"):
            anchor_id = s[len("devseek://create/"):]
            files = self._pending_files.get(anchor_id)
            if files:
                from ui.file_creator_dialog import FileCreatorDialog
                dlg = FileCreatorDialog(files, self.project_path, self._current_theme, self)
                dlg.exec_()
                if self._activity_log:
                    self._activity_log.log("file_create", f"{len(files)} arquivo(s) criado(s) via diálogo")
                self._mark_link_done(f"devseek://create/{anchor_id}", f"📁 {len(files)} arquivo(s) criado(s)")
                del self._pending_files[anchor_id]

        elif s.startswith("devseek://apply/"):
            cmd_id = s[len("devseek://apply/"):]
            commands = self._pending_commands.get(cmd_id)
            if commands and self.project_path:
                self._apply_commands(commands, cmd_id)

    def _mark_link_done(self, href: str, label: str):
        """Replace an anchor link in the chat view with a static 'done' label."""
        import re
        scroll = self.history_view.verticalScrollBar().value()
        html = self.history_view.toHtml()
        pattern = re.compile(
            r'<a\b[^>]*\bhref="' + re.escape(href) + r'"[^>]*>.*?</a>',
            re.DOTALL | re.IGNORECASE,
        )
        if pattern.search(html):
            replacement = f'<span style="color:#3DD68C;">{label}</span>'
            html = pattern.sub(replacement, html)
            self.history_view.setHtml(html)
            self.history_view.verticalScrollBar().setValue(scroll)

    def _apply_commands(self, commands: list, cmd_id: str = ""):
        from PyQt5.QtWidgets import QDialog
        from ui.diff_dialog import DiffDialog

        mode = (
            "dry_run"     if self._rb_dry.isChecked()
            else "auto"   if self._rb_auto.isChecked()
            else "interactive"
        )

        backup_dir = None
        if self.context_manager:
            backup_dir = self.context_manager.devseek_path / "backups"

        def _log(result):
            if self._activity_log:
                ev = "file_create" if result.command.action == "create_file" else \
                     "file_update" if result.command.action in ("update_file", "replace") else \
                     "file_delete" if result.command.action == "delete" else "info"
                self._activity_log.log(ev, result.message)

        def _finish(label: str):
            if cmd_id and cmd_id in self._pending_commands:
                del self._pending_commands[cmd_id]
                self._mark_link_done(f"devseek://apply/{cmd_id}", label)

        # ── Dry run: preview diffs, no apply ─────────────────────────────────
        if mode == "dry_run":
            previews = [preview_command(cmd, self.project_path) for cmd in commands]
            dlg = DiffDialog(previews, self._current_theme, self, preview=False)
            dlg.exec_()
            _finish(f"🔍 Dry-run: {len(commands)} operação(ões) revisada(s)")
            return

        # ── Interactive: show diffs BEFORE applying, user selects ─────────────
        if mode == "interactive":
            previews = [preview_command(cmd, self.project_path) for cmd in commands]
            dlg = DiffDialog(previews, self._current_theme, self, preview=True)
            if dlg.exec_() != QDialog.Accepted:
                _finish("🚫 Cancelado sem alterações")
                return

            selected = set(dlg.accepted_indices())
            results = []
            for i, cmd in enumerate(commands):
                if i in selected:
                    if cmd.action == "run":
                        self.run_command_requested.emit(cmd.path)
                        r = apply_command(cmd, self.project_path, backup_dir)
                    else:
                        r = apply_command(cmd, self.project_path, backup_dir)
                    results.append(r)
                    _log(r)

            n_ok  = sum(1 for r in results if r.success or r.command.action == "run")
            n_tot = len(selected)
            n_run = sum(1 for r in results if r.command.action == "run")
            if n_tot == 0:
                label = "🚫 Nenhuma alteração selecionada"
            elif n_ok == n_tot:
                label = (
                    f"✅ {n_ok} ação(ões) aplicada(s)"
                    if not n_run else
                    f"✅ {n_ok} ação(ões) executada(s), incluindo {n_run} comando(s)"
                )
            elif n_ok > 0:
                label = f"⚠️ {n_ok}/{n_tot} ação(ões) aplicada(s)"
            else:
                label = "❌ Nenhuma ação aplicada"
            _finish(label)
            return

        # ── Auto: apply all, show results summary ─────────────────────────────
        results = []
        for cmd in commands:
            if cmd.action == "run":
                self.run_command_requested.emit(cmd.path)
            r = apply_command(cmd, self.project_path, backup_dir)
            results.append(r)
            _log(r)

        n_ok  = sum(1 for r in results if r.success or r.command.action == "run")
        n_tot = len(commands)
        n_run = sum(1 for r in results if r.command.action == "run")
        if n_ok == n_tot:
            label = (
                f"✅ {n_ok} ação(ões) aplicada(s)"
                if not n_run else
                f"✅ {n_ok} ação(ões) executada(s), incluindo {n_run} comando(s)"
            )
        elif n_ok > 0:
            label = f"⚠️ {n_ok}/{n_tot} ação(ões) aplicada(s)"
        else:
            label = "❌ Nenhuma ação aplicada"
        _finish(label)

        dlg = DiffDialog(results, self._current_theme, self, preview=False)
        dlg.exec_()

    def _clear_view(self):
        self.history_view.clear()
        self._pending_files.clear()
        self._pending_commands.clear()
        self._clear_error_details(clear_status=True)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self, theme: dict):
        self._current_theme = theme
        sidebar = theme.get("sidebar_bg", "#252526")
        chat_bg = theme.get("chat_bg", "#1E1E1E")
        fg = theme.get("chat_fg", "#D4D4D4")
        tab_bg = theme.get("tab_bg", "#2D2D2D")
        sel = theme.get("selection_bg", "#264F78")

        # Apply chat font
        chat_font = QFont(
            theme.get("chat_font_family", "Segoe UI"),
            int(theme.get("chat_font_size", 10)),
        )
        self.history_view.setFont(chat_font)
        self.input_field.setFont(chat_font)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {sidebar};
                color: {fg};
            }}
            QTextBrowser {{
                background-color: {chat_bg};
                color: {fg};
                border: 1px solid {tab_bg};
                border-radius: 4px;
            }}
            QPlainTextEdit {{
                background-color: {chat_bg};
                color: {fg};
                border: 1px solid {tab_bg};
                border-radius: 4px;
                selection-background-color: {sel};
            }}
            QPushButton {{
                background-color: {tab_bg};
                color: {fg};
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {sel};
                color: white;
            }}
            QPushButton:disabled {{
                color: #555;
            }}
            QCheckBox {{
                color: {fg};
                spacing: 4px;
            }}
            QRadioButton {{
                color: {fg};
                spacing: 4px;
            }}
            QFrame[frameShape="4"] {{
                color: {tab_bg};
            }}
            QLabel {{
                background: transparent;
                color: {fg};
            }}
            QProgressBar {{
                background: {tab_bg};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: #3DD68C;
                border-radius: 2px;
            }}
        """)
