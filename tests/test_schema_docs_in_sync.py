"""docs/specs/*.md field tables are generated from app/schemas/stable; they must not drift.

Fix a failure with: python scripts/generate_schema_reference.py
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_schema_reference.py"


def _load():
    spec = importlib.util.spec_from_file_location("generate_schema_reference", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rows_list_nested_fields_with_required_and_enum():
    gen = _load()
    schema = {
        "required": ["Study"],
        "properties": {
            "Study": {
                "type": "object",
                "description": "Study block",
                "required": ["TaskName"],
                "properties": {
                    "TaskName": {"type": "string", "description": "Task id"},
                    "Kind": {"type": "string", "enum": ["a", "b"]},
                },
            },
            "Tags": {
                "type": "array",
                "items": {"type": "object", "properties": {"Name": {"type": "string"}}},
            },
        },
    }
    rows = {r[0]: r for r in gen.schema_rows(schema)}
    assert rows["Study"][2] == "yes"
    assert rows["Study.TaskName"][2] == "yes"
    assert rows["Study.Kind"][2] == "no" and "`a`, `b`" in rows["Study.Kind"][3]
    assert "Tags[].Name" in rows


def test_every_documented_schema_has_a_page_with_markers():
    gen = _load()
    for schema_name, page in gen.PAGES.items():
        text = (REPO_ROOT / "docs" / "specs" / page).read_text(encoding="utf-8")
        assert (
            gen.BEGIN in text and gen.END in text
        ), f"{page} lacks generated block for {schema_name}"


def test_committed_reference_matches_schemas():
    gen = _load()
    stale = gen.sync(write=False)
    assert (
        not stale
    ), f"stale generated tables, run scripts/generate_schema_reference.py: {stale}"


def test_every_schema_has_a_page_or_is_listed_elsewhere():
    """Guard against a schema being added without a page (instrument registry, entities, recipe and tool schemas have their own pages)."""
    gen = _load()
    schemas = {
        p.name.replace(".schema.json", "")
        for p in (REPO_ROOT / "app/schemas/stable").glob("*.schema.json")
    }
    assert schemas - set(gen.PAGES) <= gen.OTHER_DOCS, schemas - set(gen.PAGES)


def test_default_run_is_byte_identical():
    assert _load().main(["--check"]) == 0


def _layout(tmp_path):
    (tmp_path / "schemas" / "stable").mkdir(parents=True)
    (tmp_path / "specs").mkdir()
    (tmp_path / "schemas" / "stable" / "x.schema.json").write_text(
        '{"version": "1.0.0", "properties": {"A": {"type": "string", "description": "a"}}}', encoding="utf-8"
    )
    gen = _load()
    page = tmp_path / "specs" / "x.md"
    page.write_text(f"# X\n\n{gen.BEGIN}\nold\n{gen.END}\n", encoding="utf-8")
    args = [
        "--schemas", str(tmp_path / "schemas" / "stable"), "--specs", str(tmp_path / "specs"),
        "--link-prefix", "../schemas/stable/", "--label-prefix", "schemas/stable/", "--page", "x=x.md",
    ]
    return gen, page, args


def test_custom_layout(tmp_path):
    gen, page, args = _layout(tmp_path)
    assert gen.main(args) == 0
    text = page.read_text(encoding="utf-8")
    assert "](../schemas/stable/x.schema.json)" in text and "`schemas/stable/x.schema.json`" in text
    assert "| `A` | string | no | a |" in text


def test_check_reports_stale_page(tmp_path, capsys):
    gen, page, args = _layout(tmp_path)
    assert gen.main(args + ["--check"]) == 1
    assert "x.md" in capsys.readouterr().out
    assert "old" in page.read_text(encoding="utf-8")  # --check writes nothing
