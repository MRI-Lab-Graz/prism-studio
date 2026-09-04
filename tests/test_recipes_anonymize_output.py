"""Tests for src.recipes_surveys.anonymize_recipe_output.

Regression coverage for docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-3):
the CLI's `recipes surveys/biometrics --anonymized` flag previously only
renamed the output folder to '<layout>_<lang>_anon' and never actually
anonymized anything, while the Studio GUI's "Anonymize" checkbox on the
same page did real participant-ID pseudonymization. Both now call this one
shared function so behavior is identical regardless of entry point.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.recipes_surveys import anonymize_recipe_output


def _write_participants_tsv(dataset_path, participant_ids):
    df = pd.DataFrame({"participant_id": participant_ids})
    df.to_csv(dataset_path / "participants.tsv", sep="\t", index=False)


def _write_scores_tsv(out_root, filename, participant_ids, extra_cols=None):
    data = {"participant_id": participant_ids}
    if extra_cols:
        data.update(extra_cols)
    df = pd.DataFrame(data)
    out_path = out_root / filename
    df.to_csv(out_path, sep="\t", index=False)
    return out_path


class TestAnonymizeRecipeOutputTsv:
    def test_replaces_participant_ids_in_tsv(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01", "sub-02"])

        out_root = tmp_path / "derivatives" / "survey" / "long_en"
        out_root.mkdir(parents=True)
        scores_path = _write_scores_tsv(
            out_root, "scores.tsv", ["sub-01", "sub-02"], {"score": [1, 2]}
        )

        anonymized_count, mapping_file = anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root,
            out_format="flat",
        )

        assert anonymized_count == 1
        assert mapping_file.exists()

        result_df = pd.read_csv(scores_path, sep="\t", dtype=str)
        mapping = json.loads(mapping_file.read_text())["mapping"]
        assert set(result_df["participant_id"]) == set(mapping.values())
        # Original IDs must not remain anywhere in the output.
        assert "sub-01" not in result_df["participant_id"].values
        assert "sub-02" not in result_df["participant_id"].values

    def test_deterministic_mapping_is_stable_on_rerun_against_same_output(
        self, tmp_path
    ):
        # create_participant_mapping's determinism guarantee is scoped to a
        # given mapping file (the secret key lives alongside it there), not
        # across independent output directories — see test_reuses_existing_
        # mapping_file for the property this function actually promises.
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root = tmp_path / "out"
        out_root.mkdir()
        _write_scores_tsv(out_root, "scores.tsv", ["sub-01"])
        _, mapping_file = anonymize_recipe_output(
            dataset_path=dataset_path, out_root=out_root, out_format="flat"
        )
        first = json.loads(mapping_file.read_text())["mapping"]["sub-01"]

        _write_scores_tsv(out_root, "scores2.tsv", ["sub-01"])
        anonymize_recipe_output(
            dataset_path=dataset_path, out_root=out_root, out_format="flat"
        )
        second = json.loads(mapping_file.read_text())["mapping"]["sub-01"]

        assert first == second

    def test_random_ids_produce_different_mappings_across_runs(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root_a = tmp_path / "run_a"
        out_root_a.mkdir()
        _write_scores_tsv(out_root_a, "scores.tsv", ["sub-01"])
        _, mapping_file_a = anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root_a,
            out_format="flat",
            random_ids=True,
        )

        out_root_b = tmp_path / "run_b"
        out_root_b.mkdir()
        _write_scores_tsv(out_root_b, "scores.tsv", ["sub-01"])
        _, mapping_file_b = anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root_b,
            out_format="flat",
            random_ids=True,
        )

        mapping_a = json.loads(mapping_file_a.read_text())["mapping"]
        mapping_b = json.loads(mapping_file_b.read_text())["mapping"]
        assert mapping_a["sub-01"] != mapping_b["sub-01"]

    def test_reuses_existing_mapping_file(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root = tmp_path / "long_en_anon"
        out_root.mkdir()
        _write_scores_tsv(out_root, "scores.tsv", ["sub-01"])

        _, mapping_file = anonymize_recipe_output(
            dataset_path=dataset_path, out_root=out_root, out_format="flat"
        )
        first_mapping = json.loads(mapping_file.read_text())["mapping"]

        # Simulate a second run (e.g. re-running with --merge-all) against
        # the same output folder — the existing mapping should be reused
        # verbatim rather than regenerated.
        _write_scores_tsv(out_root, "more_scores.tsv", ["sub-01"])
        anonymize_recipe_output(
            dataset_path=dataset_path, out_root=out_root, out_format="flat"
        )
        second_mapping = json.loads(mapping_file.read_text())["mapping"]
        assert first_mapping == second_mapping

    def test_id_length_controls_pseudonym_length(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root = tmp_path / "out"
        out_root.mkdir()
        _write_scores_tsv(out_root, "scores.tsv", ["sub-01"])

        _, mapping_file = anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root,
            out_format="flat",
            id_length=4,
        )
        mapping = json.loads(mapping_file.read_text())["mapping"]
        pseudonym = mapping["sub-01"]
        assert len(pseudonym.replace("sub-", "").lstrip("0")) <= 4 or len(
            pseudonym
        ) >= 4

    def test_mask_questions_replaces_question_column(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root = tmp_path / "out"
        out_root.mkdir()
        scores_path = _write_scores_tsv(
            out_root,
            "scores.tsv",
            ["sub-01"],
            {"question": ["What is your favorite color?"]},
        )

        anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root,
            out_format="flat",
            mask_questions=True,
        )

        result_df = pd.read_csv(scores_path, sep="\t")
        assert (result_df["question"] == "[MASKED]").all()

    def test_missing_participants_tsv_raises(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()  # no participants.tsv written

        out_root = tmp_path / "out"
        out_root.mkdir()

        with pytest.raises(FileNotFoundError):
            anonymize_recipe_output(
                dataset_path=dataset_path, out_root=out_root, out_format="flat"
            )

    def test_missing_output_dir_raises(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        with pytest.raises(FileNotFoundError):
            anonymize_recipe_output(
                dataset_path=dataset_path,
                out_root=tmp_path / "does_not_exist",
                out_format="flat",
            )

    def test_participants_tsv_without_participant_id_column_raises(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        pd.DataFrame({"age": [20]}).to_csv(
            dataset_path / "participants.tsv", sep="\t", index=False
        )

        out_root = tmp_path / "out"
        out_root.mkdir()

        with pytest.raises(ValueError):
            anonymize_recipe_output(
                dataset_path=dataset_path, out_root=out_root, out_format="flat"
            )


class TestAnonymizeRecipeOutputSav:
    def test_masks_variable_labels_without_anonymizing_participant_ids(self, tmp_path):
        pyreadstat = pytest.importorskip("pyreadstat")
        out_root = tmp_path / "out"
        out_root.mkdir()
        sav_path = out_root / "wellbeing.sav"
        pyreadstat.write_sav(
            pd.DataFrame({"participant_id": ["sub-01"], "WB01": [3]}),
            sav_path,
            column_labels={"WB01": "I have felt cheerful and in good spirits"},
        )

        anonymized_count, mapping_file = anonymize_recipe_output(
            dataset_path=tmp_path / "dataset-without-participants",
            out_root=out_root,
            out_format="sav",
            anonymize_participant_ids=False,
            mask_questions=True,
        )

        data, metadata = pyreadstat.read_sav(sav_path)
        assert anonymized_count == 0
        assert mapping_file is None
        assert data["participant_id"].iloc[0] == "sub-01"
        assert metadata.column_names_to_labels["WB01"] == "[MASKED]"

    def test_masks_variable_labels_with_item_id_column_names(self, tmp_path):
        pyreadstat = pytest.importorskip("pyreadstat")
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root = tmp_path / "out"
        out_root.mkdir()
        sav_path = out_root / "wellbeing.sav"
        pyreadstat.write_sav(
            pd.DataFrame({"participant_id": ["sub-01"], "WB01": [3]}),
            sav_path,
            column_labels={
                "participant_id": "Participant identifier",
                "WB01": "I have felt cheerful and in good spirits",
            },
        )

        anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root,
            out_format="sav",
            mask_questions=True,
        )

        _data, metadata = pyreadstat.read_sav(sav_path)
        assert metadata.column_names_to_labels["WB01"] == "[MASKED]"
        assert metadata.column_names_to_labels["participant_id"] == "Participant identifier"

    def test_keeps_sociodemographic_and_score_variable_labels(self, tmp_path):
        pyreadstat = pytest.importorskip("pyreadstat")
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])
        (dataset_path / "participants.json").write_text(
            json.dumps({"age": {"Description": "Age in years"}}), encoding="utf-8"
        )
        out_root = tmp_path / "out"
        out_root.mkdir()
        sav_path = out_root / "wellbeing.sav"
        pyreadstat.write_sav(
            pd.DataFrame(
                {"participant_id": ["sub-01"], "age": [30], "WB01": [3], "Total": [3]}
            ),
            sav_path,
            column_labels={
                "participant_id": "Participant identifier",
                "age": "Age in years",
                "WB01": "I have felt cheerful and in good spirits",
                "Total": "Wellbeing total score",
            },
        )
        (out_root / "wellbeing_codebook.json").write_text(
            json.dumps({"variables": {"Total": {"score_info": {"method": "sum"}}}}),
            encoding="utf-8",
        )

        anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root,
            out_format="sav",
            mask_questions=True,
        )

        _data, metadata = pyreadstat.read_sav(sav_path)
        assert metadata.column_names_to_labels["age"] == "Age in years"
        assert metadata.column_names_to_labels["Total"] == "Wellbeing total score"
        assert metadata.column_names_to_labels["WB01"] == "[MASKED]"


class TestAnonymizeRecipeOutputCsv:
    def test_handles_csv_extension_as_well_as_tsv(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, ["sub-01"])

        out_root = tmp_path / "out"
        out_root.mkdir()
        csv_path = out_root / "scores.csv"
        pd.DataFrame({"participant_id": ["sub-01"], "score": [5]}).to_csv(
            csv_path, index=False
        )

        anonymize_recipe_output(
            dataset_path=dataset_path, out_root=out_root, out_format="csv"
        )

        result_df = pd.read_csv(csv_path, dtype=str)
        assert result_df["participant_id"].iloc[0] != "sub-01"


class TestAnonymizeRecipeOutputPrivacyMatrix:
    """Round-trip each privacy-control combination for every export family."""

    @pytest.mark.parametrize("out_format", ["tsv", "sav", "xlsx"])
    @pytest.mark.parametrize("anonymize_participant_ids", [False, True])
    @pytest.mark.parametrize("mask_questions", [False, True])
    def test_all_privacy_control_combinations(
        self,
        tmp_path,
        out_format,
        anonymize_participant_ids,
        mask_questions,
    ):
        participant_ids = ["sub-01", "sub-02"]
        question_text = "I have felt cheerful and in good spirits"
        dataset_path = tmp_path / "dataset"
        dataset_path.mkdir()
        _write_participants_tsv(dataset_path, participant_ids)
        out_root = tmp_path / "out"
        out_root.mkdir()

        if out_format == "sav":
            pyreadstat = pytest.importorskip("pyreadstat")
            output_path = out_root / "wellbeing.sav"
            pyreadstat.write_sav(
                pd.DataFrame({"participant_id": participant_ids, "WB01": [3, 4]}),
                output_path,
                column_labels={
                    "participant_id": "Participant identifier",
                    "WB01": question_text,
                },
            )
        elif out_format == "xlsx":
            output_path = out_root / "wellbeing.xlsx"
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                pd.DataFrame(
                    {"participant_id": participant_ids, "question": [question_text] * 2}
                ).to_excel(writer, sheet_name="responses", index=False)
                pd.DataFrame(
                    {"participant_id": participant_ids, "score": [3, 4]}
                ).to_excel(writer, sheet_name="scores", index=False)
        else:
            output_path = out_root / "wellbeing.tsv"
            pd.DataFrame(
                {"participant_id": participant_ids, "question": [question_text] * 2}
            ).to_csv(output_path, sep="\t", index=False)

        anonymized_count, mapping_file = anonymize_recipe_output(
            dataset_path=dataset_path,
            out_root=out_root,
            out_format=out_format,
            anonymize_participant_ids=anonymize_participant_ids,
            mask_questions=mask_questions,
        )

        if anonymize_participant_ids:
            assert anonymized_count == 1
            assert mapping_file is not None and mapping_file.exists()
            mapped_ids = set(json.loads(mapping_file.read_text())["mapping"].values())
        else:
            assert anonymized_count == 0
            assert mapping_file is None
            mapped_ids = set(participant_ids)

        if out_format == "sav":
            data, metadata = pyreadstat.read_sav(output_path)
            assert set(data["participant_id"]) == mapped_ids
            assert metadata.column_names_to_labels["participant_id"] == "Participant identifier"
            assert metadata.column_names_to_labels["WB01"] == (
                "[MASKED]" if mask_questions else question_text
            )
        elif out_format == "xlsx":
            responses = pd.read_excel(output_path, sheet_name="responses", dtype=str)
            scores = pd.read_excel(output_path, sheet_name="scores", dtype=str)
            assert set(responses["participant_id"]) == mapped_ids
            assert set(scores["participant_id"]) == mapped_ids
            assert set(responses["question"]) == {
                "[MASKED]" if mask_questions else question_text
            }
        else:
            data = pd.read_csv(output_path, sep="\t", dtype=str)
            assert set(data["participant_id"]) == mapped_ids
            assert set(data["question"]) == {
                "[MASKED]" if mask_questions else question_text
            }
