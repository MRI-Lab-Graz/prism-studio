"""CLI handler for `prism_tools dataset build-hostile-demo`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.hostile_demo_generator import ALL_DOMAINS, generate_hostile_dataset
from src.hostile_demo_guide import write_demo_guide


def cmd_dataset_build_hostile_demo(args) -> None:
    """Generate an adversarial PRISM dataset for stress-testing backend pipelines."""
    output_root = Path(args.output).resolve()
    domains_arg = (args.domains or "all").strip()
    domains = None if domains_arg in ("", "all") else set(domains_arg.split(","))
    if domains is not None and not domains <= ALL_DOMAINS:
        unknown = domains - ALL_DOMAINS
        print(f"Error: unknown domain(s): {', '.join(sorted(unknown))}")
        sys.exit(1)

    try:
        result = generate_hostile_dataset(
            output_root,
            seed=args.seed,
            domains=domains,
            use_datalad=args.use_datalad,
            name=args.name,
        )
    except Exception as error:
        print(f"Error generating hostile demo dataset: {error}")
        sys.exit(1)

    guide_path = None
    if args.guide:
        guide_path = write_demo_guide(result, output_root / "DEMO_GUIDE.md")

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "success": True,
                    "project_root": str(result.project_root),
                    "case_count": len(result.cases),
                    "case_ids": [case.id for case in result.cases],
                    "guide": str(guide_path) if guide_path else None,
                }
            )
        )
        return

    print(f"✅ Created hostile demo dataset: {result.project_root}")
    print(f"   Injected {len(result.cases)} hostile cases across "
          f"{len(result.files_written)} domain(s)")
    if guide_path:
        print(f"   Guide written to: {guide_path}")
