"""Turn a sidecar column into a proposal for the term registry (`prism_tools.py terms propose`).

The proposal format and its checks live in the prism-specification repository
(scripts/term_proposal.py, vendored in scripts/specification/); this module only builds the
document from a column and the prefilled issue-form URL. Nothing here sends anything.
Spec: docs/superpowers/specs/2026-10-23-metric-proposal-design.md
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlencode

from src.schema_manager import DEFAULT_SCHEMA_DIR
from src.term_registry import resolve_column

ISSUE_REPO = "MRI-Lab-Graz/prism-specification"
ISSUE_TEMPLATE = "propose-metric.yml"
URL_LIMIT = 6000
_OPTIONAL_CHILD_FIELDS = ("MinValue", "WarnMaxValue", "LOINC")


class ProposalError(ValueError):
    """The column cannot be proposed; the message says why and what to do instead."""


def slugify(text: str) -> str:
    """Lowercase ID slug: runs of anything but a-z0-9 become `-`; must start with a letter."""
    if any(ch.isalpha() and not ch.isascii() for ch in str(text)):  # dropping letters would make IL-1α and IL-1β collide
        raise ProposalError(f"cannot make an ASCII ID from {text!r}; pass --label with an ASCII name")
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if not re.match(r"[a-z]", slug):
        raise ProposalError(f"cannot make an ID from {text!r} (it must start with a letter); pass --label")
    return slug


def load_inherited_sidecar(data_file) -> tuple[dict, str]:
    """The sidecar of a data file with BIDS inheritance (root-level merged with subject-level), as the validator reads it."""
    from src.validator import _default_load_sidecar_json, _resolve_inherited_sidecar_core  # lazy: the validator is heavy

    data_file = Path(data_file).resolve()
    root = next((p for p in data_file.parents if (p / "dataset_description.json").is_file()), data_file.parent)
    sidecar, path = _resolve_inherited_sidecar_core(str(data_file), str(root), None, _default_load_sidecar_json)
    if not isinstance(sidecar, dict):
        raise ProposalError(f"no sidecar found for {data_file} (looked for the subject-level and the root-level sidecar)")
    return sidecar, path


def _dangling_slug(col_def: dict) -> str | None:
    """Local name of a `Term` the column already uses that the registry does not know yet (prism:zonulin -> zonulin)."""
    ref = col_def.get("Term")
    if not isinstance(ref, str) or not ref.strip():
        return None
    local = ref.partition(":")[2] if ref.startswith("prism:") else ref
    return local.split(".")[0] or None


def build_proposal(
    registry: dict[str, dict],
    sidecar: dict,
    column: str,
    label: str | None = None,
    modality: str = "biosample",
) -> dict:
    col_def = sidecar.get(column)
    if not isinstance(col_def, dict):
        raise ProposalError(
            f"column {column!r} not found in the sidecar (or it is not a column definition); "
            "if it is defined in the root-level sidecar of the project, use --data with a data file of the project (its inherited sidecar is read) or pass the root-level sidecar"
        )
    technical = sidecar.get("Technical")
    specimen = technical.get("SpecimenType") if isinstance(technical, dict) else None
    if not specimen:
        raise ProposalError(
            "the sidecar has no Technical.SpecimenType; use --data with a data file of the project (its inherited "
            "sidecar is read) or pass the sidecar that defines it (usually the root-level one)"
        )

    res = resolve_column(registry, column, col_def, specimen)
    if res.kind in ("term", "suggestion"):
        raise ProposalError(
            f"{column!r} is already an official metric ({res.term['TermID']}): "
            f'add "Term": "{res.term["TermID"]}" to the column instead of proposing it'
        )
    if res.kind == "specimen_mismatch":
        parent = res.term.get("Parent")
        hint = f"; to propose a term for this specimen point Term at {parent}" if parent else ""
        raise ProposalError(res.message + hint)
    if res.kind == "deprecated":
        raise ProposalError(res.message)
    if not col_def.get("Units"):
        raise ProposalError(f"column {column!r} has no Units; a proposal needs the unit")

    if res.kind == "known_analyte_new_specimen":
        parent_id, new_parent = res.term["TermID"], None
    else:  # unknown analyte: propose the analyte and its specimen-specific term
        name = label or column
        # a Term the column already carries decides the ID, otherwise the files would not resolve after the merge
        parent_id = f"prism:{slugify(label or _dangling_slug(col_def) or column)}"
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


def issue_url(proposal: dict, limit: int = URL_LIMIT) -> str | None:
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
    url = f"https://github.com/{ISSUE_REPO}/issues/new?{query}"
    return url if len(url) <= limit else None


def specification_scripts_dir() -> Path:
    """`scripts/specification` in a checkout and in the frozen build (bundled at `<_MEIPASS>/scripts`)."""
    candidates = [Path(__file__).resolve().parents[1] / "scripts" / "specification"]
    meipass = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    if meipass:
        candidates.append(Path(meipass).resolve() / "scripts" / "specification")
    return next((c for c in candidates if c.is_dir()), candidates[0])


def check_with_specification(proposal: dict, registry: dict[str, dict]) -> list[str]:
    """Problems found by prism-specification's own checks (the vendored scripts/specification/term_proposal.py)."""
    spec = importlib.util.spec_from_file_location("specification_term_proposal", specification_scripts_dir() / "term_proposal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = Path(DEFAULT_SCHEMA_DIR) / "stable" / f"{proposal['modality']}.schema.json"
    return module.check_proposal(proposal, registry, module.check_terms.specimen_types(schema))[1]


def deliver_proposal(proposal: dict, *, out=None, open_browser: bool = False, similar=None, alias=None) -> dict:
    """What `terms propose` and `spec propose` do with a finished proposal: optionally save it, optionally open
    the prefilled form, and describe it. Nothing is sent: opening the form is the user's browser, not an API call.

    Returns {"saved": Path | None, "issue_url": str | None, "opened": bool, "text": str}.
    """
    saved = None
    if out:
        saved = Path(out)
        saved.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    url = issue_url(proposal)
    opened = bool(open_browser and url and webbrowser.open(url))
    if opened:
        how = f"Opened the prefilled form in your browser:\n{url}"
    elif open_browser and url:
        how = f"Could not open a browser; open this address yourself:\n{url}"
    elif url:
        how = f"To send it, run this again with --open (it opens the prefilled form):\n{url}"
    else:
        form = f"https://github.com/{ISSUE_REPO}/issues/new?template={ISSUE_TEMPLATE}"
        how = f"The proposal is too long for a link: open {form} and paste the proposal above into the field."
    renaming = f'"{alias}"' if alias else "your column name"
    text = (
        "Proposal (nothing has been sent unless it says 'Opened' below):\n"
        + json.dumps(proposal, indent=2, ensure_ascii=False)
        + (
            f"\n\nSimilar official terms: {', '.join(similar) or 'none'} (check that none of them is what you mean)."
            if similar is not None else ""
        )
        + f"\nThe maintainers may choose a different ID or name; {renaming} is kept as an alias, so your files keep working."
        + (f"\nSaved to {saved} (send this file to a maintainer if you do not use GitHub)." if saved else "")
        + f"\n{how}"
    )
    return {"saved": saved, "issue_url": url, "opened": opened, "text": text}
