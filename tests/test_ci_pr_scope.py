import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parent.parent / "scripts" / "ci" / "pr_scope.py"
    spec = importlib.util.spec_from_file_location("pr_scope", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BOT = "modality/issue-181-123"


def test_bot_branch_with_only_proposal_files_is_content_only():
    mod = _load()
    assert mod.content_only(BOT, ["proposals/issue-181/a.json", "proposals/issue-181/fixture/b.tsv"])


def test_other_branch_is_never_content_only():
    mod = _load()
    assert not mod.content_only("feat/x", ["proposals/issue-181/a.json"])


def test_any_file_outside_proposals_disables_it():
    mod = _load()
    assert not mod.content_only(BOT, ["proposals/issue-181/a.json", "app/schemas/stable/entities.schema.json"])


def test_prefix_lookalike_directory_is_not_proposals():
    mod = _load()
    assert not mod.content_only(BOT, ["proposals-evil/a.json"])


def test_no_changed_files_is_not_content_only():
    mod = _load()
    assert not mod.content_only(BOT, [])
