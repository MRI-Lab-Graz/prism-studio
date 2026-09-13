"""End-to-end privacy check for every Analysis Outputs selection.

The Recipes page lets a user pick format (csv / xlsx / sav) x output scope
(one file per survey / single combined file). Each of those six selections
writes a different set of files -- the data file plus codebook sidecars, a
Jamovi R helper, or extra workbook sheets. "Anonymize participant IDs" and
"Mask copyrighted question text" must hold for *all* of the files a given
selection produces, not just the main data file.

These tests run the real export pipeline and then assert that no original
participant ID and no question text survives anywhere under the output
folder (the mapping file excepted -- that is the key, by design).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.recipes_surveys import anonymize_recipe_output, compute_survey_recipes

QUESTION_TEXT = "I have felt cheerful and in good spirits"
PARTICIPANTS = ["sub-001", "sub-002"]


def _setup_project(tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path / "project"
    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir(parents=True)

    project_root.mkdir(parents=True)
    (project_root / "participants.tsv").write_text(
        "participant_id\n" + "\n".join(PARTICIPANTS) + "\n", encoding="utf-8"
    )

    for idx, pid in enumerate(PARTICIPANTS, start=1):
        survey_dir = project_root / pid / "ses-1" / "survey"
        survey_dir.mkdir(parents=True)
        (survey_dir / f"{pid}_ses-1_task-wb_survey.tsv").write_text(
            f"WB01\n{idx}\n", encoding="utf-8"
        )

    sidecar_dir = project_root / "code" / "library" / "survey"
    sidecar_dir.mkdir(parents=True)
    (sidecar_dir / "survey-wb.json").write_text(
        json.dumps(
            {
                "Technical": {"TaskName": "wb"},
                "Questions": {
                    "WB01": {
                        "Description": QUESTION_TEXT,
                        "Levels": {"1": "Never", "2": "Always"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    (recipe_dir / "recipe-wb.json").write_text(
        json.dumps(
            {
                "Kind": "survey",
                "RecipeVersion": "1.0",
                "Survey": {"TaskName": "wb"},
                "Scores": [{"Name": "Total", "Method": "sum", "Items": ["WB01"]}],
            }
        ),
        encoding="utf-8",
    )
    return project_root, recipe_dir


def _searchable_text(path: Path) -> str:
    """Readable text of an output file (xlsx is a zip -- expand its sheets)."""
    if path.suffix.lower() == ".xlsx":
        import pandas as pd

        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        return "\n".join(
            "\n".join(map(str, frame.columns)) + "\n" + frame.to_csv(index=False)
            for frame in sheets.values()
        )
    return path.read_bytes().decode("utf-8", errors="ignore")


def _leaking_files(out_root: Path, needles: list[str]) -> dict[str, list[str]]:
    """Map filename -> leaked needles found in its readable content."""
    leaks: dict[str, list[str]] = {}
    for path in sorted(out_root.rglob("*")):
        if not path.is_file() or path.name == "participants_mapping.json":
            continue
        text = _searchable_text(path)
        found = [needle for needle in needles if needle in text]
        if found:
            leaks[path.name] = found
    return leaks


@pytest.mark.parametrize("out_format", ["csv", "xlsx", "sav"])
@pytest.mark.parametrize("merge_all", [False, True])
def test_no_participant_id_or_question_text_survives(tmp_path, out_format, merge_all):
    if out_format == "sav":
        pytest.importorskip("pyreadstat")
    project_root, recipe_dir = _setup_project(tmp_path)

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        out_format=out_format,
        include_raw=True,
        merge_all=merge_all,
        anonymized=True,
    )

    count, mapping_file = anonymize_recipe_output(
        dataset_path=project_root,
        out_root=result.out_root,
        out_format=out_format,
        anonymize_participant_ids=True,
        mask_questions=True,
    )

    assert count > 0
    assert mapping_file is not None and mapping_file.exists()

    leaks = _leaking_files(result.out_root, PARTICIPANTS + [QUESTION_TEXT])
    assert leaks == {}, f"{out_format}/merge_all={merge_all} leaked: {leaks}"


def test_score_and_participant_labels_survive_question_masking(tmp_path):
    """Masking must hit question text only -- not score or ID descriptions."""
    project_root, recipe_dir = _setup_project(tmp_path)
    recipe = json.loads((recipe_dir / "recipe-wb.json").read_text())
    recipe["Scores"][0]["Description"] = "Well-being sum score"
    (recipe_dir / "recipe-wb.json").write_text(json.dumps(recipe), encoding="utf-8")

    result = compute_survey_recipes(
        prism_root=project_root,
        repo_root=tmp_path,
        recipe_dir=recipe_dir,
        out_format="csv",
        include_raw=True,
    )
    anonymize_recipe_output(
        dataset_path=project_root,
        out_root=result.out_root,
        out_format="csv",
        anonymize_participant_ids=True,
        mask_questions=True,
    )

    codebook = json.loads((result.out_root / "wb_codebook.json").read_text())
    assert codebook["variables"]["Total"]["label"] == "Well-being sum score"
    assert codebook["variables"]["participant_id"]["label"] == "Participant identifier"
    assert codebook["variables"]["WB01"]["label"] == "[MASKED]"


def test_sav_export_falling_back_to_csv_is_still_anonymized(tmp_path):
    """An SPSS run that fell back to CSV must not skip anonymization."""
    project_root, _recipe_dir = _setup_project(tmp_path)
    out_root = tmp_path / "out"
    out_root.mkdir()
    (out_root / "wb.csv").write_text(
        "participant_id,Total\nsub-001,1\nsub-002,2\n", encoding="utf-8"
    )

    count, mapping_file = anonymize_recipe_output(
        dataset_path=project_root,
        out_root=out_root,
        out_format="sav",
    )

    assert count == 1
    written = (out_root / "wb.csv").read_text()
    assert "sub-001" not in written and "sub-002" not in written
    mapping = json.loads(mapping_file.read_text())["mapping"]
    assert all(pseudonym in written for pseudonym in mapping.values())


def test_participant_id_missing_from_participants_tsv_is_still_anonymized(tmp_path):
    """An ID present in the data but not in participants.tsv must not leak.

    Unlisted participants are common in half-curated datasets; passing them
    through unchanged silently ships a real ID inside an "anonymized" export.
    """
    project_root, _recipe_dir = _setup_project(tmp_path)
    out_root = tmp_path / "out"
    out_root.mkdir()
    (out_root / "wb.tsv").write_text(
        "participant_id\tTotal\nsub-001\t1\nsub-999\t9\n", encoding="utf-8"
    )

    _count, mapping_file = anonymize_recipe_output(
        dataset_path=project_root,
        out_root=out_root,
        out_format="tsv",
    )

    written = (out_root / "wb.tsv").read_text()
    assert "sub-999" not in written
    assert "sub-999" in json.loads(mapping_file.read_text())["mapping"]
