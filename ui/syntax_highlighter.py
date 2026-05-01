from PyQt5.QtCore import QRegularExpression
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


# Pattern groups: (regex, format_key)
_PYTHON_PATTERNS = [
    (r"\bdef\b|\bclass\b|\bimport\b|\bfrom\b|\breturn\b|\bif\b|\belif\b|\belse\b"
     r"|\bfor\b|\bwhile\b|\bin\b|\bnot\b|\band\b|\bor\b|\bis\b|\bNone\b|\bTrue\b"
     r"|\bFalse\b|\bwith\b|\bas\b|\btry\b|\bexcept\b|\bfinally\b|\braise\b"
     r"|\byield\b|\blambda\b|\bglobal\b|\bnonlocal\b|\bdel\b|\bpass\b|\bbreak\b"
     r"|\bcontinue\b|\basync\b|\bawait\b|\bassert\b|\btype\b", "keyword"),
    (r"@\w+", "decorator"),
    (r"\bprint\b|\blen\b|\brange\b|\btype\b|\bisinstance\b|\bhasattr\b|\bgetattr\b"
     r"|\bsetattr\b|\bsuper\b|\bproperty\b|\bstaticmethod\b|\bclassmethod\b"
     r"|\blist\b|\bdict\b|\bset\b|\btuple\b|\bstr\b|\bint\b|\bfloat\b|\bbool\b"
     r"|\bbytes\b|\bopen\b|\binput\b|\bzip\b|\bmap\b|\bfilter\b|\benumerate\b"
     r"|\bsorted\b|\breversed\b|\bany\b|\ball\b|\bmin\b|\bmax\b|\bsum\b|\babs\b"
     r"|\bround\b|\bvars\b|\bdir\b|\bhelp\b|\brepr\b|\bhash\b|\bid\b|\bcallable\b", "builtin"),
    (r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', "string"),
    (r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', "string"),
    (r"#[^\n]*", "comment"),
    (r"\b\d+\.?\d*([eE][+-]?\d+)?\b|\b0x[0-9a-fA-F]+\b", "number"),
]

_JS_PATTERNS = [
    (r"\bconst\b|\blet\b|\bvar\b|\bfunction\b|\breturn\b|\bif\b|\belse\b|\bfor\b"
     r"|\bwhile\b|\bdo\b|\bbreak\b|\bcontinue\b|\bswitch\b|\bcase\b|\bdefault\b"
     r"|\bnew\b|\bthis\b|\bclass\b|\bextends\b|\bimport\b|\bexport\b|\bfrom\b"
     r"|\bof\b|\bin\b|\btypeof\b|\binstanceof\b|\bnull\b|\bundefined\b|\btrue\b"
     r"|\bfalse\b|\basync\b|\bawait\b|\btry\b|\bcatch\b|\bfinally\b|\bthrow\b"
     r"|\bdelete\b|\byield\b|\bstatic\b|\bget\b|\bset\b|\bsuper\b", "keyword"),
    (r"`[^`]*`|\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'", "string"),
    (r"//[^\n]*", "comment"),
    (r"/\*[\s\S]*?\*/", "comment"),
    (r"\b\d+\.?\d*([eE][+-]?\d+)?\b", "number"),
    (r"@\w+", "decorator"),
]

_HTML_PATTERNS = [
    (r"<[!?/]?[\w:-]+", "keyword"),
    (r"/?>", "keyword"),
    (r'=\s*"[^"]*"|=\s*\'[^\']*\'', "string"),
    (r"<!--[\s\S]*?-->", "comment"),
    (r"&\w+;|&#\d+;", "builtin"),
]

_CSS_PATTERNS = [
    (r"[.#]?[\w-]+\s*\{", "keyword"),
    (r"[\w-]+\s*:", "function"),
    (r'"[^"]*"|\'[^\']*\'', "string"),
    (r"/\*[\s\S]*?\*/", "comment"),
    (r"#[0-9a-fA-F]{3,8}\b|\b\d+(%|px|em|rem|vh|vw|pt|cm|mm|s|ms)?\b", "number"),
]

_JSON_PATTERNS = [
    (r'"(?:[^"\\]|\\.)*"\s*:', "keyword"),
    (r'"(?:[^"\\]|\\.)*"', "string"),
    (r"\b(true|false|null)\b", "builtin"),
    (r"-?\b\d+\.?\d*([eE][+-]?\d+)?\b", "number"),
]

LANGUAGE_PATTERNS = {
    "python": _PYTHON_PATTERNS,
    "py": _PYTHON_PATTERNS,
    "javascript": _JS_PATTERNS,
    "js": _JS_PATTERNS,
    "typescript": _JS_PATTERNS,
    "ts": _JS_PATTERNS,
    "jsx": _JS_PATTERNS,
    "tsx": _JS_PATTERNS,
    "html": _HTML_PATTERNS,
    "css": _CSS_PATTERNS,
    "scss": _CSS_PATTERNS,
    "json": _JSON_PATTERNS,
}

DEFAULT_COLORS = {
    "keyword": "#569CD6",
    "string": "#CE9178",
    "comment": "#6A9955",
    "number": "#B5CEA8",
    "function": "#DCDCAA",
    "class": "#4EC9B0",
    "decorator": "#C586C0",
    "builtin": "#4FC1FF",
}


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language: str = "text", theme: dict = None):
        super().__init__(document)
        self.language = language.lower()
        self.theme = theme or {}
        self._rules: list = []
        self._build_rules()

    def update_theme(self, theme: dict):
        self.theme = theme
        self._build_rules()
        self.rehighlight()

    def _color(self, key: str) -> str:
        syntax = self.theme.get("syntax", {})
        return syntax.get(key, DEFAULT_COLORS.get(key, "#D4D4D4"))

    def _build_rules(self):
        self._rules = []
        patterns = LANGUAGE_PATTERNS.get(self.language, [])

        formats = {
            "keyword": _fmt(self._color("keyword"), bold=True),
            "string": _fmt(self._color("string")),
            "comment": _fmt(self._color("comment"), italic=True),
            "number": _fmt(self._color("number")),
            "function": _fmt(self._color("function")),
            "class": _fmt(self._color("class")),
            "decorator": _fmt(self._color("decorator")),
            "builtin": _fmt(self._color("builtin")),
        }

        for pattern, fmt_key in patterns:
            self._rules.append((
                QRegularExpression(pattern),
                formats.get(fmt_key, formats["keyword"]),
            ))

    def highlightBlock(self, text: str):
        for regex, text_format in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), text_format)
