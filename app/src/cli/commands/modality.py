"""Modality proposal command handler for prism_tools CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.modality_contribution import (
    Problem,
    ProposalError,
    build_modality_artifacts,
    check_proposal,
    check_sample,
    errors_only,
    read_proposal,
)


def _report(
    args,
    problems: list[Problem],
    modality: str = "",
    files: list[str] | None = None,
    exit_code: int = 1,
) -> None:
    # Prints the result, then exits with exit_code when any problem is an error.
    failed = bool(errors_only(problems))
    if bool(getattr(args, "json", False)):
        print(json.dumps({
            "success": not failed,
            "modality": modality,
            "problems": [
                {"severity": p.severity, "where": p.where, "message": p.message}
                for p in problems
            ],
            "files": files or [],
        }, ensure_ascii=False))
    else:
        for p in problems:
            print(p)
    if failed:
        sys.exit(exit_code)


def cmd_modality_propose(args) -> None:
    """Check a modality proposal and generate its schema, sidecar, fixture and notes."""
    json_mode = bool(getattr(args, "json", False))
    if not args.check and not args.out:
        _report(
            args,
            [Problem("error", "--out", "--out is required unless --check is given")],
            exit_code=2,
        )
    proposal_path = Path(args.proposal).expanduser()
    sample_path = Path(args.sample).expanduser()
    try:
        proposal = read_proposal(proposal_path)
    except (ProposalError, OSError) as exc:
        _report(args, [Problem("error", proposal_path.name, str(exc))])
        return

    problems = check_proposal(proposal) + check_sample(proposal, sample_path)
    if errors_only(problems):
        _report(args, problems, proposal["modality"])
        return

    if args.check:
        _report(args, problems, proposal["modality"])
        if not json_mode:
            print(f"OK: proposal '{proposal['modality']}' and its sample are valid")
        return

    out_dir = Path(args.out).expanduser()
    try:
        written = build_modality_artifacts(proposal, sample_path, proposal_path, out_dir)
    except OSError as exc:
        _report(args, [Problem("error", "--out", f"cannot write to {out_dir.name}: {exc}")], proposal["modality"])
        return
    files = [str(p) for p in written]
    _report(args, problems, proposal["modality"], files)
    if not json_mode:
        print(f"Wrote {len(files)} files to {out_dir}")
        print(f"Next: a maintainer follows {out_dir / 'REGISTRATION.md'}")
