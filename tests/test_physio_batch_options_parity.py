"""`physio batch-convert` takes what Studio's batch convert takes (THE RULE, CLAUDE.md).

Studio's job options are read from its own source, so a new option there fails here until the command has it.
"""

import argparse
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src.cli.parser import build_prism_tools_parsers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "app" / "src" / "web" / "blueprints" / "conversion_physio_handlers.py"

# Studio job option -> CLI flag dest, where the CLI named it first
RENAMED = {"modality_filter": "modality", "physio_destination": "destination", "source_dir": "input"}
# Studio job options that are plumbing, not something the user chooses
INTERNAL = {"tmp_dir", "project_path", "folder_name"}
# KNOWN GAPS, each to be fixed and deleted from here (the list may only shrink): the "save to project" step
# (stage, DataLad-aware copy, register sessions) and its layout options exist only in Studio.
KNOWN_GAPS = {
    "save_to_project": "Studio stages the output, copies it into the project with DataLad and registers the sessions",
    "dest_root": "folder in the project the files are copied to",
    "flat_structure": "project copy layout",
    "subject_rewrite_mode": "subject label rewriting while copying",
}


def _studio_job_options() -> set[str]:
    tree = ast.parse(HANDLER.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "api_batch_convert_start")
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "config" for t in node.targets) and isinstance(node.value, ast.Dict):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise AssertionError("Studio's job config dict not found")


def _cli_flags() -> set[str]:
    _root, parsers = build_prism_tools_parsers(ROOT / "app")
    sub = [a for a in parsers["physio"]._actions if isinstance(a, argparse._SubParsersAction)][0]
    return {a.dest for a in sub.choices["batch-convert"]._actions}


def test_every_studio_batch_option_has_a_cli_flag_or_a_listed_gap():
    flags = _cli_flags()
    missing = {o for o in _studio_job_options() - INTERNAL if RENAMED.get(o, o) not in flags}
    assert missing == set(KNOWN_GAPS), f"unlisted gaps: {sorted(missing - set(KNOWN_GAPS))}; fixed (delete from KNOWN_GAPS): {sorted(set(KNOWN_GAPS) - missing)}"


def test_the_command_passes_the_report_flag_and_writes_the_dataset_description(tmp_path, monkeypatch):
    from src.cli.commands.convert import cmd_physio_batch_convert

    seen = {}

    def fake_batch(**kw):
        seen.update(kw)
        return SimpleNamespace(success_count=0, error_count=0, skipped=[], new_files=[], existing_files=[])

    monkeypatch.setattr("src.batch_convert.batch_convert_folder", fake_batch)
    source, out = tmp_path / "raw", tmp_path / "out"
    source.mkdir()
    out.mkdir()
    cmd_physio_batch_convert(SimpleNamespace(
        input=str(source), output=str(out), modality="all", sampling_rate=None, dry_run=False, destination=None,
        generate_physio_reports=True, dataset_name="My Study",
    ))

    assert seen["generate_physio_reports"] is True
    assert '"Name": "My Study"' in (out / "dataset_description.json").read_text(encoding="utf-8")
