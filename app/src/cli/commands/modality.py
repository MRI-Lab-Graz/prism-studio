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


def _report(args, problems: list[Problem], modality: str = "", files: list[str] | None = None) -> None:
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
        sys.exit(1)


def cmd_modality_propose(args) -> None:
    """Check a modality proposal and generate its schema, sidecar, fixture and notes."""
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
        if not bool(getattr(args, "json", False)):
            print(f"OK: proposal '{proposal['modality']}' and its sample are valid")
        return

    if not args.out:
        print("Error: --out is required unless --check is given")
        sys.exit(2)
    written = build_modality_artifacts(proposal, sample_path, proposal_path, Path(args.out).expanduser())
    out_dir = Path(args.out).expanduser()
    files = [str(p) for p in written]
    _report(args, problems, proposal["modality"], files)
    if not bool(getattr(args, "json", False)):
        print(f"Wrote {len(files)} files to {out_dir}")
        print(f"Next: a maintainer follows {out_dir / 'REGISTRATION.md'}")
