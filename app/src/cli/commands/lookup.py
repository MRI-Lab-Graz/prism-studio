"""Online lookups for prism_tools: `doi lookup` and `orcid search` (the template editor and project page call the same functions)."""

from __future__ import annotations

import json
import sys

from src.doi_lookup import lookup_doi
from src.orcid_lookup import orcid_search_response


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


def cmd_orcid_search(args) -> None:
    """Search ORCID iDs by name; several hits are listed, never picked."""
    payload, status = orcid_search_response(args.given_names, args.family_name, args.limit, args.current_orcid)
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False))
    elif payload["success"]:
        for c in payload["candidates"]:
            print(f"{c['orcid_id']}\t{c.get('display_name', '')}\t{c.get('affiliation', '')}")
    else:
        print(f"Error: {payload['error']}", file=sys.stderr)
    if status != 200:
        sys.exit(1)
