"""CI guard for THE RULE (CLAUDE.md): Studio must not call backend functions that no CLI command calls.

`scripts/check_cli_studio_parity.py` lists every backend name Studio imports and the CLI never does. The
reviewed list in `scripts/cli_studio_baseline.json` may only shrink: a new Studio-only call fails here.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_cli_studio_parity import new_studio_only_calls, studio_only_backend_calls  # noqa: E402


def _repo(tmp_path, web_source, cli_source):
    (tmp_path / "app" / "src" / "web" / "blueprints").mkdir(parents=True)
    (tmp_path / "app" / "src" / "cli" / "commands").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "app" / "src" / "web" / "blueprints" / "route.py").write_text(web_source, encoding="utf-8")
    (tmp_path / "app" / "src" / "cli" / "commands" / "cmd.py").write_text(cli_source, encoding="utf-8")
    return tmp_path


def test_a_backend_function_only_studio_calls_is_reported(tmp_path):
    repo = _repo(tmp_path, "from src.converters.survey import convert, only_in_studio\n", "from src.converters.survey import convert\n")
    assert studio_only_backend_calls(repo) == {"src.converters.survey:only_in_studio"}


def test_relative_imports_are_resolved_before_comparing(tmp_path):
    repo = _repo(tmp_path, "from ...converters.survey import helper\n", "from src.converters.survey import helper\n")
    assert studio_only_backend_calls(repo) == set()


def test_studio_own_modules_and_classes_are_not_backend_calls(tmp_path):
    repo = _repo(tmp_path, "from src.web.utils import thing\nfrom src.converters.survey import SomeClass, SOME_CONSTANT\n", "")
    assert studio_only_backend_calls(repo) == set()


def test_a_bare_import_of_an_app_src_module_is_the_same_function_as_the_src_import(tmp_path):
    """prism.py imports `core.validation`, Studio `src.core.validation`: one file, one function."""
    repo = _repo(tmp_path, "from src.core.validation import validate\n", "from core.validation import validate\n")
    (repo / "app" / "src" / "core").mkdir(parents=True)
    (repo / "app" / "src" / "core" / "validation.py").write_text("def validate(): pass\n", encoding="utf-8")
    assert studio_only_backend_calls(repo) == set()


def test_only_names_missing_from_the_baseline_are_new(tmp_path):
    repo = _repo(tmp_path, "from src.x import known, fresh\n", "")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"src.x:known": "to review"}), encoding="utf-8")
    assert new_studio_only_calls(repo, baseline) == {"src.x:fresh"}


def test_the_repository_adds_no_new_studio_only_backend_call():
    new = new_studio_only_calls(ROOT, ROOT / "scripts" / "cli_studio_baseline.json")
    assert not new, (
        "Studio calls backend code that no CLI command calls: " + ", ".join(sorted(new)) + ". THE RULE: the CLI executes, "
        "Studio only triggers. Make the CLI command run it too (preferred). If it is truly UI-only (icons, the dedicated "
        "terminal, ...), add it to scripts/cli_studio_baseline.json with the reason."
    )
