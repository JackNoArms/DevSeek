"""
Pytest configuration and shared fixtures for DevSeek tests.

Fixtures provided:
  qapp        - singleton QApplication (required for any PyQt5 import)
  tmp_project - temporary project directory pre-initialised with .devseek/
  ctx         - ContextManager pointed at tmp_project
"""
import sys
import os
import pytest
from pathlib import Path

# Ensure the project root is on sys.path so imports like
# "from core.command_parser import ..." work from any cwd.
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── QApplication ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """Single QApplication for the entire test session.

    PyQt5 requires exactly one QApplication to exist before any widget or
    QThread subclass is instantiated.  scope="session" ensures it is created
    once and reused across all test modules.
    """
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


# ── Temporary project ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_project(tmp_path):
    """A temporary directory that looks like an initialised DevSeek project.

    Structure created:
        tmp_path/
          .devseek/
            context.json
            instructions.md
            structure.txt
    """
    from core.context_manager import ContextManager
    cm = ContextManager(str(tmp_path))
    cm.initialize()
    return tmp_path


@pytest.fixture
def ctx(tmp_project):
    """ContextManager pointed at the temporary project."""
    from core.context_manager import ContextManager
    return ContextManager(str(tmp_project))
