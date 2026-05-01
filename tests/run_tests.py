"""
DevSeek Test Runner - colored CLI report.

Usage:
    python tests/run_tests.py              # run all tests
    python tests/run_tests.py unit         # only unit tests (no QApplication needed)
    python tests/run_tests.py integration  # only integration tests
    python tests/run_tests.py -v           # verbose (show each test name)
    python tests/run_tests.py -x           # stop on first failure
"""
import sys
import subprocess
from pathlib import Path

# Ensure the project root is on sys.path so the runner can be called from anywhere.
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force UTF-8 output so ANSI codes work on Windows terminals that support it.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI colour helpers
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"


def _c(color: str, text: str) -> str:
    return f"{color}{text}{_RESET}"


def _banner(text: str) -> None:
    width = 60
    line = "-" * width
    print()
    print(_c(_CYAN + _BOLD, line))
    print(_c(_CYAN + _BOLD, f"  {text}"))
    print(_c(_CYAN + _BOLD, line))


# Suite definitions
_SUITES = {
    "parser": {
        "label": "Command Parser",
        "path": "tests/test_command_parser.py",
        "requires_qt": False,
    },
    "context": {
        "label": "Context Manager",
        "path": "tests/test_context_manager.py",
        "requires_qt": False,
    },
    "bot": {
        "label": "Bot Logic (test mode)",
        "path": "tests/test_bot_logic.py",
        "requires_qt": True,
    },
    "integration": {
        "label": "Integration (full pipeline)",
        "path": "tests/test_integration.py",
        "requires_qt": True,
    },
}

_GROUP_UNIT        = ["parser", "context"]
_GROUP_INTEGRATION = ["bot", "integration"]
_GROUP_ALL         = _GROUP_UNIT + _GROUP_INTEGRATION


# Runner
def _run_suite(key: str, extra_flags: list) -> tuple:
    suite = _SUITES[key]
    print()
    print(_c(_BOLD, f">>  {suite['label']}"), _c(_DIM, f"({suite['path']})"))

    cmd = [
        sys.executable, "-m", "pytest",
        suite["path"],
        "--tb=short",
        "-q",
        *extra_flags,
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    passed = result.returncode == 0
    status = _c(_GREEN, "PASSOU") if passed else _c(_RED, "FALHOU")
    print(_c(_BOLD, f"   -> {status}"))
    return passed, suite["label"]


def main() -> None:
    args = sys.argv[1:]
    extra_flags = []
    group = "all"

    for arg in args:
        if arg in ("-v", "--verbose"):
            extra_flags.append("-v")
        elif arg in ("-x", "--exitfirst"):
            extra_flags.append("-x")
        elif arg == "unit":
            group = "unit"
        elif arg == "integration":
            group = "integration"
        else:
            print(_c(_YELLOW, f"Argumento desconhecido ignorado: {arg}"))

    if group == "unit":
        keys = _GROUP_UNIT
        title = "DevSeek Unit Tests"
    elif group == "integration":
        keys = _GROUP_INTEGRATION
        title = "DevSeek Integration Tests"
    else:
        keys = _GROUP_ALL
        title = "DevSeek Full Test Suite"

    _banner(title)

    results = []
    for key in keys:
        ok, label = _run_suite(key, extra_flags)
        results.append((ok, label))
        if not ok and "-x" in extra_flags:
            break

    _banner("Resumo")
    total  = len(results)
    passed = sum(1 for ok, _ in results if ok)
    failed = total - passed

    for ok, label in results:
        icon = _c(_GREEN, "[OK]") if ok else _c(_RED, "[FALHOU]")
        print(f"  {icon}  {label}")

    print()
    if failed == 0:
        print(_c(_GREEN + _BOLD, f"  OK  Todos os {total} grupos passaram!"))
    else:
        print(_c(_RED + _BOLD, f"  FALHA  {failed}/{total} grupos falharam."))
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
