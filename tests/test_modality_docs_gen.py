import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    build_docs_page,
    build_docs_snippets,
    build_registration_md,
    build_schema,
    read_proposal,
    registration_entry,
)

P = read_proposal(Path(__file__).resolve().parents[1] / "examples" / "modality_proposal" / "bloodwork.yml")


def test_new_entry_has_the_fixed_pattern_and_the_suggestions():
    e = registration_entry(P)
    assert e["allowedEntities"] == ["task", "acq", "run"]
    assert e["optionalEntityValues"]["acq"] == {
        "enum": ["fasting", "nonfasting"],
        "allowOther": True,
        "otherPattern": "[a-zA-Z0-9]+",
    }


def test_entry_without_suggestions_has_no_optional_values():
    assert "optionalEntityValues" not in registration_entry({**P, "entities": []})


def test_schema_text_and_study_block_make_task_optional():
    s = build_schema(P)
    assert "[_task-<label>]" in s["description"]
    assert "TaskName" not in s["properties"]["Study"]["required"]


def test_docs_page_has_pattern_suggestions_and_columns():
    page = build_docs_page(P)
    assert page.startswith("# Bloodwork")
    assert "sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_bloodchem.<extension>" in page
    assert "`acq-fasting`" in page and "Drawn after at least 8 hours" in page
    assert "`crp`" in page and "mg/L" in page


def test_snippets_name_the_pages_the_gate_checks():
    s = build_docs_snippets(P)
    assert s["toctree"] == "   specs/bloodwork"
    assert s["entities_row"].startswith("| `bloodwork` | prism | `bloodchem` |")
    assert 'href="specs/bloodwork.html"' in s["card"]


def test_registration_md_lists_the_docs_steps():
    md = build_registration_md(P)
    for needle in ("docs/specs/bloodwork.md", "docs/index.rst", "docs/SCHEMA_SPECIFICATIONS.md",
                   "docs/specs/entities.md", "modality-docs"):
        assert needle in md


def test_docs_page_shows_example_sidecar_types_and_guide_link():
    page = build_docs_page(P)
    assert "```json" in page and '"OriginalName": "bloodwork"' in page
    assert "- `CRP`: C-reactive protein" in page
    assert "../MODALITY_PROPOSALS.md" in page


def test_contributor_text_is_escaped():
    p = {**P, "description": "Blood <script>x</script> & more"}
    p["columns"] = [{**P["columns"][0], "description": "a | b", "units": "x|y"}]
    card = build_docs_snippets(p)["card"]
    assert "<script>" not in card and "&lt;script&gt;" in card and "&amp;" in card
    page = build_docs_page(p)
    assert "a \\| b" in page and "x\\|y" in page
    assert "<script>" not in page.split("```json")[0]  # fenced code is shown literally


def test_description_ending_in_a_full_stop_is_not_doubled():
    p = {**P, "description": "Venous blood."}
    assert "Venous blood.." not in build_docs_page(p)
    assert "Venous blood.." not in build_schema(p)["description"]
