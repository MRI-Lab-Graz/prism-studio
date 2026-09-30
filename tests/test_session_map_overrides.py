"""Multi-version questionnaires in a longitudinal project.

Template-version selections name sessions in OUTPUT space (ses-1, ...), not in the
source labels of the data (pre, post). They must be accepted when they name a session
the user defined, and what gets stored after a conversion must be the mapped session.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.converters.survey import _build_task_context_maps  # noqa: E402
from src.converters.survey_core import build_survey_id_normalizers  # noqa: E402
from src.session_map import SessionsNotMappedError, save_session_map  # noqa: E402
from src.web.services.project_registration import register_session_in_project  # noqa: E402

MAP = {"pre": "1", "post": "2"}
TEMPLATES = {
    "wellbeing-multi": {
        "json": {
            "Study": {
                "TaskName": "wellbeing-multi",
                "Version": "10-likert",
                "Versions": ["10-likert", "7-likert"],
            }
        }
    }
}


def context_maps(overrides, normalize_ses):
    df = pd.DataFrame({"session": ["pre", "post"]})
    return _build_task_context_maps(
        tasks_with_data={"wellbeing-multi"},
        df=df,
        res_ses_col="session",
        session="all",
        res_run_col=None,
        task_run_columns={},
        templates=TEMPLATES,
        template_version_overrides=overrides,
        normalize_ses_fn=normalize_ses,
    )[1]


def test_override_naming_an_output_session_is_accepted_in_a_longitudinal_project():
    normalize = build_survey_id_normalizers(None, session_map=MAP).normalize_ses
    acq = context_maps(
        [{"task": "wellbeing-multi", "session": "ses-1", "version": "7-likert"}], normalize
    )
    assert acq[("wellbeing-multi", "ses-1", None)] == "7-likert"
    assert acq[("wellbeing-multi", "ses-2", None)] == "10-likert"


def test_override_naming_a_source_label_is_mapped_first():
    normalize = build_survey_id_normalizers(None, session_map=MAP).normalize_ses
    acq = context_maps(
        [{"task": "wellbeing-multi", "session": "post", "version": "7-likert"}], normalize
    )
    assert acq[("wellbeing-multi", "ses-2", None)] == "7-likert"


def test_override_naming_a_session_the_user_never_defined_is_refused():
    normalize = build_survey_id_normalizers(None, session_map=MAP).normalize_ses
    with pytest.raises(SessionsNotMappedError) as info:
        context_maps(
            [{"task": "wellbeing-multi", "session": "ses-9", "version": "7-likert"}], normalize
        )
    assert info.value.labels == ["ses-9"]


def test_data_rows_still_need_a_source_entry_even_if_the_label_equals_a_target():
    normalize = build_survey_id_normalizers(None, session_map=MAP).normalize_ses
    with pytest.raises(SessionsNotMappedError):
        normalize("1")  # '1' is a target of 'pre', but the data label '1' is unmapped


def project(tmp_path, timepoints="multiple"):
    (tmp_path / "project.json").write_text(
        json.dumps({"StudyDesign": {"Timepoints": timepoints}})
    )
    return tmp_path


def stored_selections(root):
    return json.loads((root / "project.json").read_text())["TemplateVersionSelections"]


def test_registration_stores_the_mapped_session_not_the_raw_label(tmp_path):
    root = project(tmp_path)
    save_session_map(root, MAP)

    register_session_in_project(
        root, "pre", ["wellbeing-multi"], "survey", "f.csv", "survey-xlsx",
        template_version_overrides={"wellbeing-multi": "7-likert"},
    )

    assert stored_selections(root) == [
        {"task": "wellbeing-multi", "version": "7-likert", "session": "ses-1"}
    ]


def test_registration_maps_the_sessions_named_inside_the_selections_too(tmp_path):
    root = project(tmp_path)
    save_session_map(root, MAP)

    register_session_in_project(
        root, "all", ["wellbeing-multi"], "survey", "f.csv", "survey-xlsx",
        template_version_overrides=[
            {"task": "wellbeing-multi", "session": "pre", "version": "7-likert"},
            {"task": "wellbeing-multi", "session": "ses-2", "version": "10-likert"},
        ],
    )

    assert [e["session"] for e in stored_selections(root)] == ["ses-1", "ses-2"]


def test_what_registration_stored_is_valid_for_the_next_conversion(tmp_path):
    root = project(tmp_path)
    save_session_map(root, MAP)
    register_session_in_project(
        root, "pre", ["wellbeing-multi"], "survey", "f.csv", "survey-xlsx",
        template_version_overrides={"wellbeing-multi": "7-likert"},
    )

    normalize = build_survey_id_normalizers(root, session_map=MAP).normalize_ses
    acq = context_maps(stored_selections(root), normalize)  # must not raise

    assert acq[("wellbeing-multi", "ses-1", None)] == "7-likert"


def test_single_timepoint_project_registers_exactly_as_before(tmp_path):
    root = project(tmp_path, "single")

    register_session_in_project(
        root, "pre", ["wellbeing-multi"], "survey", "f.csv", "survey-xlsx",
        template_version_overrides={"wellbeing-multi": "7-likert"},
    )

    assert stored_selections(root)[0]["session"] == "ses-pre"
