"""
Unit tests for core/command_parser.py

Covers:
  - parse_commands()       : plain-text DEVSEEK markers
  - extract_chat_text()    : DEVSEEK_CHAT extraction
  - _remove_ui_noise()     : Copiar/Baixar stripping
  - _normalize_devseek_blocks(): backtick fence stripping
  - preview_command()      : diff without writing
  - apply_command()        : file creation/update/replace/delete/mkdir/move
  - document-order sorting : MKDIR before CREATE
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.command_parser import (
    parse_commands,
    extract_chat_text,
    preview_command,
    apply_command,
    ParsedCommand,
)
from tests.fixtures import (
    CHAT_ONLY,
    NO_PROTOCOL,
    SINGLE_FILE_CREATE,
    SINGLE_FILE_UPDATE,
    MULTI_FILE_HTML_GAME,
    MKDIR_THEN_CREATE,
    REPLACE_PATCH,
    WITH_UI_NOISE,
    EXPECTED_HTML,
    EXPECTED_CSS,
    EXPECTED_JS,
)


# ── extract_chat_text ─────────────────────────────────────────────────────────

class TestExtractChatText:
    def test_returns_none_when_no_chat_block(self):
        assert extract_chat_text(NO_PROTOCOL) is None

    def test_returns_none_for_empty_string(self):
        assert extract_chat_text("") is None

    def test_extracts_single_chat_block(self):
        text = extract_chat_text(CHAT_ONLY)
        assert text is not None
        assert "Apenas uma explicação" in text

    def test_extracts_chat_from_multi_file_response(self):
        text = extract_chat_text(MULTI_FILE_HTML_GAME)
        assert text is not None
        assert "três arquivos" in text
        # Code should NOT be in the chat text
        assert "DOCTYPE" not in text
        assert "```" not in text

    def test_strips_outer_whitespace(self):
        raw = "[DEVSEEK_CHAT]\n\n  texto  \n\n[/DEVSEEK_CHAT]\n[DEVSEEK_FIM]"
        result = extract_chat_text(raw)
        assert result == "texto"

    def test_strips_leaked_protocol_markers(self):
        """Markers like [DEVSEEK_REPLACE] that DeepSeek wrote inside the chat must be removed."""
        raw = (
            "[DEVSEEK_CHAT]\n"
            "Farei a substituição usando [DEVSEEK_REPLACE] no arquivo.\n"
            "Também vou [DEVSEEK_CREATE: x.py] algo novo.\n"
            "[/DEVSEEK_CHAT]\n[DEVSEEK_FIM]"
        )
        result = extract_chat_text(raw)
        assert result is not None
        assert "[DEVSEEK_REPLACE]" not in result
        assert "[DEVSEEK_CREATE:" not in result
        assert "Farei a substituição usando" in result
        assert "algo novo" in result

    def test_joins_multiple_chat_blocks(self):
        raw = (
            "[DEVSEEK_CHAT]\nBloco 1\n[/DEVSEEK_CHAT]\n"
            "[DEVSEEK_CHAT]\nBloco 2\n[/DEVSEEK_CHAT]\n"
        )
        result = extract_chat_text(raw)
        assert "Bloco 1" in result
        assert "Bloco 2" in result


# ── parse_commands ────────────────────────────────────────────────────────────

class TestParseCommands:
    def test_no_commands_for_plain_text(self):
        cmds = parse_commands(NO_PROTOCOL)
        assert cmds == []

    def test_no_commands_for_chat_only(self):
        cmds = parse_commands(CHAT_ONLY)
        assert cmds == []

    def test_single_create(self):
        cmds = parse_commands(SINGLE_FILE_CREATE)
        assert len(cmds) == 1
        cmd = cmds[0]
        assert cmd.action == "create_file"
        assert cmd.path == "hello.py"
        assert "def hello" in cmd.content

    def test_single_update(self):
        cmds = parse_commands(SINGLE_FILE_UPDATE)
        assert len(cmds) == 1
        assert cmds[0].action == "update_file"
        assert cmds[0].path == "hello.py"

    def test_multi_file_count(self):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        assert len(cmds) == 3

    def test_multi_file_paths(self):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        paths = [c.path for c in cmds]
        assert "index.html" in paths
        assert "style.css" in paths
        assert "game.js" in paths

    def test_multi_file_content_html(self):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        html_cmd = next(c for c in cmds if c.path == "index.html")
        assert "<!DOCTYPE html>" in html_cmd.content

    def test_multi_file_content_css(self):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        css_cmd = next(c for c in cmds if c.path == "style.css")
        assert "background" in css_cmd.content

    def test_multi_file_content_js(self):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        js_cmd = next(c for c in cmds if c.path == "game.js")
        assert "getElementById" in js_cmd.content

    def test_mkdir_and_create_document_order(self):
        """MKDIR must come before CREATE when written that way in the response."""
        cmds = parse_commands(MKDIR_THEN_CREATE)
        assert len(cmds) == 2
        assert cmds[0].action == "mkdir"
        assert cmds[0].path == "utils"
        assert cmds[1].action == "create_file"
        assert cmds[1].path == "utils/helpers.py"

    def test_replace_action(self):
        # REPLACE_PATCH needs an existing file; parse only checks structure
        cmds = parse_commands(REPLACE_PATCH)
        assert len(cmds) == 1
        cmd = cmds[0]
        assert cmd.action == "replace"
        assert "Hello" in cmd.search
        assert "Olá" in cmd.replace

    def test_ui_noise_stripped(self):
        """Copiar/Baixar lines must not end up in file content."""
        cmds = parse_commands(WITH_UI_NOISE)
        assert len(cmds) == 1
        content = cmds[0].content
        assert "Copiar" not in content
        assert "Baixar" not in content
        assert "x = 1" in content


# ── apply_command ─────────────────────────────────────────────────────────────

class TestApplyCommand:
    def test_create_file(self, tmp_path):
        cmd = ParsedCommand(action="create_file", path="out.py", content="x = 1\n")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert (tmp_path / "out.py").read_text() == "x = 1\n"

    def test_create_file_nested(self, tmp_path):
        cmd = ParsedCommand(action="create_file", path="sub/deep/file.py", content="pass\n")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert (tmp_path / "sub" / "deep" / "file.py").exists()

    def test_update_file(self, tmp_path):
        (tmp_path / "f.py").write_text("old\n")
        cmd = ParsedCommand(action="update_file", path="f.py", content="new\n")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert (tmp_path / "f.py").read_text() == "new\n"

    def test_update_nonexistent_fails(self, tmp_path):
        cmd = ParsedCommand(action="update_file", path="missing.py", content="x")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is False

    def test_replace(self, tmp_path):
        (tmp_path / "r.py").write_text("a = 1\nb = 2\n")
        cmd = ParsedCommand(action="replace", path="r.py", search="a = 1", replace="a = 99")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert "a = 99" in (tmp_path / "r.py").read_text()

    def test_replace_search_not_found(self, tmp_path):
        (tmp_path / "r.py").write_text("x = 1\n")
        cmd = ParsedCommand(action="replace", path="r.py", search="NOT THERE", replace="y")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is False

    def test_replace_indent_normalized(self, tmp_path):
        """Search without indentation must match indented file content."""
        (tmp_path / "f.js").write_text(
            "function render() {\n"
            "    if (x) {\n"
            "        doA();\n"
            "        //remove me\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        cmd = ParsedCommand(
            action="replace",
            path="f.js",
            search="if (x) {\ndoA();\n//remove me\n}",
            replace="if (x) {\ndoA();\n}",
        )
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        content = (tmp_path / "f.js").read_text(encoding="utf-8")
        assert "//remove me" not in content
        assert "doA();" in content

    def test_replace_indent_normalized_varying_levels(self, tmp_path):
        """Closing brace keeps its SHALLOWER indentation, not the deeper code lines'."""
        (tmp_path / "g.js").write_text(
            "function f() {\n"
            "        ctx.fill();\n"       # 8 spaces
            "        //me apague\n"       # 8 spaces
            "    }\n"                     # 4 spaces (shallower closing brace)
            "}\n",
            encoding="utf-8",
        )
        cmd = ParsedCommand(
            action="replace",
            path="g.js",
            # search has NO indentation (typical when DeepSeek sends it)
            search="ctx.fill();\n//me apague\n}",
            replace="ctx.fill();\n}",
        )
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        content = (tmp_path / "g.js").read_text(encoding="utf-8")
        assert "//me apague" not in content
        # ctx.fill() should retain 8 spaces, } should retain 4 spaces
        assert "        ctx.fill();" in content
        assert "    }" in content
        assert "        }" not in content  # must NOT have the wrong (deeper) indent

    def test_delete_file(self, tmp_path):
        f = tmp_path / "del.py"
        f.write_text("content")
        cmd = ParsedCommand(action="delete", path="del.py")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert not f.exists()

    def test_mkdir(self, tmp_path):
        cmd = ParsedCommand(action="mkdir", path="new_dir")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert (tmp_path / "new_dir").is_dir()

    def test_move_file(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("content")
        cmd = ParsedCommand(action="move", path="src.py", dest="dst.py")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is True
        assert not src.exists()
        assert (tmp_path / "dst.py").read_text() == "content"

    def test_path_traversal_blocked(self, tmp_path):
        cmd = ParsedCommand(action="create_file", path="../escape.py", content="evil")
        result = apply_command(cmd, str(tmp_path))
        assert result.success is False

    def test_applies_all_three_files_from_game_response(self, tmp_path):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        for cmd in cmds:
            r = apply_command(cmd, str(tmp_path))
            assert r.success is True, f"Failed: {r.message}"
        assert (tmp_path / "index.html").exists()
        assert (tmp_path / "style.css").exists()
        assert (tmp_path / "game.js").exists()

    def test_file_content_matches_expected(self, tmp_path):
        cmds = parse_commands(MULTI_FILE_HTML_GAME)
        for cmd in cmds:
            apply_command(cmd, str(tmp_path))
        assert (tmp_path / "index.html").read_text(encoding="utf-8") == EXPECTED_HTML
        assert (tmp_path / "style.css").read_text(encoding="utf-8") == EXPECTED_CSS
        assert (tmp_path / "game.js").read_text(encoding="utf-8") == EXPECTED_JS


# ── preview_command ───────────────────────────────────────────────────────────

class TestPreviewCommand:
    def test_preview_does_not_write(self, tmp_path):
        cmd = ParsedCommand(action="create_file", path="new.py", content="x = 1")
        preview_command(cmd, str(tmp_path))
        assert not (tmp_path / "new.py").exists()

    def test_preview_success_is_none(self, tmp_path):
        cmd = ParsedCommand(action="create_file", path="new.py", content="x = 1")
        result = preview_command(cmd, str(tmp_path))
        assert result.success is None

    def test_preview_diff_for_existing_file(self, tmp_path):
        (tmp_path / "f.py").write_text("old\n")
        cmd = ParsedCommand(action="create_file", path="f.py", content="new\n")
        result = preview_command(cmd, str(tmp_path))
        assert result.success is None
        assert "-old" in result.diff
        assert "+new" in result.diff

    def test_preview_update_nonexistent_fails(self, tmp_path):
        cmd = ParsedCommand(action="update_file", path="missing.py", content="x")
        result = preview_command(cmd, str(tmp_path))
        assert result.success is False
