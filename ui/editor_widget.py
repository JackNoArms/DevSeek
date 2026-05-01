from pathlib import Path
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QFontMetrics,
    QPalette, QTextCharFormat, QTextCursor, QPixmap, QBrush
)


class _LineNumberArea(QWidget):
    def __init__(self, editor: "EditorWidget"):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class EditorWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg = QColor("#1E1E1E")
        self._fg = QColor("#D4D4D4")
        self._ln_bg = QColor("#252526")
        self._ln_fg = QColor("#858585")
        self._cur_line = QColor("#282828")
        self._bg_pixmap = None
        self._bg_opacity = 0.15
        self._bg_position = "center"

        self._ln_area = _LineNumberArea(self)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.blockCountChanged.connect(self._update_ln_width)
        self.updateRequest.connect(self._update_ln_area)
        self.cursorPositionChanged.connect(self._highlight_brackets)

        self._update_ln_width(0)

        metrics = QFontMetrics(self.font())
        self.setTabStopDistance(metrics.horizontalAdvance(" ") * 4)

        self._bracket_pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
        self._close_brackets = set(self._bracket_pairs.values())

        self._highlight_brackets()

    # ── Zoom via Ctrl+scroll ──────────────────────────────────────────────────

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            font = self.font()
            size = font.pointSize()
            font.setPointSize(min(size + 1, 36) if delta > 0 else max(size - 1, 6))
            self.setFont(font)
            self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
            event.accept()
        else:
            super().wheelEvent(event)

    # ── Bracket matching ──────────────────────────────────────────────────────

    def _highlight_brackets(self):
        extras = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(self._cur_line)
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extras.append(sel)

        cursor = self.textCursor()
        doc = self.document()
        pos = cursor.position()

        for check_pos in (pos - 1, pos):
            if check_pos < 0:
                continue
            ch = doc.characterAt(check_pos)
            match_pos = self._find_bracket_match(ch, check_pos, doc)
            if match_pos is not None:
                for p in (check_pos, match_pos):
                    sel = QTextEdit.ExtraSelection()
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor("#3a3a00"))
                    fmt.setForeground(QColor("#FFD700"))
                    sel.format = fmt
                    c = self.textCursor()
                    c.setPosition(p)
                    c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
                    sel.cursor = c
                    extras.append(sel)
                break

        self.setExtraSelections(extras)

    def _find_bracket_match(self, ch: str, pos: int, doc) -> int | None:
        if ch in self._bracket_pairs:
            close = self._bracket_pairs[ch]
            depth, i = 0, pos
            while i < doc.characterCount():
                c = doc.characterAt(i)
                if c == ch:
                    depth += 1
                elif c == close:
                    depth -= 1
                    if depth == 0:
                        return i
                i += 1
        elif ch in self._close_brackets:
            open_ch = next(k for k, v in self._bracket_pairs.items() if v == ch)
            depth, i = 0, pos
            while i >= 0:
                c = doc.characterAt(i)
                if c == ch:
                    depth += 1
                elif c == open_ch:
                    depth -= 1
                    if depth == 0:
                        return i
                i -= 1
        return None

    # ── Line number area ──────────────────────────────────────────────────────

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 8 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_ln_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_ln_area(self, rect, dy):
        if dy:
            self._ln_area.scroll(0, dy)
        else:
            self._ln_area.update(0, rect.y(), self._ln_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_ln_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._ln_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )
        # Rebuild bg palette when size changes so image scales correctly
        self._apply_bg_palette()

    def paint_line_numbers(self, event):
        painter = QPainter(self._ln_area)
        painter.fillRect(event.rect(), self._ln_bg)
        painter.setFont(self.font())

        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        h = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(self._ln_fg)
                painter.drawText(
                    0, top, self._ln_area.width() - 4, h,
                    Qt.AlignRight, str(num + 1)
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1

    # ── Background image via QPalette ─────────────────────────────────────────

    def _apply_bg_palette(self):
        """
        Sets the viewport's Base brush so the background image appears behind
        the text. Uses QPalette which is the correct Qt approach — paintEvent
        on the editor widget itself does not paint the text area (viewport).
        """
        vp = self.viewport()
        vp_w = vp.width() or 800
        vp_h = vp.height() or 600

        if self._bg_pixmap and not self._bg_pixmap.isNull():
            # Compose: bg color + image at opacity → single QPixmap used as brush
            canvas = QPixmap(vp_w, vp_h)
            canvas.fill(self._bg)

            painter = QPainter(canvas)
            painter.setOpacity(self._bg_opacity)

            px_w = self._bg_pixmap.width()
            px_h = self._bg_pixmap.height()
            pos = self._bg_position

            if pos == "stretch":
                painter.drawPixmap(0, 0, vp_w, vp_h, self._bg_pixmap)
            else:
                scale = min(vp_w / px_w, vp_h / px_h, 1.0)
                dw, dh = int(px_w * scale), int(px_h * scale)
                if pos == "center":
                    x, y = (vp_w - dw) // 2, (vp_h - dh) // 2
                elif pos == "top-left":
                    x, y = 0, 0
                elif pos == "top-right":
                    x, y = vp_w - dw, 0
                elif pos == "bottom-left":
                    x, y = 0, vp_h - dh
                else:  # bottom-right
                    x, y = vp_w - dw, vp_h - dh
                painter.drawPixmap(x, y, dw, dh, self._bg_pixmap)

            painter.end()

            palette = vp.palette()
            palette.setBrush(QPalette.Base, QBrush(canvas))
            vp.setPalette(palette)
        else:
            palette = vp.palette()
            palette.setColor(QPalette.Base, self._bg)
            vp.setPalette(palette)

        vp.setAutoFillBackground(True)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self, theme: dict):
        self._bg = QColor(theme.get("editor_bg", "#1E1E1E"))
        self._fg = QColor(theme.get("editor_fg", "#D4D4D4"))
        self._ln_bg = QColor(theme.get("sidebar_bg", "#252526"))
        self._ln_fg = QColor(theme.get("sidebar_fg", "#858585"))
        self._cur_line = QColor(theme.get("tab_bg", "#282828"))
        sel_bg = theme.get("selection_bg", "#264F78")

        img_path = theme.get("editor_bg_image", "")
        self._bg_pixmap = QPixmap(img_path) if img_path and Path(img_path).is_file() else None
        self._bg_opacity = float(theme.get("editor_bg_opacity", 0.15))
        self._bg_position = theme.get("editor_bg_position", "center")

        family = theme.get("editor_font_family", "Consolas")
        size = int(theme.get("editor_font_size", 11))
        font = QFont(family, size)
        font.setBold(bool(theme.get("editor_font_bold", False)))
        font.setItalic(bool(theme.get("editor_font_italic", False)))
        self.setFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)

        # Remove background-color from stylesheet — QPalette handles it now
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                color: {theme.get('editor_fg', '#D4D4D4')};
                border: none;
                selection-background-color: {sel_bg};
            }}
        """)

        self._apply_bg_palette()
        self._highlight_brackets()
        self._ln_area.update()
