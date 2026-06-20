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
