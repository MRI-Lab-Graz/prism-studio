"""Turn a sidecar column into a proposal for the term registry (`prism_tools.py terms propose`).

The proposal format and its checks live in the prism-specification repository
(scripts/term_proposal.py, vendored in scripts/specification/); this module only builds the
document from a column and the prefilled issue-form URL. Nothing here sends anything.
Spec: docs/superpowers/specs/2026-10-23-metric-proposal-design.md
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlencode

from src.term_registry import resolve_column

ISSUE_REPO = "MRI-Lab-Graz/prism-specification"
ISSUE_TEMPLATE = "propose-metric.yml"
URL_LIMIT = 6000
_OPTIONAL_CHILD_FIELDS = ("MinValue", "WarnMaxValue", "LOINC")


class ProposalError(ValueError):
    """The column cannot be proposed; the message says why and what to do instead."""


def slugify(text: str) -> str:
    """Lowercase ID slug: runs of anything but a-z0-9 become `-`; must start with a letter."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if not re.match(r"[a-z]", slug):
        raise ProposalError(f"cannot make an ID from {text!r} (it must start with a letter); pass --label")
    return slug


def build_proposal(
    registry: dict[str, dict],
    sidecar: dict,
    column: str,
    label: str | None = None,
    modality: str = "biosample",
) -> dict:
    col_def = sidecar.get(column)
    if not isinstance(col_def, dict):
        raise ProposalError(f"column {column!r} not found in the sidecar (or it is not a column definition)")
    technical = sidecar.get("Technical")
    specimen = technical.get("SpecimenType") if isinstance(technical, dict) else None
    if not specimen:
        raise ProposalError("the sidecar has no Technical.SpecimenType")

    res = resolve_column(registry, column, col_def, specimen)
    if res.kind in ("term", "suggestion"):
        raise ProposalError(
            f"{column!r} is already an official metric ({res.term['TermID']}): "
            f'add "Term": "{res.term["TermID"]}" to the column instead of proposing it'
        )
    if res.kind in ("deprecated", "specimen_mismatch"):
        raise ProposalError(res.message)
    if not col_def.get("Units"):
        raise ProposalError(f"column {column!r} has no Units; a proposal needs the unit")

    if res.kind == "known_analyte_new_specimen":
        parent_id, new_parent = res.term["TermID"], None
    else:  # unknown analyte: propose the analyte and its specimen-specific term
        name = label or column
        parent_id = f"prism:{slugify(name)}"
        description = col_def.get("Description")
        new_parent = {
            "TermID": parent_id, "Level": "analyte", "Label": name, "Aliases": [column],
            "Description": description if isinstance(description, str) else name,
        }
    child = {
        "TermID": f"{parent_id}.{specimen}", "Level": "analyte-specimen", "Parent": parent_id,
        "SpecimenType": specimen, "Units": col_def["Units"],
    }
    child.update({f: col_def[f] for f in _OPTIONAL_CHILD_FIELDS if col_def.get(f) is not None})
    return {"modality": modality, "terms": ([new_parent] if new_parent else []) + [child]}


def issue_url(proposal: dict, repo: str = ISSUE_REPO, limit: int = URL_LIMIT) -> str | None:
    """Prefilled issue-form URL, or None when it would be longer than `limit` characters."""
    first = proposal["terms"][0]
    query = urlencode(
        {
            "template": ISSUE_TEMPLATE,
            "title": f"[Metric]: {first.get('Label') or first['TermID']}",
            "proposal": json.dumps(proposal, separators=(",", ":"), ensure_ascii=False),
        },
        quote_via=quote,
    )
    url = f"https://github.com/{repo}/issues/new?{query}"
    return url if len(url) <= limit else None
