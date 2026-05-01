from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QPushButton,
    QGroupBox, QScrollArea, QWidget, QDialogButtonBox,
    QColorDialog, QLabel, QHBoxLayout, QFontComboBox,
    QSpinBox, QCheckBox, QSlider, QLineEdit, QFileDialog,
    QTabWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont


class ColorButton(QPushButton):
    def __init__(self, color: str, label: str = "", parent=None):
        super().__init__(parent)
        self.color = color
        self._label = label
        self._refresh()
        self.clicked.connect(self._pick)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, f"Cor: {self._label}")
        if c.isValid():
            self.color = c.name()
            self._refresh()

    def _refresh(self):
        brightness = sum(int(self.color[i:i+2], 16) for i in (1, 3, 5)) / 3
        text_color = "#000" if brightness > 128 else "#FFF"
        self.setText(self.color)
        self.setFixedSize(100, 26)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color};
                color: {text_color};
                border: 2px solid rgba(255,255,255,0.2);
                border-radius: 4px;
                font-size: 10px;
                font-family: monospace;
            }}
            QPushButton:hover {{
                border-color: rgba(255,255,255,0.6);
            }}
        """)


class ThemeDialog(QDialog):
    def __init__(self, current_theme: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Personalizar Tema — DevSeek")
        self.setMinimumSize(520, 620)
        self._theme = current_theme.copy()
        self._buttons: dict[str, ColorButton] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Theme name field (top, always visible)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nome do tema:"))
        self._name_field = QLineEdit(self._theme.get("name", "Custom"))
        self._name_field.setPlaceholderText("Ex: Meu Tema Escuro")
        self._name_field.setMaximumWidth(260)
        name_row.addWidget(self._name_field)
        name_row.addStretch()
        root.addLayout(name_row)

        tabs = QTabWidget()

        # ── Tab 1: Cores ──────────────────────────────────────────────────────
        colors_w = QWidget()
        colors_layout = QVBoxLayout(colors_w)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        vbox = QVBoxLayout(container)

        iface_group = QGroupBox("Interface")
        iface_form = QFormLayout(iface_group)
        iface_fields = {
            "editor_bg":    "Fundo do editor",
            "editor_fg":    "Texto do editor",
            "sidebar_bg":   "Fundo da barra lateral",
            "sidebar_fg":   "Texto da barra lateral",
            "chat_bg":      "Fundo do chat",
            "chat_fg":      "Texto do chat",
            "tab_bg":       "Abas (inativas)",
            "tab_active_bg":"Aba ativa",
            "tab_fg":       "Texto das abas",
            "selection_bg": "Seleção de texto",
        }
        for key, label in iface_fields.items():
            color = self._theme.get(key, "#1E1E1E")
            btn = ColorButton(color, label)
            self._buttons[key] = btn
            iface_form.addRow(QLabel(label), btn)
        vbox.addWidget(iface_group)

        syn_group = QGroupBox("Sintaxe")
        syn_form = QFormLayout(syn_group)
        syntax = self._theme.get("syntax", {})
        syn_fields = {
            "keyword":   "Palavras-chave",
            "string":    "Strings / texto",
            "comment":   "Comentários",
            "number":    "Números",
            "function":  "Funções",
            "class":     "Classes",
            "decorator": "Decoradores",
            "builtin":   "Builtins",
        }
        for key, label in syn_fields.items():
            color = syntax.get(key, "#569CD6")
            btn = ColorButton(color, label)
            self._buttons[f"syntax.{key}"] = btn
            syn_form.addRow(QLabel(label), btn)
        vbox.addWidget(syn_group)

        scroll.setWidget(container)
        colors_layout.addWidget(scroll)
        tabs.addTab(colors_w, "Cores")

        # ── Tab 2: Fontes ─────────────────────────────────────────────────────
        fonts_w = QWidget()
        fonts_layout = QVBoxLayout(fonts_w)
        fonts_layout.setSpacing(12)

        # Editor font
        editor_font_group = QGroupBox("Fonte do Editor")
        ef_form = QFormLayout(editor_font_group)

        self._editor_font_combo = QFontComboBox()
        self._editor_font_combo.setCurrentFont(
            QFont(self._theme.get("editor_font_family", "Consolas"))
        )
        ef_form.addRow("Família:", self._editor_font_combo)

        self._editor_font_size = QSpinBox()
        self._editor_font_size.setRange(6, 36)
        self._editor_font_size.setValue(int(self._theme.get("editor_font_size", 11)))
        ef_form.addRow("Tamanho:", self._editor_font_size)

        self._editor_font_bold = QCheckBox("Negrito")
        self._editor_font_bold.setChecked(bool(self._theme.get("editor_font_bold", False)))
        self._editor_font_italic = QCheckBox("Itálico")
        self._editor_font_italic.setChecked(bool(self._theme.get("editor_font_italic", False)))
        style_row = QHBoxLayout()
        style_row.addWidget(self._editor_font_bold)
        style_row.addWidget(self._editor_font_italic)
        style_row.addStretch()
        ef_form.addRow("Estilo:", style_row)

        fonts_layout.addWidget(editor_font_group)

        # Chat font
        chat_font_group = QGroupBox("Fonte do Chat")
        cf_form = QFormLayout(chat_font_group)

        self._chat_font_combo = QFontComboBox()
        self._chat_font_combo.setCurrentFont(
            QFont(self._theme.get("chat_font_family", "Segoe UI"))
        )
        cf_form.addRow("Família:", self._chat_font_combo)

        self._chat_font_size = QSpinBox()
        self._chat_font_size.setRange(6, 24)
        self._chat_font_size.setValue(int(self._theme.get("chat_font_size", 10)))
        cf_form.addRow("Tamanho:", self._chat_font_size)

        fonts_layout.addWidget(chat_font_group)
        fonts_layout.addStretch()
        tabs.addTab(fonts_w, "Fontes")

        # ── Tab 3: Plano de fundo ─────────────────────────────────────────────
        bg_w = QWidget()
        bg_layout = QVBoxLayout(bg_w)
        bg_layout.setSpacing(12)

        bg_group = QGroupBox("Imagem de fundo do editor")
        bg_form = QFormLayout(bg_group)

        # Image path picker
        img_row = QHBoxLayout()
        self._bg_image_field = QLineEdit(self._theme.get("editor_bg_image", ""))
        self._bg_image_field.setPlaceholderText("Caminho da imagem (PNG, JPG...)")
        self._bg_image_field.setReadOnly(True)
        img_row.addWidget(self._bg_image_field, stretch=1)

        btn_pick_img = QPushButton("Escolher...")
        btn_pick_img.setFixedWidth(90)
        btn_pick_img.clicked.connect(self._pick_bg_image)
        img_row.addWidget(btn_pick_img)

        btn_clear_img = QPushButton("Remover")
        btn_clear_img.setFixedWidth(80)
        btn_clear_img.clicked.connect(lambda: self._bg_image_field.clear())
        img_row.addWidget(btn_clear_img)

        bg_form.addRow("Imagem:", img_row)

        # Opacity slider
        opacity_row = QHBoxLayout()
        self._bg_opacity = QSlider(Qt.Horizontal)
        self._bg_opacity.setRange(0, 100)
        opacity_val = int(float(self._theme.get("editor_bg_opacity", 0.15)) * 100)
        self._bg_opacity.setValue(opacity_val)
        self._opacity_lbl = QLabel(f"{opacity_val}%")
        self._opacity_lbl.setFixedWidth(36)
        self._bg_opacity.valueChanged.connect(
            lambda v: self._opacity_lbl.setText(f"{v}%")
        )
        opacity_row.addWidget(self._bg_opacity)
        opacity_row.addWidget(self._opacity_lbl)
        bg_form.addRow("Opacidade:", opacity_row)

        # Position
        from PyQt5.QtWidgets import QComboBox
        self._bg_position = QComboBox()
        self._bg_position.addItems(["center", "top-left", "top-right", "bottom-left", "bottom-right", "stretch"])
        saved_pos = self._theme.get("editor_bg_position", "center")
        idx = self._bg_position.findText(saved_pos)
        if idx >= 0:
            self._bg_position.setCurrentIndex(idx)
        bg_form.addRow("Posição:", self._bg_position)

        bg_layout.addWidget(bg_group)

        # Preview hint
        hint = QLabel("💡 A imagem aparece como marca d'água semitransparente\natrás do texto do editor.")
        hint.setStyleSheet("color: #858585; font-size: 10px;")
        hint.setAlignment(Qt.AlignCenter)
        bg_layout.addWidget(hint)
        bg_layout.addStretch()

        tabs.addTab(bg_w, "Plano de fundo")

        root.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher imagem de fundo",
            str(Path.home()),
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if path:
            self._bg_image_field.setText(path)

    def get_theme(self) -> dict:
        theme = self._theme.copy()
        syntax = theme.get("syntax", {}).copy()

        for key, btn in self._buttons.items():
            if key.startswith("syntax."):
                syntax[key[7:]] = btn.color
            else:
                theme[key] = btn.color

        theme["syntax"] = syntax
        name = self._name_field.text().strip() or "Custom"
        theme["name"] = name

        # Font settings
        theme["editor_font_family"] = self._editor_font_combo.currentFont().family()
        theme["editor_font_size"]   = self._editor_font_size.value()
        theme["editor_font_bold"]   = self._editor_font_bold.isChecked()
        theme["editor_font_italic"] = self._editor_font_italic.isChecked()
        theme["chat_font_family"]   = self._chat_font_combo.currentFont().family()
        theme["chat_font_size"]     = self._chat_font_size.value()

        # Background image settings
        theme["editor_bg_image"]    = self._bg_image_field.text().strip()
        theme["editor_bg_opacity"]  = self._bg_opacity.value() / 100.0
        theme["editor_bg_position"] = self._bg_position.currentText()

        return theme
