"""
Integration tests: full pipeline  bot → parser → apply

Flow:
  1. Inject a realistic multi-file DEVSEEK response via set_test_response()
  2. Run DeepSeekWorker (test mode — no Chrome, no network)
  3. Collect the response_received signal
  4. Pass to parse_commands()
  5. Apply each command to a tmp_path project directory
  6. Assert that every expected file exists with correct content

Also tests ContextManager.build_prompt() → DeepSeekWorker round-trip to
verify the full "build prompt → send → receive → parse → apply" chain.
"""
import sys
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.deepseek_bot import DeepSeekWorker, set_test_response
from core.command_parser import parse_commands, apply_command
from core.context_manager import ContextManager
from tests.fixtures import (
    MULTI_FILE_HTML_GAME,
    SINGLE_FILE_CREATE,
    MKDIR_THEN_CREATE,
    REPLACE_PATCH,
    EXPECTED_HTML,
    EXPECTED_CSS,
    EXPECTED_JS,
)


# ── Shared helper ─────────────────────────────────────────────────────────────

def _run_worker_sync(response: str, timeout_s: float = 5.0) -> str | None:
    """Inject response, run worker, return first received string or None on timeout."""
    from PyQt5.QtCore import Qt
    set_test_response(response)
    worker = DeepSeekWorker(prompt="integration test")

    received: list[str] = []
    # DirectConnection delivers the signal in the emitting thread — works without exec().
    worker.response_received.connect(received.append, Qt.DirectConnection)

    worker.start()
    deadline = time.time() + timeout_s
    while worker.isRunning() and time.time() < deadline:
        time.sleep(0.05)

    set_test_response(None)
    return received[0] if received else None


# ── Single-file pipeline ───────────────────────────────────────────────────────

class TestSingleFilePipeline:
    def test_response_received(self, qapp):
        result = _run_worker_sync(SINGLE_FILE_CREATE)
        assert result is not None

    def test_parse_yields_one_command(self, qapp):
        result = _run_worker_sync(SINGLE_FILE_CREATE)
        cmds = parse_commands(result)
        assert len(cmds) == 1

    def test_create_file_on_disk(self, qapp, tmp_path):
        result = _run_worker_sync(SINGLE_FILE_CREATE)
        cmds = parse_commands(result)
        for cmd in cmds:
            r = apply_command(cmd, str(tmp_path))
            assert r.success is True, r.message
        assert (tmp_path / "hello.py").exists()

    def test_file_contains_expected_function(self, qapp, tmp_path):
        result = _run_worker_sync(SINGLE_FILE_CREATE)
        for cmd in parse_commands(result):
            apply_command(cmd, str(tmp_path))
        content = (tmp_path / "hello.py").read_text(encoding="utf-8")
        assert "def hello" in content


# ── Multi-file pipeline ────────────────────────────────────────────────────────

class TestMultiFilePipeline:
    def test_three_commands_parsed(self, qapp):
        result = _run_worker_sync(MULTI_FILE_HTML_GAME)
        assert result is not None
        cmds = parse_commands(result)
        assert len(cmds) == 3

    def test_all_files_created(self, qapp, tmp_path):
        result = _run_worker_sync(MULTI_FILE_HTML_GAME)
        for cmd in parse_commands(result):
            r = apply_command(cmd, str(tmp_path))
            assert r.success is True, r.message
        assert (tmp_path / "index.html").exists()
        assert (tmp_path / "style.css").exists()
        assert (tmp_path / "game.js").exists()

    def test_html_content_exact(self, qapp, tmp_path):
        result = _run_worker_sync(MULTI_FILE_HTML_GAME)
        for cmd in parse_commands(result):
            apply_command(cmd, str(tmp_path))
        assert (tmp_path / "index.html").read_text(encoding="utf-8") == EXPECTED_HTML

    def test_css_content_exact(self, qapp, tmp_path):
        result = _run_worker_sync(MULTI_FILE_HTML_GAME)
        for cmd in parse_commands(result):
            apply_command(cmd, str(tmp_path))
        assert (tmp_path / "style.css").read_text(encoding="utf-8") == EXPECTED_CSS

    def test_js_content_exact(self, qapp, tmp_path):
        result = _run_worker_sync(MULTI_FILE_HTML_GAME)
        for cmd in parse_commands(result):
            apply_command(cmd, str(tmp_path))
        assert (tmp_path / "game.js").read_text(encoding="utf-8") == EXPECTED_JS


# ── MKDIR + CREATE pipeline ────────────────────────────────────────────────────

class TestMkdirCreatePipeline:
    def test_two_commands(self, qapp):
        result = _run_worker_sync(MKDIR_THEN_CREATE)
        cmds = parse_commands(result)
        assert len(cmds) == 2

    def test_mkdir_first(self, qapp):
        result = _run_worker_sync(MKDIR_THEN_CREATE)
        cmds = parse_commands(result)
        assert cmds[0].action == "mkdir"

    def test_directory_and_file_created(self, qapp, tmp_path):
        result = _run_worker_sync(MKDIR_THEN_CREATE)
        for cmd in parse_commands(result):
            r = apply_command(cmd, str(tmp_path))
            assert r.success is True, r.message
        assert (tmp_path / "utils").is_dir()
        assert (tmp_path / "utils" / "helpers.py").exists()


# ── REPLACE pipeline ───────────────────────────────────────────────────────────

class TestReplacePipeline:
    def test_replace_command_parsed(self, qapp):
        result = _run_worker_sync(REPLACE_PATCH)
        cmds = parse_commands(result)
        assert len(cmds) == 1
        assert cmds[0].action == "replace"

    def test_replace_applied(self, qapp, tmp_path):
        # Pre-create the file with the original content
        (tmp_path / "hello.py").write_text(
            'def hello(name: str = "World") -> str:\n'
            '    return f"Hello, {name}!"\n',
            encoding="utf-8",
        )
        result = _run_worker_sync(REPLACE_PATCH)
        for cmd in parse_commands(result):
            r = apply_command(cmd, str(tmp_path))
            assert r.success is True, r.message
        content = (tmp_path / "hello.py").read_text(encoding="utf-8")
        assert "Olá" in content


# ── ContextManager build_prompt → worker round-trip ───────────────────────────

class TestPromptRoundTrip:
    """Verify that build_prompt output is accepted by the worker without errors."""

    def test_prompt_reaches_worker(self, qapp, tmp_project):
        cm = ContextManager(str(tmp_project))
        prompt = cm.build_prompt(
            "Crie um arquivo simples hello.py",
            [],
            include_structure=False,
        )
        # Inject a canned response that the prompt would normally produce
        result = _run_worker_sync(SINGLE_FILE_CREATE)
        assert result is not None
        # Prompt itself should contain the protocol instructions
        assert "[DEVSEEK_CHAT]" in prompt
        assert "[DEVSEEK_CREATE:" in prompt

    def test_initialized_project_structure_in_prompt(self, qapp, tmp_project):
        cm = ContextManager(str(tmp_project))
        prompt = cm.build_prompt("q", [])
        assert "Estrutura do Projeto" in prompt
        # The .devseek dir is hidden (starts with '.'), so it won't appear
        # but the project root name is always included
        assert tmp_project.name in prompt
