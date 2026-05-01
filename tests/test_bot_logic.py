"""
Unit tests for pure (Chrome-free) functions in core/deepseek_bot.py

Covers:
  - response_is_complete()  : structural completeness detector
  - set_test_response()     : test mode toggle
  - DeepSeekWorker (test mode): signal emission without browser
"""
import sys
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.deepseek_bot import response_is_complete, set_test_response, DeepSeekWorker, FINISH_MARKER
from tests.fixtures import (
    CHAT_ONLY,
    SINGLE_FILE_CREATE,
    MULTI_FILE_HTML_GAME,
    PARTIAL_UNCLOSED,
    PARTIAL_MAIS_PENDING,
)


# ── response_is_complete ──────────────────────────────────────────────────────

class TestResponseIsComplete:
    def test_empty_string_is_complete(self):
        # No open blocks → vacuously complete
        assert response_is_complete("") is True

    def test_plain_text_no_blocks_is_complete(self):
        assert response_is_complete("Hello world") is True

    def test_chat_only_closed_is_complete(self):
        # [DEVSEEK_CHAT]...[/DEVSEEK_CHAT] — balanced
        assert response_is_complete(CHAT_ONLY) is True

    def test_single_file_closed_is_complete(self):
        assert response_is_complete(SINGLE_FILE_CREATE) is True

    def test_partial_unclosed_is_incomplete(self):
        assert response_is_complete(PARTIAL_UNCLOSED) is False

    def test_mais_pending_is_incomplete(self):
        # DEVSEEK_MAIS present AND last CREATE is closed — still incomplete
        assert response_is_complete(PARTIAL_MAIS_PENDING) is False

    def test_multi_file_with_mais_is_incomplete(self):
        # MULTI_FILE_HTML_GAME contains [DEVSEEK_MAIS] — treated as "more coming" signal.
        # response_is_complete returns False even though all blocks are closed because
        # MAIS tells the stability detector to keep waiting. FIM (not this function)
        # is what declares a multi-file response complete in real operation.
        assert response_is_complete(MULTI_FILE_HTML_GAME) is False

    def test_multi_file_no_mais_all_closed_is_complete(self):
        text = (
            "[DEVSEEK_CHAT]hello[/DEVSEEK_CHAT]\n"
            "[DEVSEEK_CREATE: a.py]\ncode a\n[/DEVSEEK_CREATE]\n"
            "[DEVSEEK_CREATE: b.py]\ncode b\n[/DEVSEEK_CREATE]\n"
        )
        assert response_is_complete(text) is True

    def test_more_opens_than_closes(self):
        text = "[DEVSEEK_CREATE: a.py]\ncode\n"
        assert response_is_complete(text) is False

    def test_balanced_chat_and_create(self):
        text = (
            "[DEVSEEK_CHAT]hi[/DEVSEEK_CHAT]\n"
            "[DEVSEEK_CREATE: x.py]\ncode\n[/DEVSEEK_CREATE]\n"
        )
        assert response_is_complete(text) is True

    def test_mais_without_following_close_is_incomplete(self):
        text = (
            "[DEVSEEK_CREATE: a.py]\ncode\n[/DEVSEEK_CREATE]\n"
            "[DEVSEEK_MAIS]\n"
        )
        assert response_is_complete(text) is False

    def test_replace_block_balanced(self):
        text = (
            "[DEVSEEK_REPLACE: f.py]\nSEARCH:\nold\nREPLACE:\nnew\n[/DEVSEEK_REPLACE]\n"
        )
        assert response_is_complete(text) is True

    def test_replace_block_unclosed(self):
        text = "[DEVSEEK_REPLACE: f.py]\nSEARCH:\nold\nREPLACE:\nnew\n"
        assert response_is_complete(text) is False


# ── set_test_response / test mode ─────────────────────────────────────────────

class TestTestMode:
    def teardown_method(self, _method):
        # Always reset after each test to avoid bleed-through
        set_test_response(None)

    def test_default_is_none(self):
        import core.deepseek_bot as bot
        set_test_response(None)
        assert bot._test_mode_response is None

    def test_set_stores_value(self):
        import core.deepseek_bot as bot
        set_test_response("hello")
        assert bot._test_mode_response == "hello"

    def test_reset_to_none(self):
        import core.deepseek_bot as bot
        set_test_response("something")
        set_test_response(None)
        assert bot._test_mode_response is None


# ── DeepSeekWorker (test mode — no Chrome) ────────────────────────────────────

class TestDeepSeekWorkerTestMode:
    """Run DeepSeekWorker with a test response injected.

    Requires a QApplication (qapp fixture from conftest.py).
    All tests complete without opening Chrome.
    """

    def teardown_method(self, _method):
        set_test_response(None)

    def _run_worker(self, response: str, timeout_s: float = 5.0) -> dict:
        """Start worker, collect all signals, return collected data."""
        from PyQt5.QtCore import Qt
        set_test_response(response)
        worker = DeepSeekWorker(prompt="test prompt")

        received = []
        statuses = []
        errors = []

        # DirectConnection delivers signals in the emitting thread (worker thread),
        # bypassing the main event loop queue — required in tests without exec().
        worker.response_received.connect(received.append, Qt.DirectConnection)
        worker.status_update.connect(statuses.append, Qt.DirectConnection)
        worker.error_occurred.connect(errors.append, Qt.DirectConnection)

        worker.start()
        deadline = time.time() + timeout_s
        while worker.isRunning() and time.time() < deadline:
            time.sleep(0.05)

        if worker.isRunning():
            worker.cancel()
            worker.wait(500)

        return {"received": received, "statuses": statuses, "errors": errors}

    def test_emits_response_received(self, qapp):
        data = self._run_worker(SINGLE_FILE_CREATE)
        assert len(data["received"]) == 1

    def test_response_content_matches_fixture(self, qapp):
        data = self._run_worker(SINGLE_FILE_CREATE)
        assert data["received"][0] == SINGLE_FILE_CREATE

    def test_emits_status_updates(self, qapp):
        data = self._run_worker(SINGLE_FILE_CREATE)
        assert len(data["statuses"]) >= 1

    def test_status_mentions_teste(self, qapp):
        data = self._run_worker(SINGLE_FILE_CREATE)
        combined = " ".join(data["statuses"])
        assert "TESTE" in combined

    def test_no_errors_in_test_mode(self, qapp):
        data = self._run_worker(SINGLE_FILE_CREATE)
        assert data["errors"] == []

    def test_multi_file_response_emitted_intact(self, qapp):
        data = self._run_worker(MULTI_FILE_HTML_GAME)
        assert len(data["received"]) == 1
        assert "index.html" in data["received"][0]
        assert "style.css" in data["received"][0]
        assert "game.js" in data["received"][0]

    def test_worker_finishes_without_hanging(self, qapp):
        import time as _time
        set_test_response(CHAT_ONLY)
        worker = DeepSeekWorker(prompt="p")
        worker.start()
        started = _time.time()
        worker.wait(3000)  # 3 seconds maximum
        elapsed = _time.time() - started
        assert not worker.isRunning(), "Worker did not finish within 3 seconds"
        assert elapsed < 3.0
