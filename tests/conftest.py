import os
import pathlib
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
HELP_DIR = FIXTURES / "help"


def load_help(name: str) -> str:
    return (HELP_DIR / name).read_text(errors="replace")


import pytest  # noqa: E402


@pytest.fixture(scope="session")
def rules():
    from clitree.core import rules as rules_mod

    return rules_mod.load_rules()


@pytest.fixture(scope="session")
def help_text():
    return load_help


@pytest.fixture(scope="session")
def fakecli():
    return str(FIXTURES / "fakecli.py")
