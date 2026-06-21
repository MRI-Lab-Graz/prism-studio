from __future__ import annotations

from pathlib import Path

from src.hostile_demo_generator import (
    ALL_DOMAINS,
    assert_text_files_never_annexed,
    generate_hostile_dataset,
)


def test_generate_hostile_dataset_all_domains(tmp_path: Path) -> None:
    result = generate_hostile_dataset(tmp_path / "demo", seed=1, use_datalad=False)

    assert result.project_root.exists()
    assert result.cases, "generator should produce at least one hostile case"
    assert set(result.files_written.keys()) == ALL_DOMAINS

    case_ids = [case.id for case in result.cases]
    assert len(case_ids) == len(set(case_ids)), "case ids must be unique"


def test_generate_hostile_dataset_domain_subset(tmp_path: Path) -> None:
    result = generate_hostile_dataset(
        tmp_path / "demo", seed=1, domains={"sociodemo"}, use_datalad=False
    )

    assert set(result.files_written.keys()) == {"sociodemo"}
    assert all(case.domain == "sociodemo" for case in result.cases)


def test_generate_hostile_dataset_is_deterministic(tmp_path: Path) -> None:
    result_a = generate_hostile_dataset(
        tmp_path / "demo_a", seed=42, domains={"sociodemo"}, use_datalad=False
    )
    result_b = generate_hostile_dataset(
        tmp_path / "demo_b", seed=42, domains={"sociodemo"}, use_datalad=False
    )

    file_a = result_a.project_root / "code" / "rawdata" / "hostile_participants_raw.csv"
    file_b = result_b.project_root / "code" / "rawdata" / "hostile_participants_raw.csv"
    assert file_a.read_bytes() == file_b.read_bytes()
    assert [c.id for c in result_a.cases] == [c.id for c in result_b.cases]


def test_generated_dataset_never_annexes_text_files(tmp_path: Path) -> None:
    result = generate_hostile_dataset(tmp_path / "demo", seed=1, use_datalad=False)
    violations = assert_text_files_never_annexed(result.project_root)
    assert violations == []


def test_generated_dataset_preserves_distinct_session_labels(tmp_path: Path) -> None:
    result = generate_hostile_dataset(
        tmp_path / "demo", seed=1, domains={"subject_session"}, use_datalad=False
    )
    subject_dir = result.project_root / "sub-sess01"
    sessions = sorted(p.name for p in subject_dir.iterdir() if p.is_dir())
    assert sessions == ["ses-01", "ses-1", "ses-pre"]


def test_generate_hostile_dataset_new_domains_produce_files(tmp_path: Path) -> None:
    result = generate_hostile_dataset(
        tmp_path / "demo",
        seed=1,
        domains={"entity_rewrite", "recipes", "input_formats"},
        use_datalad=False,
    )
    assert set(result.files_written.keys()) == {
        "entity_rewrite",
        "recipes",
        "input_formats",
    }

    recipes_dir = result.project_root / "code" / "recipes"
    assert (recipes_dir / "survey" / "recipe-hostile-missing-taskname.json").exists()
    assert (
        recipes_dir / "biometrics" / "recipe-hostile-missing-biometric-name.json"
    ).exists()

    rawdata_dir = result.project_root / "code" / "rawdata"
    assert (rawdata_dir / "hostile_biometrics_data_wide.xlsx").exists()
    assert (rawdata_dir / "hostile_participants_utf16.csv").exists()
    assert (rawdata_dir / "hostile_participants_latin1.csv").exists()


def test_generate_hostile_dataset_survey_full_run_domain(tmp_path: Path) -> None:
    result = generate_hostile_dataset(
        tmp_path / "demo", seed=1, domains={"survey_full_run"}, use_datalad=False
    )
    assert set(result.files_written.keys()) == {"survey_full_run"}
    assert all(case.domain == "survey_full_run" for case in result.cases)

    library_dir = result.project_root / "code" / "library" / "survey"
    template_files = list(library_dir.glob("survey-*.json"))
    assert len(template_files) == 1

    rawdata_dir = result.project_root / "code" / "rawdata"
    assert (rawdata_dir / "survey_clean_baseline.csv").exists()
    assert (rawdata_dir / "survey_exact_duplicate_rows.csv").exists()
    assert (rawdata_dir / "survey_conflicting_duplicate_rows.csv").exists()
    assert (rawdata_dir / "survey_out_of_range_value.csv").exists()
    assert (rawdata_dir / "survey_mixed_tab_comma_delimiters.csv").exists()

    recipe_files = list((result.project_root / "code" / "recipes" / "survey").glob("recipe-*.json"))
    assert len(recipe_files) == 1


def test_generate_hostile_dataset_participants_merge_domain(tmp_path: Path) -> None:
    result = generate_hostile_dataset(
        tmp_path / "demo", seed=1, domains={"participants_merge"}, use_datalad=False
    )
    assert set(result.files_written.keys()) == {"participants_merge"}
    assert all(case.domain == "participants_merge" for case in result.cases)

    rawdata_dir = result.project_root / "code" / "rawdata"
    assert (rawdata_dir / "participants_merge_initial_source.csv").exists()
    assert (rawdata_dir / "participants_merge_incoming_source.csv").exists()
    assert (rawdata_dir / "participants_merge_incoming_conflicting_duplicates.csv").exists()


def test_non_mri_domains_excludes_environment_mri() -> None:
    from src.hostile_demo_generator import ALL_DOMAINS, NON_MRI_DOMAINS

    assert "environment_mri" not in NON_MRI_DOMAINS
    assert NON_MRI_DOMAINS == ALL_DOMAINS - {"environment_mri"}
