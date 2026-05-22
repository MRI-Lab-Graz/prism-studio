"""Audit session assignment consistency using MRI sidecar metadata.

The audit compares the chronological order of acquisition dates from
``*acq-mprage_T1w.json`` sidecars against numeric session labels (``ses-1``,
``ses-2``, ``ses-3`` ...) and checks birth-date consistency across sessions
for each subject.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from src.system_files import is_system_file

_ACQUISITION_DATE_KEYS = (
    "AcquisitionDateTime",
    "AcquisitionDate",
    "SeriesDate",
    "StudyDate",
    "ContentDate",
)

_BIRTH_DATE_KEYS = (
    "PatientBirthDate",
    "DateOfBirth",
    "BirthDate",
)

_SESSION_LABEL_RE = re.compile(r"^ses-(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class AuditFinding:
    """A single audit finding produced for one subject."""

    subject: str
    code: str
    message: str


@dataclass(frozen=True)
class SessionInfo:
    """Extracted audit-relevant metadata for one subject session."""

    session: str
    session_index: int | None
    sidecar_count: int
    acquisition_date: date | None
    birth_date: date | None


@dataclass(frozen=True)
class SubjectAudit:
    """Audit data and findings for one subject."""

    subject: str
    sessions: list[SessionInfo]
    findings: list[AuditFinding]


@dataclass(frozen=True)
class ProjectAudit:
    """Complete audit result for a project."""

    project_root: Path
    sidecar_pattern: str
    subjects: list[SubjectAudit]

    @property
    def findings(self) -> list[AuditFinding]:
        """Flattened list of findings across all subjects."""
        all_findings: list[AuditFinding] = []
        for subject_audit in self.subjects:
            all_findings.extend(subject_audit.findings)
        return all_findings


def _extract_case_insensitive_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered_map = {key.lower(): key for key in payload.keys()}
    for expected_key in keys:
        actual_key = lowered_map.get(expected_key.lower())
        if actual_key is not None:
            return payload.get(actual_key)
    return None


def _parse_date_value(raw_value: Any) -> date | None:
    """Parse supported date/date-time values into ``datetime.date``."""
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    compact_digits = re.sub(r"[^0-9]", "", text)
    if len(compact_digits) >= 8:
        yyyymmdd = compact_digits[:8]
        try:
            from datetime import datetime

            return datetime.strptime(yyyymmdd, "%Y%m%d").date()
        except ValueError:
            return None

    return None


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return payload
    raise ValueError("JSON content must be an object")


def _parse_session_index(session_label: str) -> int | None:
    match = _SESSION_LABEL_RE.match(session_label)
    if not match:
        return None
    return int(match.group(1))


def _collect_session_sidecars(session_dir: Path, sidecar_pattern: str) -> list[Path]:
    sidecars: list[Path] = []
    for candidate in session_dir.rglob(sidecar_pattern):
        if not candidate.is_file() or is_system_file(candidate.name):
            continue
        sidecars.append(candidate)
    return sorted(sidecars)


def _audit_subject(
    project_root: Path,
    subject_dir: Path,
    sidecar_pattern: str,
) -> SubjectAudit:
    subject = subject_dir.name
    findings: list[AuditFinding] = []
    sessions: list[SessionInfo] = []

    session_dirs = [
        child
        for child in sorted(subject_dir.iterdir())
        if child.is_dir() and child.name.startswith("ses-") and not is_system_file(child.name)
    ]

    if not session_dirs:
        findings.append(
            AuditFinding(
                subject=subject,
                code="no_sessions_found",
                message="No ses-* folders found for subject.",
            )
        )
        return SubjectAudit(subject=subject, sessions=sessions, findings=findings)

    for session_dir in session_dirs:
        session_label = session_dir.name
        session_index = _parse_session_index(session_label)
        if session_index is None:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="non_numeric_session_label",
                    message=f"Session label '{session_label}' is not numeric (expected ses-1, ses-2, ...).",
                )
            )

        sidecars = _collect_session_sidecars(session_dir, sidecar_pattern)
        if not sidecars:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="missing_sidecars",
                    message=f"No sidecars matching '{sidecar_pattern}' in {session_label}.",
                )
            )
            sessions.append(
                SessionInfo(
                    session=session_label,
                    session_index=session_index,
                    sidecar_count=0,
                    acquisition_date=None,
                    birth_date=None,
                )
            )
            continue

        acquisition_dates: set[date] = set()
        birth_dates: set[date] = set()

        for sidecar in sidecars:
            rel_sidecar = sidecar.relative_to(project_root)
            try:
                payload = _load_json(sidecar)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                findings.append(
                    AuditFinding(
                        subject=subject,
                        code="unreadable_sidecar",
                        message=f"Could not read {rel_sidecar}: {exc}",
                    )
                )
                continue

            acquisition_raw = _extract_case_insensitive_value(payload, _ACQUISITION_DATE_KEYS)
            acquisition_date = _parse_date_value(acquisition_raw)
            if acquisition_raw is not None and acquisition_date is None:
                findings.append(
                    AuditFinding(
                        subject=subject,
                        code="invalid_acquisition_date",
                        message=f"Could not parse acquisition date in {rel_sidecar}.",
                    )
                )
            if acquisition_date is not None:
                acquisition_dates.add(acquisition_date)

            birth_raw = _extract_case_insensitive_value(payload, _BIRTH_DATE_KEYS)
            birth_date = _parse_date_value(birth_raw)
            if birth_raw is not None and birth_date is None:
                findings.append(
                    AuditFinding(
                        subject=subject,
                        code="invalid_birth_date",
                        message=f"Could not parse birth date in {rel_sidecar}.",
                    )
                )
            if birth_date is not None:
                birth_dates.add(birth_date)

        if len(acquisition_dates) > 1:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="multiple_acquisition_dates_within_session",
                    message=f"Session {session_label} has multiple acquisition dates: "
                    + ", ".join(sorted(item.isoformat() for item in acquisition_dates)),
                )
            )

        if len(birth_dates) > 1:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="multiple_birth_dates_within_session",
                    message=f"Session {session_label} has multiple birth dates: "
                    + ", ".join(sorted(item.isoformat() for item in birth_dates)),
                )
            )

        selected_acquisition_date = min(acquisition_dates) if acquisition_dates else None
        selected_birth_date = next(iter(birth_dates)) if len(birth_dates) == 1 else None

        if selected_acquisition_date is None:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="missing_acquisition_date",
                    message=f"No parseable acquisition date found in {session_label}.",
                )
            )

        if selected_birth_date is None:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="missing_birth_date",
                    message=f"No unique parseable birth date found in {session_label}.",
                )
            )

        sessions.append(
            SessionInfo(
                session=session_label,
                session_index=session_index,
                sidecar_count=len(sidecars),
                acquisition_date=selected_acquisition_date,
                birth_date=selected_birth_date,
            )
        )

    comparable_sessions = [
        item for item in sessions if item.session_index is not None and item.acquisition_date is not None
    ]
    if len(comparable_sessions) >= 2:
        by_index = sorted(comparable_sessions, key=lambda item: item.session_index or -1)
        by_date = sorted(
            comparable_sessions,
            key=lambda item: (item.acquisition_date or date.min, item.session_index or -1),
        )

        ordered_by_index = [item.session for item in by_index]
        ordered_by_date = [item.session for item in by_date]
        if ordered_by_index != ordered_by_date:
            findings.append(
                AuditFinding(
                    subject=subject,
                    code="session_date_order_mismatch",
                    message=(
                        "Session numbering does not match acquisition chronology. "
                        f"By session: {ordered_by_index}; by date: {ordered_by_date}."
                    ),
                )
            )

    birth_dates_across_sessions = {
        item.birth_date for item in sessions if item.birth_date is not None
    }
    if len(birth_dates_across_sessions) > 1:
        findings.append(
            AuditFinding(
                subject=subject,
                code="birth_date_mismatch_across_sessions",
                message=(
                    "Birth date differs across sessions: "
                    + ", ".join(sorted(item.isoformat() for item in birth_dates_across_sessions))
                ),
            )
        )

    return SubjectAudit(subject=subject, sessions=sessions, findings=findings)


def audit_project_session_assignments(
    project_root: Path,
    sidecar_pattern: str = "*acq-mprage_T1w.json",
) -> ProjectAudit:
    """Audit all subjects in a project for session/date consistency."""
    root = Path(project_root)
    if not root.exists():
        raise FileNotFoundError(f"Project path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Project path is not a directory: {root}")

    subject_dirs = [
        child
        for child in sorted(root.iterdir())
        if child.is_dir() and child.name.startswith("sub-") and not is_system_file(child.name)
    ]

    audits = [
        _audit_subject(project_root=root, subject_dir=subject_dir, sidecar_pattern=sidecar_pattern)
        for subject_dir in subject_dirs
    ]

    return ProjectAudit(project_root=root, sidecar_pattern=sidecar_pattern, subjects=audits)


__all__ = [
    "AuditFinding",
    "SessionInfo",
    "SubjectAudit",
    "ProjectAudit",
    "audit_project_session_assignments",
]
