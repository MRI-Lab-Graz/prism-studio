"""Preregistration draft: project.json -> AsPredicted-ordered Markdown (CLI + GUI route)."""

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

from src.preregistration import draft_markdown, load_draft  # noqa: E402

QUESTIONS = [
    "1. Have any data been collected for this study already?",
    "2. What is the main question or hypothesis being tested?",
    "3. Describe the key dependent variable(s) and how they will be measured.",
    "4. How many and which conditions will participants be assigned to?",
    "5. Specify exactly which analyses you will conduct.",
    "6. Describe how outliers will be defined and handled, and your rules for excluding observations.",
    "7. How many observations will be collected, or what will determine sample size?",
    "8. Anything else you would like to preregister?",
]

PROJECT = {
    "Preregistration": {
        "DataStatus": "not-collected",
        "Hypotheses": ["H1: Mindfulness lowers stress.", "H2: Effect lasts 4 weeks."],
        "PrimaryOutcomes": "PSS-10 total score",
        "SecondaryOutcomes": "WHO-5 total score",
        "AnalysisPlan": "ANCOVA with baseline covariate",
        "InferenceCriteria": "alpha = .05, Holm correction",
        "ExploratoryAnalyses": "Moderation by age",
    },
    "StudyDesign": {
        "Type": "randomized-controlled-trial",
        "Randomization": "Block randomization",
        "Blinding": "Single blind",
        "ControlCondition": "Waitlist",
    },
    "Conditions": {
        "Groups": [
            {"id": "mind", "label": "Mindfulness", "description": "8-week course"},
            {"id": "wait", "label": "Waitlist"},
        ]
    },
    "Eligibility": {
        "InclusionCriteria": ["Age 18-65"],
        "ExclusionCriteria": ["Current psychotherapy"],
        "TargetSampleSize": 120,
        "PowerAnalysis": "G*Power, d = .5, power = .80",
    },
    "Procedure": {
        "QualityControl": ["Attention checks"],
        "MissingDataHandling": "Multiple imputation",
    },
}


def section(md: str, n: int) -> str:
    """Text of question n (without its heading)."""
    start = md.index(QUESTIONS[n - 1]) + len(QUESTIONS[n - 1])
    end = md.index(QUESTIONS[n]) if n < len(QUESTIONS) else len(md)
    return md[start:end]


def test_all_questions_appear_in_order():
    md = draft_markdown(PROJECT)
    positions = [md.index(q) for q in QUESTIONS]
    assert positions == sorted(positions)


def test_answers_come_from_the_matching_fields():
    md = draft_markdown(PROJECT)
    assert "No data collected yet" in section(md, 1)
    assert "- H1: Mindfulness lowers stress." in section(md, 2)
    assert "- H2: Effect lasts 4 weeks." in section(md, 2)
    assert "PSS-10 total score" in section(md, 3)
    q4 = section(md, 4)
    assert "Mindfulness" in q4 and "8-week course" in q4 and "Waitlist" in q4
    assert "Block randomization" in q4 and "Single blind" in q4
    q5 = section(md, 5)
    assert "ANCOVA with baseline covariate" in q5 and "Holm correction" in q5
    q6 = section(md, 6)
    assert "Current psychotherapy" in q6 and "Attention checks" in q6
    assert "Multiple imputation" in q6
    q7 = section(md, 7)
    assert "120" in q7 and "G*Power" in q7 and "Age 18-65" in q7
    q8 = section(md, 8)
    assert "WHO-5 total score" in q8 and "Moderation by age" in q8


def test_empty_project_flags_every_question_instead_of_dropping_it():
    md = draft_markdown({})
    for n in range(1, len(QUESTIONS) + 1):
        assert "Not filled in yet" in section(md, n), f"question {n} is silent"


def test_draft_says_it_is_not_a_registration():
    assert "not a registration" in draft_markdown({}).lower()


def test_wrong_typed_values_from_a_hand_edited_project_json_do_not_crash():
    md = draft_markdown(
        {
            "Preregistration": {"Hypotheses": "one hypothesis as a string"},
            "Conditions": {"Groups": "oops"},
            "Eligibility": {"TargetSampleSize": None},
        }
    )
    assert "one hypothesis as a string" in section(md, 2)


def test_unknown_data_status_is_shown_not_hidden():
    md = draft_markdown({"Preregistration": {"DataStatus": "weird"}})
    assert "weird" in section(md, 1)


def test_load_draft_reads_project_root_or_project_json(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    assert "PSS-10 total score" in load_draft(tmp_path)
    assert "PSS-10 total score" in load_draft(tmp_path / "project.json")


def test_load_draft_without_project_json_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_draft(tmp_path)


# ---- CLI -------------------------------------------------------------------


def _run_cli(argv):
    from src.cli.entrypoint import main

    old = sys.argv
    sys.argv = ["prism_tools.py", *argv]
    try:
        main()
    finally:
        sys.argv = old


def test_cli_prints_the_draft(tmp_path, capsys):
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    _run_cli(["preregistration", "draft", "--project", str(tmp_path)])
    assert QUESTIONS[0] in capsys.readouterr().out


def test_cli_writes_output_file(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    out = tmp_path / "prereg.md"
    _run_cli(
        ["preregistration", "draft", "--project", str(tmp_path), "--output", str(out)]
    )
    assert QUESTIONS[0] in out.read_text(encoding="utf-8")


def test_cli_reports_missing_project_json(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        _run_cli(["preregistration", "draft", "--project", str(tmp_path)])
    assert exc.value.code == 2
    assert "project.json" in capsys.readouterr().out


def test_cli_works_on_a_project_that_is_not_ready_yet(tmp_path, capsys):
    """A draft is prepared early, so the required-fields gate must not block it."""
    (tmp_path / "project.json").write_text(
        json.dumps({"Metadata": {}}), encoding="utf-8"
    )
    _run_cli(["preregistration", "draft", "--project", str(tmp_path)])
    assert "Not filled in yet" in capsys.readouterr().out


# ---- GUI: thin route over the same function ---------------------------------


def test_gui_route_serves_the_same_markdown(tmp_path):
    from flask import Flask

    from src.web.blueprints.projects import projects_bp

    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(projects_bp)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["current_project_path"] = str(tmp_path)
        sess["current_project_name"] = "demo"

    resp = client.get("/api/projects/preregistration-draft")
    assert resp.status_code == 200
    assert resp.mimetype == "text/markdown"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert resp.get_data(as_text=True) == load_draft(tmp_path)


def test_gui_route_without_project_is_an_error():
    from flask import Flask

    from src.web.blueprints.projects import projects_bp

    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(projects_bp)
    assert (
        app.test_client().get("/api/projects/preregistration-draft").status_code == 400
    )


def test_download_link_is_only_rendered_when_a_project_is_open():
    tpl = (REPO / "app/templates/includes/projects/study_metadata.html").read_text()
    assert re.search(
        r'\{% if current_project\.path %\}\s*<div[^>]*>\s*<a [^>]*id="smPreregDownload"',
        tpl,
    )


def test_cli_format_md_equals_load_draft(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    out = tmp_path / "p.md"
    _run_cli(["preregistration", "draft", "--project", str(tmp_path), "--format", "md", "--output", str(out)])
    assert out.read_text(encoding="utf-8") == load_draft(tmp_path)


def test_cli_format_docx_writes_zip(tmp_path):
    import zipfile

    pytest.importorskip("docx")
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    out = tmp_path / "p.docx"
    _run_cli(["preregistration", "draft", "--project", str(tmp_path), "--format", "docx", "--output", str(out)])
    assert zipfile.is_zipfile(out)


def test_cli_format_docx_requires_output(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_cli(["preregistration", "draft", "--project", str(tmp_path), "--format", "docx"])
    assert exc.value.code == 2


def test_gui_route_format_tex_and_default_unchanged(tmp_path):
    from flask import Flask

    from src.web.blueprints.projects import projects_bp

    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(projects_bp)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["current_project_path"] = str(tmp_path)

    tex = client.get("/api/projects/preregistration-draft?format=tex")
    assert tex.status_code == 200
    assert tex.get_data(as_text=True).startswith("\\documentclass")
    assert "preregistration_draft.tex" in tex.headers["Content-Disposition"]
    assert client.get("/api/projects/preregistration-draft?format=pdf").status_code == 400
    assert (
        client.get("/api/projects/preregistration-draft").get_data(as_text=True)
        == load_draft(tmp_path)
    )
