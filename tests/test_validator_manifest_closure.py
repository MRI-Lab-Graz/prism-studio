"""Every local module the validator wheel's files import (lazy imports included)
must itself be in scripts/validator_manifest.txt, or be allowlisted with a reason."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWLIST = {
    "app/src/project_manager.py": "Studio-only; runner._validate_citation_cff imports it in try/except "
    "(known gap: wheel emits a bogus PRISM303 warning for datasets with CITATION.cff)",
    "src/anonymizer.py": "export path, never reached by the validator",
    "src/participants_converter.py": "needs pandas; the import in subject_id_matching is guarded by try/except, and it is also "
    "loaded by importlib.import_module STRING imports (runner._check_participants_subject_alignment, "
    "participants_mapping) that this AST test cannot see, so in the wheel the strict --bids "
    "participants alignment check and auto-applied mapping silently do nothing (known gap)",
}


# Note: __init__.py files are not checked (packages are staged via the manifest's own entries).
def _candidates(mod, level, importer):
    parts = mod.split(".") if mod else []
    roots = []
    if level:
        base = importer.parent
        for _ in range(level - 1):
            base = base.parent
        roots = [base]
    else:  # validator sys.path: app/, app/src (bare imports), repo root
        roots = [ROOT / "app", ROOT / "app" / "src", ROOT]
    outs = []
    for r in roots:
        cand = r.joinpath(*parts)
        outs += [cand.with_suffix(".py"), cand / "__init__.py"]
    return [c for c in outs if c.exists()]


def _missing():
    manifest = set((ROOT / "scripts/validator_manifest.txt").read_text().split())
    missing = {}
    for rel in sorted(manifest):
        p = ROOT / rel
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                items = [(a.name, 0, []) for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                items = [(n.module or "", n.level, [a.name for a in n.names])]
            else:
                continue
            for mod, level, sub in items:
                targets = _candidates(mod, level, p)
                for s in sub:
                    targets += _candidates(f"{mod}.{s}" if mod else s, level, p)
                for t in targets:
                    tr = t.relative_to(ROOT).as_posix()
                    if tr not in manifest and not tr.endswith("__init__.py"):
                        missing.setdefault(tr, set()).add(rel)
    return missing


def test_manifest_covers_every_local_import():
    missing = {m: w for m, w in _missing().items() if m not in ALLOWLIST}
    assert not missing, {m: sorted(w) for m, w in missing.items()}
