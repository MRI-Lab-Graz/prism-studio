import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_proposal,
    errors_only,
    proposal_kind,
    read_proposal,
    write_proposal_workbook,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
NEW = EXAMPLES / "bloodwork.yml"


def _proposal(**over) -> dict:
    p = read_proposal(NEW)
    p.update(over)
    return p


def _messages(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_old_files_with_rationale_still_read(tmp_path):
    f = tmp_path / "p.yml"
    f.write_text(
        "modality: bloodwork\nsuffix: bloodchem\nextensions: [tsv]\ndescription: d\n"
        "rationale: old text\ncolumns:\n  - id: crp\n    description: c\n",
        encoding="utf-8",
    )
    assert "rationale" not in read_proposal(f)


def test_entities_are_read_from_yaml_and_workbook(tmp_path):
    p = read_proposal(NEW)
    assert {"entity": "acq", "value": "fasting"}.items() <= p["entities"][0].items()
    wb = tmp_path / "p.xlsx"
    write_proposal_workbook(p, wb)
    assert read_proposal(wb)["entities"] == p["entities"]


def test_missing_description_is_the_only_text_requirement():
    msg = _messages(check_proposal(_proposal(description="")))
    assert "Modality.Description" in msg
    assert "Rationale" not in msg


@pytest.mark.parametrize(
    "entities,needle",
    [
        ([{"entity": "run", "value": "1", "description": ""}], "task"),  # only task/acq suggestable
        ([{"entity": "acq", "value": "fasting study", "description": ""}], "letters and digits"),
        (
            [{"entity": "acq", "value": "a", "description": ""}, {"entity": "acq", "value": "a", "description": ""}],
            "duplicate",
        ),
    ],
)
def test_entity_suggestions_are_checked(entities, needle):
    assert needle in _messages(check_proposal(_proposal(entities=entities)))


def _ext(**over):
    return _proposal(**{"modality": "biometrics", "suffix": "bloodpanel", "entities": [], **over})


def test_kind_is_new_for_an_unknown_name_and_extension_for_a_prism_modality():
    assert proposal_kind(_proposal()) == "new"
    assert proposal_kind(_ext()) == "extension"


def test_extension_with_a_free_suffix_has_no_errors():
    assert errors_only(check_proposal(_ext())) == []


def test_extension_suffix_that_is_taken_is_still_rejected():
    assert "PRISM modality 'physio'" in _messages(check_proposal(_ext(suffix="physio")))
    assert "BIDS suffix 'blood'" in _messages(check_proposal(_ext(suffix="blood")))


def test_extension_cannot_carry_entity_suggestions():
    ents = [{"entity": "acq", "value": "fasting", "description": ""}]
    assert "existing modality" in _messages(check_proposal(_ext(entities=ents)))


def test_bids_and_passthrough_names_are_refused_with_advice():
    assert "BIDS" in _messages(check_proposal(_proposal(modality="anat")))
    assert "BIDS datatype 'phenotype'" in _messages(check_proposal(_proposal(modality="phenotype")))


import json  # noqa: E402

from src.modality_contribution import (  # noqa: E402
    build_modality_artifacts,
    build_registration_md,
    check_extension_fit,
    registration_entry,
)

EXT = EXAMPLES / "bloodpanel.yml"
EXT_SAMPLE = EXAMPLES / "bloodpanel_sample.tsv"


def test_extension_entry_appends_to_the_existing_one():
    existing = {"kind": "prism", "suffixes": ["biometrics"], "extensions": ["tsv", "json"]}
    e = registration_entry(read_proposal(EXT), existing)
    assert e == {"kind": "prism", "suffixes": ["biometrics", "bloodpanel"], "extensions": ["tsv", "json"]}
    e2 = registration_entry({**read_proposal(EXT), "extensions": ["tsv.gz"]}, existing)
    assert e2["extensions"] == ["tsv", "json", "tsv.gz"]


def test_extension_build_writes_no_schema_and_a_modality_fixture(tmp_path):
    p = read_proposal(EXT)
    files = build_modality_artifacts(p, EXT_SAMPLE, EXT, tmp_path / "out")
    names = {f.relative_to(tmp_path / "out").as_posix() for f in files}
    assert "biometrics.schema.json" not in names
    assert "fixture/sub-01/biometrics/sub-01_task-bloodpanel_bloodpanel.tsv" in names
    assert "docs/biometrics-bloodpanel.md" in names
    md = (tmp_path / "out" / "REGISTRATION.md").read_text(encoding="utf-8")
    assert '"bloodpanel"' in md and "biometrics.schema.json" not in md


def test_extension_example_sidecar_is_fitted_to_the_target_schema():
    assert check_extension_fit(read_proposal(EXT)) == []


def test_malformed_extension_proposal_returns_errors_without_raising():
    problems = check_proposal({**read_proposal(EXT), "extensions": []})
    assert "Modality.Extensions" in _messages(problems)


def test_new_build_fixture_has_no_task_entity(tmp_path):
    p = read_proposal(NEW)
    files = build_modality_artifacts(p, EXAMPLES / "bloodwork_sample.tsv", NEW, tmp_path / "o")
    assert any(f.name == "sub-01_bloodchem.tsv" for f in files)
    assert (tmp_path / "o" / "docs" / "bloodwork.md").is_file()
    assert json.loads((tmp_path / "o" / "example_sidecar.json").read_text())["Study"].get("TaskName") is None


def test_extension_docs_section_keeps_the_modality_own_naming_rules(tmp_path):
    build_modality_artifacts(read_proposal(EXT), EXT_SAMPLE, EXT, tmp_path / "out")
    section = (tmp_path / "out" / "docs" / "biometrics-bloodpanel.md").read_text(encoding="utf-8")
    assert "[_acq-<label>]" not in section
    assert "_bloodpanel" in section


@pytest.mark.parametrize("target,block", [("physio", "Technical"), ("survey", "Technical")])
def test_extension_into_other_modalities_warns_with_the_block_path(target, block, tmp_path):
    p = _ext(modality=target, suffix=f"x{target[:4]}")
    problems = check_proposal(p)
    assert errors_only(problems) == []
    warnings = [w.message for w in problems if w.severity == "warning"]
    assert any(m.startswith(f"{block}: ") for m in warnings), warnings
    assert not any(p["suffix"] in m for m in warnings), warnings  # no suffix string forced into a typed field
    build_modality_artifacts(p, EXT_SAMPLE, EXT, tmp_path / "out")  # does not crash


def test_environment_cannot_be_extended():
    assert "environment" in _messages(check_proposal(_ext(modality="environment", suffix="xenvi")))
    assert "Modality.Name" in _messages(check_proposal(_ext(modality="environment", suffix="xenvi")))


def test_fit_ignores_non_dict_property_schemas():
    from src.modality_contribution import _fit_sidecar

    schema = {"properties": {"Study": {"required": ["A", "B"], "properties": {"A": True}}}}
    assert _fit_sidecar({"Study": {}}, schema, "lbl") == {"Study": {}}


def test_extension_fixture_keeps_a_task_entity(tmp_path):
    files = build_modality_artifacts(read_proposal(EXT), EXT_SAMPLE, EXT, tmp_path / "out")
    assert any(f.name == "sub-01_task-bloodpanel_bloodpanel.tsv" for f in files)
    survey = _ext(modality="survey", suffix="xsurv")
    files = build_modality_artifacts(survey, EXT_SAMPLE, EXT, tmp_path / "s")
    assert any(f.name == "sub-01_task-panas_xsurv.tsv" for f in files)


def test_extension_registration_md_mentions_the_entities_table_row():
    md = (build_registration_md(read_proposal(EXT), {"kind": "prism", "suffixes": ["biometrics"], "extensions": ["tsv"]}))
    assert "specs/entities.md" in md and "docs/specs/entities.md" not in md and "Suffixes" in md


def test_numeric_entity_value_is_refused(tmp_path):
    from src.modality_contribution import ProposalError

    f = tmp_path / "p.yml"
    f.write_text(
        "modality: bloodwork\nsuffix: bloodchem\nextensions: [tsv]\ndescription: d\n"
        "columns:\n  - id: crp\n    description: c\nentities:\n  - entity: acq\n    value: 01\n",
        encoding="utf-8",
    )
    with pytest.raises(ProposalError, match="quotes"):
        read_proposal(f)
