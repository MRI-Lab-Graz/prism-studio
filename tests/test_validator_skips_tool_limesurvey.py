"""tool-limesurvey system-variable files are not PRISM survey data.

Their JSON sidecar (Metadata/SystemFields) must not be checked against the
survey schema (it used to fail with "'Technical' is a required property").
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "app", "src"))

from runner import _load_schemas, _validate_modality_dir
from validator import DatasetValidator


class _Stats:
    def add_file(self, *a, **k):
        pass


def test_tool_limesurvey_files_get_no_schema_errors(tmp_path):
    d = tmp_path / "sub-01" / "ses-1" / "survey"
    d.mkdir(parents=True)
    stem = "sub-01_ses-1_tool-limesurvey_survey"
    (d / f"{stem}.tsv").write_text("token\tseed\nabc\t1\n")
    (d / f"{stem}.json").write_text(
        json.dumps({"Metadata": {"SchemaVersion": "1.0.0", "Tool": "LimeSurvey"}, "SystemFields": {}})
    )
    issues = _validate_modality_dir(
        str(d), "sub-01", "ses-1", "survey",
        DatasetValidator(_load_schemas(str(tmp_path), None, {})[0]), _Stats(), str(tmp_path),
    )
    assert [i for i in issues if i[0] != "INFO"] == []
