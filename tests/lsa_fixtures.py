"""Synthetic LimeSurvey archive with response ids, completion and last page."""

import zipfile
from pathlib import Path

from tests.test_limesurvey_e2e import LSS_XML
from tests.test_survey_cli_lsa import _library as make_library  # noqa: F401

FIELDS = ["id", "token", "startdate", "submitdate", "lastpage", "MTESTSQ001", "MTESTSQ002", "MTESTSQ003"]

# a: one abandoned start + two completed; b: only abandoned starts; c: one completed.
REAL_PATTERN = [
    ["1", "a", "2026-03-01 09:00:00", "", "2", "4", "3", "5"],
    ["2", "a", "2026-03-01 11:00:00", "2026-03-01 11:20:00", "5", "2", "4", "3"],
    ["3", "a", "2026-09-01 10:00:00", "2026-09-01 10:20:00", "5", "3", "3", "3"],
    ["4", "b", "2026-03-02 10:00:00", "", "4", "1", "2", "3"],
    ["5", "b", "2026-03-02 10:05:00", "", "", "1", "2", "3"],
    ["6", "c", "2026-03-03 10:00:00", "2026-03-03 10:10:00", "5", "5", "5", "5"],
]


def make_lsa(tmp_path: Path, rows: list[list[str]] = REAL_PATTERN) -> Path:
    body = "".join(
        "<row>" + "".join(f"<{f}><![CDATA[{v}]]></{f}>" for f, v in zip(FIELDS, row)) + "</row>"
        for row in rows
    )
    lsr = (
        '<?xml version="1.0" encoding="UTF-8"?><document>'
        "<LimeSurveyDocType>Responses</LimeSurveyDocType><DBVersion>636</DBVersion>"
        "<languages><language>en</language></languages><responses><fields>"
        + "".join(f"<fieldname>{f}</fieldname>" for f in FIELDS)
        + f"</fields><rows>{body}</rows></responses></document>"
    )
    path = tmp_path / "repeated.lsa"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("survey_999999.lss", LSS_XML)
        z.writestr("survey_999999_responses.lsr", lsr)
    return path
