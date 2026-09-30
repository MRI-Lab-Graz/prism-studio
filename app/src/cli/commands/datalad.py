"""datalad doctor / keygen prism_tools command handlers (thin adapters over src.datalad_doctor)."""

from __future__ import annotations

import json
import sys

from src.datalad_doctor import run_doctor


def _server_url(args):
    if getattr(args, "url", None):
        return args.url
    project = getattr(args, "project", None)
    if project:
        from src.config import load_config

        return load_config(str(project)).datalad_ria_store_url
    return None


def cmd_datalad_doctor(args) -> None:
    results = run_doctor(_server_url(args))
    if getattr(args, "json", False):
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"[{'ok' if r['ok'] else 'FAIL'}] {r['name']}: {r['detail']}")
            if not r["ok"] and r["fix"]:
                print(f"       -> {r['fix']}")
    if not all(r["ok"] for r in results):
        sys.exit(1)

