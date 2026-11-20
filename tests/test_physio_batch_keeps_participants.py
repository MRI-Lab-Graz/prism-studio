"""A physio batch save never replaces the project's participants table, and its log names sessions once."""

from types import SimpleNamespace

from src.conversion_to_project import register_converted_physio_sessions, save_physio_batch_to_project


def _world(tmp_path):
    project, staged = tmp_path / "proj", tmp_path / "staged"
    (project / "sub-001").mkdir(parents=True)
    (project / "participants.tsv").write_text("participant_id\tage\tgroup\nsub-001\t23\tA\n", encoding="utf-8")
    (project / "participants.json").write_text('{"age": {"Description": "Age in years"}}', encoding="utf-8")
    folder = staged / "sub-002" / "ses-1" / "physio"
    folder.mkdir(parents=True)
    (folder / "sub-002_ses-1_recording-ecg_physio.tsv.gz").write_text("d", encoding="utf-8")
    (staged / "participants.tsv").write_text("participant_id\nsub-002\n", encoding="utf-8")  # the bare ID list
    (staged / "participants.json").write_text('{"participant_id": {"Description": "bare"}}', encoding="utf-8")
    converted = [SimpleNamespace(success=True, session="ses-1", task=None, target_folder="physio")]
    return project, staged, converted


def test_existing_participant_columns_survive_and_new_subject_is_added(tmp_path):
    project, staged, converted = _world(tmp_path)
    save_physio_batch_to_project(
        project_root=project, staged_root=staged, converted=converted, dataset_name="d", dest_root="prism",
        flat_structure=False, modality_filter="all", subject_rewrite_mode="keep",
    )
    rows = (project / "participants.tsv").read_text(encoding="utf-8").splitlines()
    assert rows[0] == "participant_id\tage\tgroup"
    assert "sub-001\t23\tA" in rows and "sub-002\tn/a\tn/a" in rows
    assert "Age in years" in (project / "participants.json").read_text(encoding="utf-8")


def test_session_label_is_not_prefixed_twice(tmp_path):
    logs = []
    register_converted_physio_sessions(
        tmp_path, [SimpleNamespace(success=True, session="ses-1", task=None, target_folder="physio")], "d",
        log_fn=lambda msg, level="info": logs.append(msg),
    )
    assert logs == ["Registered in project.json: ses-1 (physio)"]


def test_physio_save_writes_bidsignore_so_bids_validators_skip_physio(tmp_path):
    project, staged, converted = _world(tmp_path)
    save_physio_batch_to_project(
        project_root=project, staged_root=staged, converted=converted, dataset_name="d", dest_root="prism",
        flat_structure=False, modality_filter="all", subject_rewrite_mode="keep",
    )
    rules = (project / ".bidsignore").read_text(encoding="utf-8").splitlines()
    assert "physio/" in rules


def test_physio_report_folder_is_a_valid_derivative(tmp_path):
    import json

    from src.batch_convert import _physio_report_dir

    converted = SimpleNamespace(subject="sub-001", session="ses-1")
    folder = _physio_report_dir(tmp_path, converted)
    assert folder == tmp_path / "derivatives" / "physio" / "sub-001" / "ses-1"
    description = json.loads((tmp_path / "derivatives" / "physio" / "dataset_description.json").read_text("utf-8"))
    assert description["DatasetType"] == "derivative" and description["Name"] and description["BIDSVersion"]
