"""Which IDs have a link to an outside vocabulary (`SameAs` or `Measures`), and which have none yet.

An ID is *direct* when its own mapping entry holds a link, *inherited* when only its parent's does (as `term_links`
and `term_meaning` read it), else *none*. `ValueRules` and `Levels` are not links. The caller supplies the
registries and the lookup (`Specification.mappings_for`), so a project's own terms and links count when it passes them.
"""

from __future__ import annotations

from typing import Callable


def _linked(entry: dict) -> bool:
    return bool(entry.get("SameAs")) or bool(entry.get("Measures"))


def coverage(registries: dict[str, dict[str, dict]], mappings_for: Callable[[str], dict]) -> dict[str, dict]:
    """{modality: {total, direct, inherited, none, missing}}; `missing` is the sorted IDs that have no link at all."""
    result = {}
    for modality, registry in registries.items():
        direct = inherited = 0
        missing = []
        for term in registry.values():
            term_id = term.get("TermID")
            if _linked(mappings_for(term_id)):
                direct += 1
            elif isinstance(term.get("Parent"), str) and _linked(mappings_for(term["Parent"])):
                inherited += 1
            else:
                missing.append(term_id)
        result[modality] = {"total": len(registry), "direct": direct, "inherited": inherited, "none": len(missing),
                            "missing": sorted(missing)}
    return result
