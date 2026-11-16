"""Online lookups for prism_tools: `doi lookup` and `orcid search` (the template editor and project page call the same functions)."""

from __future__ import annotations

import json
import sys

from src.doi_lookup import lookup_doi


def cmd_doi_lookup(args) -> None:
    """Check a DOI (Crossref, then DataCite) and print the short citation."""
    result = lookup_doi(args.doi)
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False))
    elif result["status"] == "ok":
        print(result.get("citation") or result["doi"])
    else:
        print(f"{result['status']}: {result['doi']}")
    if result["status"] != "ok":
        sys.exit(1)
