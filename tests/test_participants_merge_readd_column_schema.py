"""Merge: a column that was removed and is added back must get a fresh annotation."""

import json

from src.participants_backend import apply_participants_merge, normalize_participant_mapping

MAPPING = {"participant_id": "participant_id", "age": "age", "sex": "sex"}
NEW_ANNOTATION = {
    "sex": {
        "Description": "NEW desc",
        "Annotations": {"IsAbout": {"TermURL": "nb:Sex", "Label": "Sex"}},
    }
}
OLD_SEX = {
    "Description": "OLD desc",
    "Levels": {"1": "male"},
    "Annotations": {
        "IsAbout": {"TermURL": "nb:OLD", "Label": "old"},
        "Format": {"TermURL": "nb:OLDFORMAT"},
    },
}


def _merge(tmp_path, tsv, schema):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "participants.tsv").write_text(tsv, encoding="utf-8")
    (project / "participants.json").write_text(json.dumps(schema), encoding="utf-8")
    source = tmp_path / "in.csv"
    source.write_text("participant_id,age,sex\n1,30,M\n2,40,F\n", encoding="utf-8")
    apply_participants_merge(
        project, source, normalize_participant_mapping(MAPPING),
        neurobagel_schema=NEW_ANNOTATION,
    )
    return json.loads((project / "participants.json").read_text(encoding="utf-8"))


def test_column_removed_from_table_gets_fresh_annotation_when_added_back(tmp_path):
    # 'sex' is gone from the table but its old entry is still in participants.json
    schema = _merge(
        tmp_path,
        "participant_id\tage\nsub-1\t30\nsub-2\t40\n",
        {"participant_id": {"Description": "id"}, "age": {"Description": "Age"}, "sex": OLD_SEX},
    )

    assert schema["sex"]["Description"] == "NEW desc"
    assert "1" not in schema["sex"].get("Levels", {})
    assert "Format" not in schema["sex"]["Annotations"]
    assert schema["sex"]["Annotations"]["IsAbout"]["TermURL"] == "nb:Sex"


def test_column_removed_from_annotation_only_gets_fresh_annotation(tmp_path):
    # 'sex' stays in the table; only its participants.json entry was removed
    schema = _merge(
        tmp_path,
        "participant_id\tage\tsex\nsub-1\t30\tM\nsub-2\t40\tF\n",
        {"participant_id": {"Description": "id"}, "age": {"Description": "Age"}},
    )

    assert schema["sex"]["Annotations"]["IsAbout"]["TermURL"] == "nb:Sex"


def test_existing_column_annotation_is_kept(tmp_path):
    schema = _merge(
        tmp_path,
        "participant_id\tage\tsex\nsub-1\t30\tM\nsub-2\t40\tF\n",
        {"participant_id": {"Description": "id"}, "age": {"Description": "Age"}, "sex": OLD_SEX},
    )

    assert schema["sex"]["Description"] == "OLD desc"
