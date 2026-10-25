"""The survey converter must not invent dataset metadata a project already holds in project.json."""

import json

from src.converters.survey import _write_survey_description


def test_description_takes_name_and_keywords_from_project_json(tmp_path):
    (tmp_path / "project.json").write_text(
        json.dumps({"name": "test", "Basics": {"Name": "test", "Keywords": ["eins", "zwei"]}}),
        encoding="utf-8",
    )
    _write_survey_description(tmp_path, None, None)
    desc = json.loads((tmp_path / "dataset_description.json").read_text(encoding="utf-8"))
    assert desc["Name"] == "test"
    assert desc["Keywords"] == ["eins", "zwei"]


def test_description_without_project_json_keeps_defaults(tmp_path):
    _write_survey_description(tmp_path, None, None)
    desc = json.loads((tmp_path / "dataset_description.json").read_text(encoding="utf-8"))
    assert desc["Name"] == "PRISM Survey Dataset"
    assert desc["Keywords"] == ["psychology", "survey", "PRISM"]


def _project(root, name="test", keywords=("eins", "zwei")):
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(
        json.dumps({"name": name, "Basics": {"Name": name, "Keywords": list(keywords)}}), encoding="utf-8"
    )


def test_biometrics_description_takes_name_and_keywords_from_project_json(tmp_path):
    import pandas as pd

    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset

    library = tmp_path / "library"
    library.mkdir()
    (library / "biometrics-grip.json").write_text(json.dumps({"grip_left": {"unit": "kg"}, "Study": {}}))
    data = tmp_path / "data.csv"
    pd.DataFrame({"participant_id": ["001"], "grip_left": [40.0]}).to_csv(data, index=False)
    out = tmp_path / "out"
    _project(out)

    convert_biometrics_table_to_prism_dataset(input_path=data, library_dir=library, output_root=out, force=True)

    desc = json.loads((out / "dataset_description.json").read_text(encoding="utf-8"))
    assert desc["Name"] == "test"
    assert desc["Keywords"] == ["eins", "zwei"]


def test_csv_description_takes_name_and_keywords_from_project_json(tmp_path):
    import pandas as pd

    from src.converters.csv import process_dataframe

    out = tmp_path / "out"
    _project(out)
    process_dataframe(pd.DataFrame({"participant_id": ["001"]}), {}, str(out), str(tmp_path))

    desc = json.loads((out / "dataset_description.json").read_text(encoding="utf-8"))
    assert desc["Name"] == "test"
    assert desc["Keywords"] == ["eins", "zwei"]
