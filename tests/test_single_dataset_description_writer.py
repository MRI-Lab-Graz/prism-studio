"""dataset_description.json has ONE writer, ProjectManager.write_dataset_description: it writes the file and
mirrors it into project.json, so the two can never be written out of step. Every other code path calls it."""

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "app"), str(REPO)]

LITERAL = "dataset_description.json"
WRITE_CALLS = {"write_text", "_write_json", "dump", "write_bytes", "write"}
# (file, function) -> why it may write the file itself. The one writer is the first entry.
ALLOWED = {
    ("src/dataset_description.py", "write_dataset_description"): "the one writer",
    ("src/modality_contribution.py", "write_minimal_dataset"): "scratch dataset in a temp folder, not a project",
    ("app/src/cli/commands/dataset.py", "cmd_dataset_build_biometrics_smoketest"): "smoke-test dataset, not a project",
    ("src/recipes_surveys.py", "_write_recipes_dataset_description"): "a derivative's own description under derivatives/",
}


def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _has_literal(node: ast.AST, names: set[str]) -> bool:
    return any(
        (isinstance(n, ast.Constant) and n.value == LITERAL) or (isinstance(n, ast.Name) and n.id in names)
        for n in ast.walk(node)
    )


def _writes_the_file(func: ast.AST) -> bool:
    """A write call whose target is the file: its name, or a variable built from its name, is in the call."""
    names = {
        t.id
        for n in ast.walk(func)
        if isinstance(n, ast.Assign) and _has_literal(n.value, set())
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    for n in ast.walk(func):
        if not isinstance(n, ast.Call):
            continue
        attr = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        opens_for_write = attr == "open" and any(
            isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value[:1] in "wax" for a in n.args
        )
        if (attr in WRITE_CALLS or opens_for_write) and _has_literal(n, names):
            return True
    return False


def test_only_the_one_writer_writes_dataset_description_json():
    offenders = []
    for root in ("src", "app/src"):
        for path in sorted((REPO / root).rglob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for func in _functions(tree):
                if _writes_the_file(func) and (rel, func.name) not in ALLOWED:
                    offenders.append(f"{rel}::{func.name}")
    assert not offenders, "write dataset_description.json through src.dataset_description.write_dataset_description:\n" + "\n".join(offenders)


def _json(path):
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_the_writer_writes_the_file_and_mirrors_it_into_project_json(tmp_path):
    from src.dataset_description import write_dataset_description

    (tmp_path / "project.json").write_text('{"name": "old"}', encoding="utf-8")
    write_dataset_description(tmp_path, {"Name": "New", "BIDSVersion": "1.10.1", "Keywords": ["a", "b"]})
    assert _json(tmp_path / "dataset_description.json")["Name"] == "New"
    project = _json(tmp_path / "project.json")
    assert project["name"] == "New" and project["Basics"]["Keywords"] == ["a", "b"]


def test_a_converter_can_write_without_touching_the_project(tmp_path):
    from src.dataset_description import write_dataset_description

    (tmp_path / "project.json").write_text('{"name": "mine"}', encoding="utf-8")
    write_dataset_description(tmp_path, {"Name": "PRISM Survey Dataset"}, mirror=False)
    assert _json(tmp_path / "project.json") == {"name": "mine"}


def test_the_writer_works_in_a_folder_that_is_not_a_project_yet(tmp_path):
    from src.dataset_description import write_dataset_description

    write_dataset_description(tmp_path, {"Name": "X"})
    assert _json(tmp_path / "dataset_description.json") == {"Name": "X"}
    assert not (tmp_path / "project.json").exists()


def test_a_project_made_on_an_existing_dataset_agrees_with_that_dataset(tmp_path):
    """The case that went wrong: a converter had written 'PRISM Survey Dataset', the project got another name."""
    from src.project_manager import ProjectManager

    (tmp_path / "dataset_description.json").write_text(
        '{"Name": "PRISM Survey Dataset", "BIDSVersion": "1.10.1", "Keywords": ["psychology", "survey", "PRISM"]}',
        encoding="utf-8",
    )
    manager = ProjectManager()
    manager.init_on_existing_bids(str(tmp_path), {"name": "test", "keywords": ["eins", "zwei"]})
    issues = manager.get_metadata_sync_status(tmp_path)["issues"]
    assert not [i for i in issues if "does not match" in i], issues


def _flags(source: str) -> bool:
    return _writes_the_file(ast.parse(source).body[0])


def test_the_guard_catches_every_way_the_file_was_written_before():
    assert _flags('def f(r, d):\n    _write_json(r / "dataset_description.json", d)')
    assert _flags('def f(r, d):\n    (r / "dataset_description.json").write_text(d)')
    assert _flags('def f(r, d):\n    p = os.path.join(r, "dataset_description.json")\n    with open(p, "w") as f:\n        json.dump(d, f)')
    assert not _flags('def f(r, d):\n    names = ["dataset_description.json"]\n    json.dump(d, open(r / "report.json", "w"))')
    assert not _flags('def f(r, d):\n    write_dataset_description(r, d)')
