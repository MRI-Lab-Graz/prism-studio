"""Ground truth for the validator: inject one known defect at a time into a clean project.

Each ``Defect`` names the PRISM code the issue catalogue (``app/src/issues.py``) promises for it.
``run_matrix`` applies every defect to a fresh copy of a clean control project, runs the real
validator and reports, per defect, whether the expected code appeared (``detected``), other
issues appeared instead (``wrong_code``) or nothing new was reported (``missed``). The control
itself must stay free of errors and warnings (``control_problems``), otherwise a "detected"
could be noise.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[1]
SURVEY_TEMPLATE = REPO / "official" / "library" / "survey" / "survey-brs.json"

ANY = "ANY"  # the catalogue has no code for it: any new error or warning counts
NONE = "NONE"  # messy but legal: the validator must stay quiet

DATA = "sub-01/ses-1/survey/sub-01_ses-1_task-brs_survey.tsv"
SIDECAR = "task-brs_survey.json"


@dataclass(frozen=True)
class Defect:
    id: str
    rule: str  # what the validator should catch, in words
    expect: str  # PRISM code from the issue catalogue
    mutate: Callable[[Path], None]


def _edit_json(path: Path, change: Callable[[dict], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write(rel: str, text: str) -> Callable[[Path], None]:
    return lambda root: (root / rel).write_text(text, encoding="utf-8")


def _remove(rel: str) -> Callable[[Path], None]:
    return lambda root: (root / rel).unlink()


def _rename(src: str, dst: str) -> Callable[[Path], None]:
    return lambda root: (root / src).rename(root / dst)


def _json(rel: str, change: Callable[[dict], None]) -> Callable[[Path], None]:
    return lambda root: _edit_json(root / rel, change)


def _answer(value: str) -> Callable[[Path], None]:
    """Replace the first answer of sub-01 (BRS01, a 0-4 item)."""
    return _write(DATA, f"BRS01\tBRS02\tBRS03\n{value}\t4\t2\n")


def _remove_subjects(root: Path) -> None:
    for folder in root.glob("sub-*"):
        shutil.rmtree(folder)


def _remove_data_file(root: Path) -> None:
    (root / "sub-03/ses-1/survey/sub-03_ses-1_task-brs_survey.tsv").unlink()


def _second_session_for_one_subject(root: Path) -> None:
    folder = root / "sub-02" / "ses-2" / "survey"
    folder.mkdir(parents=True)
    source = root / "sub-02" / "ses-1" / "survey" / "sub-02_ses-1_task-brs_survey.tsv"
    (folder / "sub-02_ses-2_task-brs_survey.tsv").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _participants_without_one_subject(root: Path) -> None:
    path = root / "participants.tsv"
    path.write_text("".join(line for line in path.read_text(encoding="utf-8").splitlines(True) if "sub-03" not in line), encoding="utf-8")


def _coded_participants_column(root: Path) -> None:
    path = root / "participants.tsv"
    rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([rows[0] + "\tgroup"] + [f"{r}\t{i % 2 + 1}" for i, r in enumerate(rows[1:])]) + "\n", encoding="utf-8")


def _copy_subject(src: str, dst: str) -> Callable[[Path], None]:
    """Copy sub-<src> as sub-<dst> (files renamed) and list it in participants.tsv."""
    def mutate(root: Path) -> None:
        _participants_row(f"sub-{dst}\t33\n")(root)
        shutil.copytree(root / f"sub-{src}", root / f"sub-{dst}")
        for path in (root / f"sub-{dst}").rglob(f"sub-{src}_*"):
            path.rename(path.with_name(path.name.replace(f"sub-{src}_", f"sub-{dst}_", 1)))
    return mutate


def _participants_row(row: str) -> Callable[[Path], None]:
    return lambda root: (root / "participants.tsv").open("a", encoding="utf-8").write(row)


def _mixed_session_padding(root: Path) -> None:
    """sub-02 uses ses-01 while everybody else uses ses-1."""
    shutil.move(root / "sub-02" / "ses-1", root / "sub-02" / "ses-01")
    (root / "sub-02/ses-01/survey/sub-02_ses-1_task-brs_survey.tsv").rename(root / "sub-02/ses-01/survey/sub-02_ses-01_task-brs_survey.tsv")


def _stray_file(root: Path) -> None:
    (root / "notes from the lab.docx").write_bytes(b"PK")


DEFECTS: list[Defect] = [
    Defect("missing_dataset_description", "dataset_description.json is absent", "PRISM001", _remove("dataset_description.json")),
    Defect("dataset_description_not_json", "dataset_description.json is not valid JSON", "PRISM202",
           _write("dataset_description.json", "{")),
    Defect("dataset_description_without_name", "dataset_description.json lacks its required Name", "PRISM301",
           _json("dataset_description.json", lambda d: d.pop("Name"))),
    Defect("missing_participants_tsv", "participants.tsv is absent", "PRISM004", _remove("participants.tsv")),
    Defect("no_subjects", "no sub-* folder exists", "PRISM002", _remove_subjects),
    Defect("missing_project_json", "project.json is absent", "PRISM010", _remove("project.json")),
    Defect("filename_without_task", "a survey file name lacks the task entity", "PRISM102",
           _rename(DATA, "sub-01/ses-1/survey/sub-01_ses-1_survey.tsv")),
    Defect("subject_label_differs_from_folder", "file in sub-01/ is named sub-09", "PRISM103",
           _rename(DATA, "sub-01/ses-1/survey/sub-09_ses-1_task-brs_survey.tsv")),
    Defect("session_label_differs_from_folder", "file in ses-1/ is named ses-2", "PRISM104",
           _rename(DATA, "sub-01/ses-1/survey/sub-01_ses-2_task-brs_survey.tsv")),
    Defect("missing_sidecar", "the survey sidecar is absent", "PRISM201", _remove(SIDECAR)),
    Defect("sidecar_not_json", "the sidecar is not valid JSON", "PRISM202", _write(SIDECAR, "{")),
    Defect("sidecar_empty", "the sidecar file is empty", "PRISM203", _write(SIDECAR, "")),
    Defect("data_file_empty", "a survey data file is empty", "PRISM401", _write(DATA, "")),
    Defect("empty_survey_folder", "a survey folder holds no file", "PRISM204", _remove_data_file),
    Defect("sidecar_missing_required_block", "the sidecar has no Study block", "PRISM301",
           _json(SIDECAR, lambda d: d.pop("Study"))),
    Defect("sidecar_field_wrong_type", "Technical is a string, not an object", "PRISM302",
           _json(SIDECAR, lambda d: d.__setitem__("Technical", "online"))),
    Defect("sidecar_old_schema_version", "the sidecar declares a schema version that does not exist", "PRISM005",
           _json(SIDECAR, lambda d: d["Metadata"].__setitem__("SchemaVersion", "0.0.1"))),
    Defect("bad_citation_file", "CITATION.cff is not valid CFF", "PRISM303", _write("CITATION.cff", "not: [valid")),
    Defect("missing_bidsignore", ".bidsignore is absent although PRISM folders need it", "PRISM501", _remove(".bidsignore")),
    Defect("data_file_header_only_blank", "a survey data file holds a blank line instead of a header", "PRISM401", _write(DATA, "\n")),
    Defect("value_outside_levels", "an answer of 9 on a 0-4 item", "PRISM402", _answer("9")),
    Defect("text_in_numeric_item", "text where a 0-4 answer belongs", "PRISM402", _answer("abc")),
    Defect("task_on_disk_not_declared", "data on disk for a task that no session declares", "PRISM703",
           _json("project.json", lambda d: d["Sessions"][0].__setitem__("tasks", []))),
    Defect("declared_task_without_data", "a session declares a required task that has no data", "PRISM704",
           _json("project.json", lambda d: d["Sessions"][0]["tasks"].append({"task": "ghost"}))),
    Defect("task_without_definition", "a session names a task that TaskDefinitions lacks", "PRISM705",
           _json("project.json", lambda d: d["TaskDefinitions"].pop("brs"))),
    Defect("participants_tsv_misses_a_subject", "sub-03 has a folder but no participants.tsv row", "PRISM707",
           _participants_without_one_subject),
    Defect("coded_column_without_labels", "participants.tsv has a coded column and no value labels", "PRISM709",
           _coded_participants_column),
    Defect("session_seen_for_one_subject", "ses-2 exists for one subject only (likely a typo)", "PRISM601",
           _second_session_for_one_subject),

    # messy files a real study produces
    Defect("ragged_row", "a data row has fewer cells than the header", ANY, _write(DATA, "BRS01\tBRS02\tBRS03\n3\t4\n")),
    Defect("extra_column_not_in_sidecar", "a data column the sidecar does not describe", ANY,
           _write(DATA, "BRS01\tBRS02\tBRS03\tBRS99\n3\t4\t2\t1\n")),
    Defect("header_with_trailing_space", "a column name ends with a space", ANY, _write(DATA, "BRS01 \tBRS02\tBRS03\n3\t4\t2\n")),
    Defect("decimal_comma_answer", "an answer written 3,5 (decimal comma)", ANY, _write(DATA, "BRS01\tBRS02\tBRS03\n3,5\t4\t2\n")),
    Defect("semicolon_separated_tsv", "a .tsv separated by semicolons", ANY, _write(DATA, "BRS01;BRS02;BRS03\n3;4;2\n")),
    Defect("nan_in_sidecar", "NaN written into a JSON sidecar", ANY, lambda root: _write(SIDECAR, (root / SIDECAR).read_text(encoding="utf-8").replace('"Reversed": false', '"Reversed": NaN', 1))(root)),
    Defect("participants_tsv_duplicate_id", "the same participant twice in participants.tsv", ANY, _participants_row("sub-01\t31\n")),
    Defect("participants_row_without_folder", "participants.tsv lists a participant that has no folder", "PRISM707", _participants_row("sub-99\t50\n")),
    Defect("non_ascii_subject_label", "sub-Müller is not a valid BIDS label", ANY, _copy_subject("03", "Müller")),
    Defect("session_padding_differs_between_subjects", "ses-1 for most subjects, ses-01 for one", "PRISM601", _mixed_session_padding),
    Defect("stray_file_at_root", "a word-processor file in the dataset root", ANY, _stray_file),
    # messy but legal: no issue may be reported
    Defect("benign_bom_and_crlf", "a data file saved by Excel (BOM, CRLF line endings)", NONE,
           lambda root: (root / DATA).write_bytes("\ufeffBRS01\tBRS02\tBRS03\r\n3\t4\t2\r\n".encode("utf-8"))),
    Defect("benign_sidecar_describes_more_items", "a file holds fewer items than the shared sidecar describes", NONE,
           _write(DATA, "BRS01\tBRS02\n3\t4\n")),
    Defect("benign_missing_answer_as_n_a", "an unanswered item written n/a", NONE, _write(DATA, "BRS01\tBRS02\tBRS03\nn/a\t4\t2\n")),
    Defect("benign_long_subject_label", "a 40-character alphanumeric participant label", NONE,
           _copy_subject("03", "x" * 40)),
]


# Defects the validator does not report with the catalogue's code (found by running this matrix).
# A defect leaves this list when the validator catches it; the test fails until it does.
KNOWN_GAPS: dict[str, str] = {
    "stray_file_at_root": "only the BIDS validator (run_bids) reports files outside the specification; this matrix runs PRISM checks only",
}


def build_clean_project(root: Path) -> None:
    """A small project the validator should accept: three participants, one survey, one session."""
    from src.converters.survey import convert_survey_file_to_prism_dataset
    from src.project_manager import ProjectManager

    created = ProjectManager().create_project(str(root), {"name": "clean-control"})
    if not created.get("success"):
        raise RuntimeError(created.get("error", "could not create the control project"))
    _edit_json(root / "project.json", _declare_project)
    work = Path(tempfile.mkdtemp(prefix="prism-matrix-"))
    try:
        library = work / "survey"
        library.mkdir()
        shutil.copy(SURVEY_TEMPLATE, library / SURVEY_TEMPLATE.name)
        answers = work / "answers.csv"
        answers.write_text(
            "participant_id,BRS01,BRS02,BRS03,BRS04,BRS05,BRS06\n"
            "sub-01,3,4,2,3,4,2\nsub-02,1,2,2,3,3,2\nsub-03,4,4,4,3,4,1\n",
            encoding="utf-8",
        )
        convert_survey_file_to_prism_dataset(
            input_path=answers, library_dir=library, output_root=root, name="clean-control",
            session_column=None, session=None, project_path=root, force=True,
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    (root / "participants.tsv").write_text("participant_id\tage\nsub-01\t30\nsub-02\t41\nsub-03\t25\n", encoding="utf-8")
    (root / "participants.json").write_text(
        json.dumps({"participant_id": {"Description": "Participant label"}, "age": {"Description": "Age at enrolment", "Unit": "year"}}, indent=2),
        encoding="utf-8",
    )


def _declare_project(data: dict) -> None:
    data["Basics"] = {"Name": "clean-control", "Authors": ["Ada Example"], "Keywords": ["resilience", "wellbeing", "survey"]}
    data["StudyDesign"] = {"Timepoints": "single"}
    data["Sessions"] = [{"id": "ses-1", "tasks": [{"task": "brs"}]}]
    data["TaskDefinitions"] = {"brs": {}}


def _validate(root: Path) -> dict[str, list[dict]]:
    """What each way of validating a project reports: ``validate`` is what ``prism.py`` runs,
    ``project`` is the Projects page check (``ProjectManager.validate_structure``), which adds
    project.json, participants.tsv and .bidsignore checks."""
    from src.project_manager import ProjectManager
    from src.share_publish import _core_validation

    core = _core_validation()
    issues, stats = core.validate_dataset(str(root), run_bids=False, run_prism=True)
    report = core.build_validation_report(str(root), "stable", issues, stats)["issues"]
    structure = ProjectManager().validate_structure(str(root))
    return {"validate": report, "project": structure["issues"] + structure["runner_warnings"]}


def _key(issue: dict, root: Path) -> tuple[str, str, str]:
    strip = lambda text: str(text or "").replace(str(root), "")  # noqa: E731
    return issue["code"], strip(issue.get("file_path")), strip(issue.get("message"))


def classify(expected: str, new_codes: list[str]) -> str:
    if expected == NONE:
        return "detected" if not new_codes else "false_positive"
    if expected == ANY:
        return "detected" if new_codes else "missed"
    if expected in new_codes:
        return "detected"
    return "wrong_code" if new_codes else "missed"


def control_problems(issues: dict[str, list[dict]]) -> list[dict]:
    """Errors and warnings on the clean control: a validator that reports these is noisy."""
    return [
        i for found in issues.values() for i in found
        if str(i.get("severity", "ERROR")).upper() in ("ERROR", "WARNING")
    ]


def run_matrix(clean: Path, defects: list[Defect] | None = None) -> dict:
    """Apply each defect to its own copy of ``clean`` and report what the validator said."""
    work = Path(tempfile.mkdtemp(prefix="prism-matrix-run-"))
    try:
        baseline = _validate(clean)
        base_keys = {(way, _key(i, clean)) for way, found in baseline.items() for i in found}
        rows = []
        for defect in defects or DEFECTS:
            copy = work / defect.id
            shutil.copytree(clean, copy)
            defect.mutate(copy)
            new = {way: [i for i in found if (way, _key(i, copy)) not in base_keys]
                   for way, found in _validate(copy).items()}
            codes = sorted({i["code"] for found in new.values() for i in found
                            if defect.expect not in (ANY, NONE) or str(i.get("severity", "ERROR")).upper() in ("ERROR", "WARNING")})
            by = [way for way, found in new.items() if any(i["code"] == defect.expect for i in found)]
            rows.append({"id": defect.id, "rule": defect.rule, "expected": defect.expect, "got": codes,
                         "by": by, "status": classify(defect.expect, codes)})
        return {"control_problems": control_problems(baseline), "rows": rows}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def matrix_problems(result: dict) -> list[str]:
    """What should fail a run: a noisy control, a newly missed defect, or a gap that is now closed."""
    undetected = {r["id"] for r in result["rows"] if r["status"] != "detected"}
    problems = [f"control project: {p['code']} {str(p.get('message'))[:100]}" for p in result["control_problems"]]
    problems += [f"newly undetected: {i}" for i in sorted(undetected - set(KNOWN_GAPS))]
    problems += [f"now detected, remove from KNOWN_GAPS: {i}" for i in sorted(set(KNOWN_GAPS) - undetected)]
    return problems


def format_matrix(result: dict) -> str:
    counts: dict[str, int] = {}
    for row in result["rows"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [
        f"{r['status']:<10} {r['expected']}  {r['id']}  (got: {', '.join(r['got']) or 'nothing new'}"
        + (f"; reported by: {', '.join(r['by'])}" if r["by"] else "") + ")"
        for r in result["rows"]
    ]
    lines.append("")
    lines.append(", ".join(f"{n} {status}" for status, n in sorted(counts.items())) + f" of {len(result['rows'])} defects")
    lines.append(f"control project: {len(result['control_problems'])} errors/warnings")
    return "\n".join(lines)
