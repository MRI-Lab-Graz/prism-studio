"""Tests for src/session_assignment_audit.py."""

import json
import os
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.session_assignment_audit import (
    audit_project_session_assignments,
    write_project_audit_csv,
)


def _write_sidecar(
    dataset_root,
    *,
    subject: str,
    session: str,
    acquisition_date: str,
    birth_date: str,
    filename: str = "sub-001_acq-mprage_T1w.json",
):
    sidecar = dataset_root / subject / session / "anat" / filename
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {
                "AcquisitionDate": acquisition_date,
                "PatientBirthDate": birth_date,
            }
        ),
        encoding="utf-8",
    )


def test_audit_ok_when_sessions_match_chronology_and_birth_date(tmp_path):
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-1",
        acquisition_date="20240101",
        birth_date="19800101",
        filename="sub-001_ses-1_acq-mprage_T1w.json",
    )
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-2",
        acquisition_date="20240201",
        birth_date="19800101",
        filename="sub-001_ses-2_acq-mprage_T1w.json",
    )
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-3",
        acquisition_date="20240301",
        birth_date="19800101",
        filename="sub-001_ses-3_acq-mprage_T1w.json",
    )

    report = audit_project_session_assignments(tmp_path)

    assert len(report.subjects) == 1
    assert len(report.findings) == 0
    assert [item.session for item in report.subjects[0].sessions] == [
        "ses-1",
        "ses-2",
        "ses-3",
    ]


def test_audit_reports_session_date_order_mismatch(tmp_path):
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-1",
        acquisition_date="20240501",
        birth_date="19800101",
        filename="sub-001_ses-1_acq-mprage_T1w.json",
    )
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-2",
        acquisition_date="20240101",
        birth_date="19800101",
        filename="sub-001_ses-2_acq-mprage_T1w.json",
    )

    report = audit_project_session_assignments(tmp_path)
    finding_codes = [finding.code for finding in report.findings]

    assert "session_date_order_mismatch" in finding_codes


def test_audit_reports_birth_date_mismatch_across_sessions(tmp_path):
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-1",
        acquisition_date="20240101",
        birth_date="19800101",
        filename="sub-001_ses-1_acq-mprage_T1w.json",
    )
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-2",
        acquisition_date="20240201",
        birth_date="19800101",
        filename="sub-001_ses-2_acq-mprage_T1w.json",
    )
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-3",
        acquisition_date="20240301",
        birth_date="19990131",
        filename="sub-001_ses-3_acq-mprage_T1w.json",
    )

    report = audit_project_session_assignments(tmp_path)
    finding_codes = [finding.code for finding in report.findings]

    assert "birth_date_mismatch_across_sessions" in finding_codes


def test_audit_reports_non_numeric_session_label(tmp_path):
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-baseline",
        acquisition_date="20240101",
        birth_date="19800101",
        filename="sub-001_ses-baseline_acq-mprage_T1w.json",
    )

    report = audit_project_session_assignments(tmp_path)
    finding_codes = [finding.code for finding in report.findings]

    assert "non_numeric_session_label" in finding_codes


def test_write_project_audit_csv_contains_session_and_finding_rows(tmp_path):
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-1",
        acquisition_date="20240201",
        birth_date="19800101",
        filename="sub-001_ses-1_acq-mprage_T1w.json",
    )
    _write_sidecar(
        tmp_path,
        subject="sub-001",
        session="ses-2",
        acquisition_date="20240101",
        birth_date="19800101",
        filename="sub-001_ses-2_acq-mprage_T1w.json",
    )

    report = audit_project_session_assignments(tmp_path)
    csv_path = tmp_path / "audit.csv"
    write_project_audit_csv(report, csv_path)

    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    record_types = [row["record_type"] for row in rows]
    assert "session" in record_types
    assert "finding" in record_types
    assert any(row["code"] == "session_date_order_mismatch" for row in rows)
