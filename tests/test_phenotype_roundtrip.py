"""Round-trip regression test for the phenotype/ compatibility bridge.

phenotype/ is a lossy, one-way-friendly bridge by design (see
src/converters/phenotype_export.py and phenotype_import.py docstrings): the
only guarantee is that item *values* survive an export-then-import
round-trip. PRISM's richer instrument metadata (VariantDefinitions,
VariantScales, Reversed, MinValue/MaxValue, Citation, ...) is not expected
to survive, and this test asserts that loss explicitly rather than only
checking that the round-tripped data is "still importable" - a test that
only checked that could mask a regression that starts silently over- or
under-preserving metadata.
"""

from __future__ import annotations

import json

import pandas as pd

from src.converters.phenotype_export import collect_phenotype_bridge_files
from src.converters.phenotype_import import import_phenotype_directory


def _write_source_dataset(base):
    """Build a small PRISM survey/ tree: 2 subjects x 2 sessions, one task+variant."""
    sidecar = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv"},
        "Metadata": {"SchemaVersion": "1.2.0", "CreationDate": "2026-01-01"},
        "Study": {
            "TaskName": "wellbeing-multi",
            "Versions": ["10-likert"],
            "VariantDefinitions": [
                {"VariantID": "10-likert", "ItemCount": 2, "ScaleType": "likert"}
            ],
            "Citation": "Demo citation, expected to be lost on round-trip.",
        },
        "WB01": {
            "Description": "I have felt cheerful",
            "Reversed": False,
            "MinValue": 1,
            "MaxValue": 5,
            "Levels": {"1": "Strongly disagree", "5": "Strongly agree"},
            "VariantScales": [
                {
                    "VariantID": "10-likert",
                    "Levels": {"1": "Strongly disagree", "5": "Strongly agree"},
                }
            ],
        },
        "WB02": {
            "Description": "I have felt calm",
            "Reversed": True,
            "MinValue": 1,
            "MaxValue": 5,
        },
    }
    (base / "task-wellbeing-multi_acq-10-likert_survey.json").write_text(
        json.dumps(sidecar), encoding="utf-8"
    )

    rows = {
        ("01", "01"): {"WB01": 4, "WB02": 2},
        ("01", "02"): {"WB01": 3, "WB02": 5},
        ("02", "01"): {"WB01": 5, "WB02": 1},
    }
    for (subject, session), values in rows.items():
        survey_dir = base / f"sub-{subject}" / f"ses-{session}" / "survey"
        survey_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"sub-{subject}_ses-{session}_task-wellbeing-multi_acq-10-likert_survey.tsv"
        )
        pd.DataFrame([values]).to_csv(
            survey_dir / filename, sep="\t", index=False, lineterminator="\n"
        )
    return rows


def _source_value_matrix(base, rows):
    matrix = {}
    for (subject, session) in rows:
        path = (
            base
            / f"sub-{subject}"
            / f"ses-{session}"
            / "survey"
            / f"sub-{subject}_ses-{session}_task-wellbeing-multi_acq-10-likert_survey.tsv"
        )
        df = pd.read_csv(path, sep="\t", dtype=str)
        matrix[(subject, session)] = df.iloc[0].to_dict()
    return matrix


def test_survey_to_phenotype_to_survey_roundtrips_item_values(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    rows = _write_source_dataset(source_root)
    source_values = _source_value_matrix(source_root, rows)

    export_result = collect_phenotype_bridge_files(source_root)
    assert len(export_result.files) == 1
    phenotype_file = export_result.files[0]
    # Only one variant ("10-likert") is present in the source dataset, so the
    # variant suffix is omitted (it's only added to disambiguate when a task
    # has multiple variants - see test_collect_phenotype_bridge_files_separates_variants).
    assert phenotype_file.name == "wellbeing-multi"

    phenotype_dir = tmp_path / "phenotype"
    phenotype_dir.mkdir()
    phenotype_file.dataframe.to_csv(
        phenotype_dir / f"{phenotype_file.name}.tsv",
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    (phenotype_dir / f"{phenotype_file.name}.json").write_text(
        json.dumps(phenotype_file.sidecar), encoding="utf-8"
    )

    reimport_root = tmp_path / "reimported"
    reimport_root.mkdir()
    import_summary = import_phenotype_directory(phenotype_dir, reimport_root)
    assert import_summary.imported_task_count == 1

    # Data fidelity: every (subject, session, item) value must survive intact.
    imported_task_name = "wellbeing-multi"
    for (subject, session), original_values in source_values.items():
        imported_path = (
            reimport_root
            / f"sub-{subject}"
            / f"ses-{session}"
            / "survey"
            / f"sub-{subject}_ses-{session}_task-{imported_task_name}_survey.tsv"
        )
        assert imported_path.is_file()
        imported_df = pd.read_csv(imported_path, sep="\t", dtype=str)
        imported_row = imported_df.iloc[0].to_dict()
        for item, value in original_values.items():
            assert imported_row[item] == str(value)

    # Metadata loss: explicitly assert what is NOT preserved, so a future
    # change that starts silently over-preserving (or further under-
    # preserving) metadata is caught rather than passing quietly. Note:
    # TaskName itself round-trips unchanged here because it was already a
    # valid PRISM TaskName to begin with (sanitization is a no-op for names
    # produced by our own exporter) - sanitization actually kicking in for
    # arbitrary/non-PRISM phenotype filenames is covered separately in
    # test_phenotype_import.py's test_sanitize_task_name_* tests.
    reimported_sidecar = json.loads(
        (reimport_root / f"task-{imported_task_name}_survey.json").read_text(
            encoding="utf-8"
        )
    )
    assert reimported_sidecar["Study"]["TaskName"] == "wellbeing-multi"
    assert (
        reimported_sidecar["Study"]["Citation"]
        != "Demo citation, expected to be lost on round-trip."
    )
    assert "VariantDefinitions" not in reimported_sidecar["Study"]
    assert "Reversed" not in reimported_sidecar.get("WB02", {}) or reimported_sidecar[
        "WB02"
    ].get("Reversed") is False
    assert "MinValue" not in reimported_sidecar.get("WB01", {})
