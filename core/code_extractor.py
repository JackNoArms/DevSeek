"""
Utilities for parsing DeepSeek (and similar AI) responses:
  - md_to_html()        : lightweight markdown → styled HTML for QTextBrowser
  - extract_files()     : find filename + code-block pairs in the response
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class DetectedFile:
    filename: str
    language: str
    content: str


# ── File extraction ───────────────────────────────────────────────────────────

_EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "css",
    ".json": "json", ".md": "markdown", ".txt": "text",
    ".sql": "sql", ".sh": "bash", ".bat": "batch",
    ".java": "java", ".cs": "csharp", ".cpp": "cpp", ".c": "c",
}
_LANG_TO_EXT = {
    "python": "py", "javascript": "js", "typescript": "ts",
    "html": "html", "css": "css", "json": "json",
    "java": "java", "csharp": "cs", "cpp": "cpp", "bash": "sh",
}

# Valid filename regex
_FILENAME_RE = re.compile(
    r'([a-zA-Z_][a-zA-Z0-9_.-]{0,60}\.[a-zA-Z]{1,8})'
)

def extract_files(text: str) -> List[DetectedFile]:
    """
    Finds filename + fenced code block pairs in AI response text.
    Supports patterns:
      ### index.html          (heading)
      **index.html**          (bold)
      `index.html`            (inline code)
      index.html              (plain text on its own line)
    Followed by:
      ```lang
      ...code...
      ```
    """
    results: List[DetectedFile] = []
    seen_content: set = set()

    # Regex: optional heading/bold prefix, filename, then a fenced block
    pattern = re.compile(
        r'(?:^#{1,4}\s*|^\*{1,2}|^`)?'         # optional prefix on line start
        r'([a-zA-Z_][a-zA-Z0-9_\-./]{0,80}'    # filename part 1
        r'\.[a-zA-Z]{1,8})'                      # extension
        r'(?:`|\*{1,2})?'                        # optional suffix
        r'\s*\n+'                                 # newline(s)
        r'```([a-zA-Z0-9]*)\s*\n'               # opening fence + lang
        r'(.*?)'                                  # code content (non-greedy)
        r'```',                                   # closing fence
        re.MULTILINE | re.DOTALL,
    )

    for m in pattern.finditer(text):
        raw_name = m.group(1).strip().lstrip('./')
        # Only take the last path component as filename
        filename = Path(raw_name).name
        if not _FILENAME_RE.fullmatch(filename):
            continue

        lang = m.group(2).strip().lower() or _EXT_TO_LANG.get(Path(filename).suffix.lower(), "text")
        content = m.group(3).rstrip('\n')

        key = content[:200]
        if key in seen_content:
            continue
        seen_content.add(key)

        results.append(DetectedFile(filename=filename, language=lang, content=content))

    # Fallback: standalone fenced blocks with no filename (name inferred from lang)
    if not results:
        standalone = re.compile(r'```([a-zA-Z0-9]+)\s*\n(.*?)```', re.DOTALL)
        counter: dict = {}
        for m in standalone.finditer(text):
            lang = m.group(1).lower()
            content = m.group(2).rstrip('\n')
            if not content.strip():
                continue
            ext = _LANG_TO_EXT.get(lang, lang)
            counter[ext] = counter.get(ext, 0) + 1
            n = counter[ext]
            filename = f"arquivo{'_' + str(n) if n > 1 else ''}.{ext}"
            results.append(DetectedFile(filename=filename, language=lang, content=content))

    return results


# ── Markdown → HTML ───────────────────────────────────────────────────────────

def md_to_html(text: str, theme: dict | None = None) -> str:
    """
    Lightweight markdown-to-HTML converter suitable for QTextBrowser.
    Handles: headings, bold/italic, inline code, fenced code blocks, lists, tables (basic).
    """
    t = theme or {}
    code_bg  = t.get("sidebar_bg", "#252526")
    code_fg  = t.get("editor_fg",  "#D4D4D4")
    kw_color = t.get("syntax", {}).get("keyword", "#569CD6")

    lines = text.split('\n')
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    in_list = False

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>')
            in_list = False

    def flush_code():
        nonlocal in_code, code_buf, code_lang
        raw = '\n'.join(code_buf)
        escaped = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        label = f'<span style="color:{kw_color};font-size:9pt;">{code_lang}</span> ' if code_lang else ''
        out.append(
            f'<div style="margin:8px 0;">'
            f'{label}'
            f'<pre style="background:{code_bg};color:{code_fg};'
            f'padding:10px;border-radius:5px;font-family:Consolas,monospace;'
            f'font-size:10pt;white-space:pre-wrap;margin:4px 0;">'
            f'{escaped}</pre></div>'
        )
        code_buf = []
        code_lang = ""
        in_code = False

    for line in lines:
        # ── Fenced code block ──────────────────────────────────────────────
        if line.startswith('```'):
            if not in_code:
                flush_list()
                in_code = True
                code_lang = line[3:].strip()
            else:
                flush_code()
            continue

        if in_code:
            code_buf.append(line)
            continue

        stripped = line.strip()

        # ── Empty line ─────────────────────────────────────────────────────
        if not stripped:
            flush_list()
            out.append('<br/>')
            continue

        # ── Headings ───────────────────────────────────────────────────────
        if stripped.startswith('#### '):
            flush_list()
            out.append(f'<h4 style="margin:6px 0 2px;">{_inline(stripped[5:])}</h4>')
            continue
        if stripped.startswith('### '):
            flush_list()
            out.append(f'<h3 style="margin:8px 0 2px;">{_inline(stripped[4:])}</h3>')
            continue
        if stripped.startswith('## '):
            flush_list()
            out.append(f'<h2 style="margin:10px 0 2px;">{_inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith('# '):
            flush_list()
            out.append(f'<h1 style="margin:12px 0 4px;">{_inline(stripped[2:])}</h1>')
            continue

        # ── Horizontal rule ────────────────────────────────────────────────
        if re.fullmatch(r'[-*_]{3,}', stripped):
            flush_list()
            out.append('<hr style="border:none;border-top:1px solid #555;margin:8px 0;"/>')
            continue

        # ── Unordered list ─────────────────────────────────────────────────
        m = re.match(r'^[-*•]\s+(.*)', stripped)
        if m:
            if not in_list:
                out.append('<ul style="margin:4px 0;padding-left:20px;">')
                in_list = True
            out.append(f'<li style="margin:2px 0;">{_inline(m.group(1))}</li>')
            continue

        # ── Ordered list ───────────────────────────────────────────────────
        m = re.match(r'^\d+\.\s+(.*)', stripped)
        if m:
            if not in_list:
                out.append('<ul style="margin:4px 0;padding-left:20px;list-style-type:decimal;">')
                in_list = True
            out.append(f'<li style="margin:2px 0;">{_inline(m.group(1))}</li>')
            continue

        # ── Normal paragraph ───────────────────────────────────────────────
        flush_list()
        out.append(f'<p style="margin:3px 0;">{_inline(stripped)}</p>')

    if in_code:
        flush_code()
    flush_list()

    return ''.join(out)


def _inline(text: str) -> str:
    """Apply inline markdown formatting to a string."""
    # HTML escape
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Bold + italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.+?)\*\*',     r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__',         r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*',         r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_',           r'<i>\1</i>', text)
    # Inline code
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#2d2d2d;color:#ce9178;padding:1px 5px;'
        r'border-radius:3px;font-family:Consolas,monospace;font-size:10pt;">\1</code>',
        text,
    )
    return text
