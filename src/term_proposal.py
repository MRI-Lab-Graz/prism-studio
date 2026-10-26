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

MODALITY_NAME = r"[a-z][a-z0-9]*"  # a kind of data names a file (patches/<modality>.json), so nothing else is allowed

ISSUE_REPO = "MRI-Lab-Graz/prism-specification"
ISSUE_TEMPLATE = "propose-metric.yml"
ISSUE_NEW_KIND_TEMPLATE = "propose-new-kind-of-data.yml"
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
    term = res.term or {}
    if res.kind in ("term", "suggestion"):
        raise ProposalError(
            f"{column!r} is already an official metric ({term['TermID']}): "
            f'add "Term": "{term["TermID"]}" to the column instead of proposing it'
        )
    if res.kind == "specimen_mismatch":
        parent = term.get("Parent")
        hint = f"; to propose a term for this specimen point Term at {parent}" if parent else ""
        raise ProposalError(res.message + hint)
    if res.kind == "deprecated":
        raise ProposalError(res.message)
    if not col_def.get("Units"):
        raise ProposalError(f"column {column!r} has no Units; a proposal needs the unit")

    if res.kind == "known_analyte_new_specimen":
        parent_id, new_parent = term["TermID"], None
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


FORMAT_V2 = "prism-proposal/2"


def as_v2(proposal: dict) -> dict:
    """The document that is sent: prism-specification's proposal format v2 (repository path -> term).

    Studio builds proposals as {"modality", "terms"}; v2 names the files they add, which is what the bot
    copies and what has no limit of two terms. A v2 document is returned as it is.
    """
    if "files" in proposal:
        return proposal
    files = {
        f"terms/{proposal['modality']}/{term['TermID'].partition(':')[2]}.json": term for term in proposal["terms"]
    }
    if proposal.get("patch"):  # a schema addition: the same file the project keeps in code/specification/patches/
        files[f"patches/{proposal['modality']}.json"] = proposal["patch"]
    return {"format": FORMAT_V2, "files": files}


def _modality_of(document: dict) -> str:
    """The modality of a v2 document: its terms/<modality>/... or patches/<modality>.json paths."""
    first = next(iter(document["files"])).split("/")
    return first[1].removesuffix(".json")


def issue_url(proposal: dict, limit: int = URL_LIMIT, context: str | None = None) -> str | None:
    """Prefilled issue-form URL for a proposal (sent as format v2), or None when it would be longer than `limit`.

    `context` (optional) fills the form's Context field."""
    document = as_v2(proposal)
    terms = [t for path, t in document["files"].items() if path.startswith("terms/")]
    if terms:
        first = terms[0]
        analytes = {t["TermID"] if t.get("Level") == "analyte" else t.get("Parent") for t in terms}  # metrics, not files
        more = f" and {len(analytes) - 1} more" if len(analytes) > 1 else ""
        title = f"[Metric]: {first.get('Label') or first['TermID']}{more}"
    else:
        title = f"[Metric]: schema addition to {_modality_of(document)}"
    query = urlencode(
        {
            "template": ISSUE_TEMPLATE,
            "title": title,
            "proposal": json.dumps(document, separators=(",", ":"), ensure_ascii=False),
            **({"context": context} if context else {}),
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


def vendored_term_proposal():
    """prism-specification's own term_proposal.py (vendored in scripts/specification/), loaded by path."""
    spec = importlib.util.spec_from_file_location("specification_term_proposal", specification_scripts_dir() / "term_proposal.py")
    if spec is None or spec.loader is None:
        raise ImportError("prism-specification's term_proposal.py cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_with_specification(proposal: dict, registry: dict[str, dict], specimens: list[str] | None = None) -> list[str]:
    """Problems found by prism-specification's own checks (the vendored scripts/specification/term_proposal.py).

    `specimens` replaces the official SpecimenType values (a project's schema patch may add some)."""
    module = vendored_term_proposal()
    document = as_v2(proposal)  # a format-v1 proposal carries at most two terms; v2 up to 40
    stable = Path(DEFAULT_SCHEMA_DIR) / "stable"
    paths = list(document["files"])
    patched = {m for p in paths if (m := re.fullmatch(rf"patches/({MODALITY_NAME})\.json", p))}
    schemas = {m[1]: json.loads((stable / f"{m[1]}.schema.json").read_text(encoding="utf-8")) for m in patched}
    # the term modality (and so the specimen types) comes from the terms/<m>/ paths; a patch-only document has none
    term_modality = next((p.split("/")[1] for p in paths if p.startswith("terms/")), "biosample")
    from src.specification import current_specification  # local: specification imports spec_overlay imports this module

    modalities = current_specification().term_modalities
    if specimens is None and "contextField" in modalities.get(term_modality, {}):
        specimens = module.check_terms.specimen_types(stable / f"{term_modality}.schema.json")
    # a one-level modality (no contextField) gets specimens=None, never [] (that would apply two-level rules)
    problems = module.check_proposal(
        document, registry, specimens or None, schemas=schemas, modalities=modalities,
    )[1]
    # the form's size limit, on the indented text that is printed, shown and pasted (extract_proposal measures that)
    size = len(json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8"))
    if size > module.MAX_BYTES:
        problems.append(f"the proposal is {size} bytes, larger than the {module.MAX_BYTES} bytes the form takes: share fewer metrics at once")
    return problems


def deliver_proposal(proposal: dict, *, out=None, open_browser: bool = False, similar=None, alias=None, context: str | None = None) -> dict:
    """What `terms propose` and `spec propose` do with a finished proposal: optionally save it, optionally open
    the prefilled form, and describe it. Nothing is sent: opening the form is the user's browser, not an API call.

    What is saved, linked and shown is the document in proposal format v2 (`as_v2`).
    Returns {"saved": Path | None, "issue_url": str | None, "opened": bool, "text": str, "document": dict}.
    """
    document = as_v2(proposal)
    saved = None
    if out:
        saved = Path(out)
        saved.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    url = issue_url(proposal, context=context)
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
        if context:
            how += f"\nAnd this into the Context field:\n{context}"
    renaming = f'"{alias}"' if alias else "your column name"
    text = (
        "Proposal (nothing has been sent unless it says 'Opened' below):\n"
        + json.dumps(document, indent=2, ensure_ascii=False)
        + (
            f"\n\nSimilar official terms: {', '.join(similar) or 'none'} (check that none of them is what you mean)."
            if similar is not None else ""
        )
        + f"\nThe maintainers may choose a different ID or name; {renaming} is kept as an alias, so your files keep working."
        + (f"\nSaved to {saved} (send this file to a maintainer if you do not use GitHub)." if saved else "")
        + f"\n{how}"
    )
    return {"saved": saved, "issue_url": url, "opened": opened, "text": text, "document": document}
