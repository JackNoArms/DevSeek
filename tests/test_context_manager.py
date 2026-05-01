"""
Unit tests for core/context_manager.py

Covers:
  - initialize()    : creates .devseek/ with context.json, instructions.md, structure.txt
  - get_context()   : reads and parses context.json
  - get_structure() : returns tree text
  - build_prompt()  : includes all sections; truncates large files; omits when flagged
  - update_structure(): reflects newly added files
  - is_initialized  : property
"""
import sys
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.context_manager import ContextManager, DEVSEEK_DIR, CONTEXT_FILE, INSTRUCTIONS_FILE, STRUCTURE_FILE


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_cm(tmp_path) -> ContextManager:
    cm = ContextManager(str(tmp_path))
    cm.initialize()
    return cm


# ── initialize ────────────────────────────────────────────────────────────────

class TestInitialize:
    def test_creates_devseek_dir(self, tmp_path):
        cm = ContextManager(str(tmp_path))
        assert not cm.is_initialized
        cm.initialize()
        assert cm.is_initialized
        assert (tmp_path / DEVSEEK_DIR).is_dir()

    def test_creates_context_json(self, tmp_path):
        cm = make_cm(tmp_path)
        assert (tmp_path / DEVSEEK_DIR / CONTEXT_FILE).exists()

    def test_context_json_has_project_name(self, tmp_path):
        cm = make_cm(tmp_path)
        ctx = cm.get_context()
        assert ctx["project_name"] == tmp_path.name

    def test_creates_instructions_md(self, tmp_path):
        cm = make_cm(tmp_path)
        assert (tmp_path / DEVSEEK_DIR / INSTRUCTIONS_FILE).exists()

    def test_creates_structure_txt(self, tmp_path):
        cm = make_cm(tmp_path)
        assert (tmp_path / DEVSEEK_DIR / STRUCTURE_FILE).exists()

    def test_idempotent(self, tmp_path):
        cm = make_cm(tmp_path)
        # Second call must not raise and must not reset existing files.
        ctx_before = cm.get_context()
        cm.initialize()
        ctx_after = cm.get_context()
        assert ctx_before == ctx_after

    def test_is_initialized_false_before(self, tmp_path):
        cm = ContextManager(str(tmp_path))
        assert cm.is_initialized is False

    def test_is_initialized_true_after(self, tmp_path):
        cm = make_cm(tmp_path)
        assert cm.is_initialized is True


# ── get_context ───────────────────────────────────────────────────────────────

class TestGetContext:
    def test_returns_dict(self, tmp_path):
        cm = make_cm(tmp_path)
        assert isinstance(cm.get_context(), dict)

    def test_returns_empty_dict_when_missing(self, tmp_path):
        cm = ContextManager(str(tmp_path))
        assert cm.get_context() == {}

    def test_returns_empty_dict_on_corrupt_json(self, tmp_path):
        cm = make_cm(tmp_path)
        (tmp_path / DEVSEEK_DIR / CONTEXT_FILE).write_text("not json", encoding="utf-8")
        assert cm.get_context() == {}

    def test_roundtrip_custom_fields(self, tmp_path):
        cm = make_cm(tmp_path)
        path = tmp_path / DEVSEEK_DIR / CONTEXT_FILE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["description"] = "My app"
        data["tech_stack"] = ["Python", "PyQt5"]
        path.write_text(json.dumps(data), encoding="utf-8")
        ctx = cm.get_context()
        assert ctx["description"] == "My app"
        assert "Python" in ctx["tech_stack"]


# ── get_structure ─────────────────────────────────────────────────────────────

class TestGetStructure:
    def test_returns_string(self, tmp_path):
        cm = make_cm(tmp_path)
        assert isinstance(cm.get_structure(), str)

    def test_contains_project_root_name(self, tmp_path):
        cm = make_cm(tmp_path)
        structure = cm.get_structure()
        assert tmp_path.name in structure

    def test_new_file_appears_after_update(self, tmp_path):
        cm = make_cm(tmp_path)
        (tmp_path / "mymodule.py").write_text("x = 1", encoding="utf-8")
        cm.update_structure()
        assert "mymodule.py" in cm.get_structure()

    def test_ignored_dirs_absent(self, tmp_path):
        cm = make_cm(tmp_path)
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.pyc").write_text("", encoding="utf-8")
        cm.update_structure()
        assert "__pycache__" not in cm.get_structure()

    def test_returns_empty_when_missing(self, tmp_path):
        cm = ContextManager(str(tmp_path))
        assert cm.get_structure() == ""


# ── build_prompt ──────────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_contains_user_question(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("Como faço X?", [])
        assert "Como faço X?" in prompt

    def test_contains_devseek_cmd_block(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("q", [])
        assert "[DEVSEEK_CHAT]" in prompt
        assert "[DEVSEEK_CREATE:" in prompt

    def test_contains_project_name(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("q", [])
        assert tmp_path.name in prompt

    def test_contains_structure_by_default(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("q", [])
        assert "Estrutura do Projeto" in prompt

    def test_omits_structure_when_flagged(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("q", [], include_structure=False)
        assert "Estrutura do Projeto" not in prompt

    def test_contains_instructions_by_default(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("q", [])
        assert "Instruções" in prompt

    def test_omits_instructions_when_flagged(self, tmp_path):
        cm = make_cm(tmp_path)
        prompt = cm.build_prompt("q", [], include_instructions=False)
        assert "Instruções e Regras" not in prompt

    def test_includes_relevant_file_content(self, tmp_path):
        cm = make_cm(tmp_path)
        files = [("main.py", "def main(): pass\n")]
        prompt = cm.build_prompt("q", files)
        assert "main.py" in prompt
        assert "def main" in prompt

    def test_large_file_sent_complete(self, tmp_path):
        """File content must never be truncated — DeepSeek decides its own limits."""
        cm = make_cm(tmp_path)
        big = "x = 1\n" * 20_000  # ~120 000 chars
        files = [("big.py", big)]
        prompt = cm.build_prompt("q", files)
        assert "truncado" not in prompt
        assert big in prompt

    def test_multiple_files_all_present(self, tmp_path):
        cm = make_cm(tmp_path)
        files = [("a.py", "a = 1"), ("b.py", "b = 2")]
        prompt = cm.build_prompt("q", files)
        assert "a.py" in prompt
        assert "b.py" in prompt

    def test_description_in_prompt_when_set(self, tmp_path):
        cm = make_cm(tmp_path)
        path = tmp_path / DEVSEEK_DIR / CONTEXT_FILE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["description"] = "Meu projeto incrível"
        path.write_text(json.dumps(data), encoding="utf-8")
        prompt = cm.build_prompt("q", [])
        assert "Meu projeto incrível" in prompt

    def test_tech_stack_in_prompt_when_set(self, tmp_path):
        cm = make_cm(tmp_path)
        path = tmp_path / DEVSEEK_DIR / CONTEXT_FILE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tech_stack"] = ["FastAPI", "SQLAlchemy"]
        path.write_text(json.dumps(data), encoding="utf-8")
        prompt = cm.build_prompt("q", [])
        assert "FastAPI" in prompt
