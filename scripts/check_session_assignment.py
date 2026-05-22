#!/usr/bin/env python3
"""Helper script to audit session assignment consistency in a BIDS project.

Checks:
1) Session numbering (ses-1, ses-2, ses-3 ...) vs acquisition chronology from
   ``*acq-mprage_T1w.json`` sidecars.
2) Birth date consistency across sessions per subject.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.session_assignment_audit import audit_project_session_assignments


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether session labels match acquisition dates and whether "
            "birth dates stay consistent across timepoints."
        )
    )
    parser.add_argument(
        "project_root",
        help="Path to the project root (contains sub-* folders)",
    )
    parser.add_argument(
        "--pattern",
        default="*acq-mprage_T1w.json",
        help="Glob pattern used inside each session (default: *acq-mprage_T1w.json)",
    )
    parser.add_argument(
        "--show-ok-subjects",
        action="store_true",
        help="Also print subjects without findings",
    )
    return parser.parse_args()


def _format_date(value) -> str:
    return value.isoformat() if value is not None else "n/a"


def main() -> int:
    args = _parse_args()
    report = audit_project_session_assignments(
        project_root=Path(args.project_root),
        sidecar_pattern=args.pattern,
    )

    total_subjects = len(report.subjects)
    total_findings = len(report.findings)
    subjects_with_findings = [item for item in report.subjects if item.findings]

    print(f"Project: {report.project_root}")
    print(f"Pattern: {report.sidecar_pattern}")
    print(f"Subjects: {total_subjects}")
    print(f"Subjects with findings: {len(subjects_with_findings)}")
    print(f"Total findings: {total_findings}")

    for subject_audit in report.subjects:
        if not args.show_ok_subjects and not subject_audit.findings:
            continue

        print("")
        print(subject_audit.subject)
        for session in sorted(
            subject_audit.sessions,
            key=lambda item: (
                item.session_index is None,
                item.session_index if item.session_index is not None else item.session,
            ),
        ):
            print(
                "  "
                + f"{session.session}: index={session.session_index if session.session_index is not None else 'n/a'}, "
                + f"acquisition_date={_format_date(session.acquisition_date)}, "
                + f"birth_date={_format_date(session.birth_date)}, "
                + f"sidecars={session.sidecar_count}"
            )

        if subject_audit.findings:
            print("  Findings:")
            for finding in subject_audit.findings:
                print(f"    - [{finding.code}] {finding.message}")
        else:
            print("  Findings: none")

    return 1 if total_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
