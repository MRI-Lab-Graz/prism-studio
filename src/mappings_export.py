"""The links of mappings/ as SSSOM (Simple Standard for Sharing Ontological Mappings), the form an outside reasoner reads.

`SameAs` becomes `skos:exactMatch`; a `Measures` entry becomes the SKOS match its `Match` names (`exact`, `broader`,
`narrower`, `related`; none given is `related`) with its `Source` as `author_label` and `Checked` as `mapping_date`.
`Status` and `Higher` have no SSSOM slot of their own and go to `comment`; no confidence number is invented from
`Status`. `ValueRules` and `Levels` are not links and are not exported. Nothing is read from disk but the list of
vocabularies; the mappings come from the caller (`Specification.mappings`).
"""

from __future__ import annotations

import json
import re

import yaml

from src.term_registry import mappings_root

SET_ID = "https://w3id.org/prism-specification/mappings"
NAMESPACE = "https://w3id.org/prism-specification/terms/"
JUSTIFICATION = "semapv:ManualMappingCuration"
PREDICATES = {"exact": "skos:exactMatch", "broader": "skos:broadMatch", "narrower": "skos:narrowMatch", "related": "skos:relatedMatch"}
COLUMNS = ("subject_id", "predicate_id", "object_id", "mapping_justification", "author_label", "mapping_date", "comment")


def _vocabulary_patterns() -> dict[str, re.Pattern]:
    try:
        data = json.loads((mappings_root() / "vocabularies.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: re.compile(v["pattern"]) for k, v in data.items() if isinstance(v, dict) and isinstance(v.get("pattern"), str)}


class _Prefixes:
    """CURIE prefixes handed out as the IDs and URLs come, so every CURIE of the table is in its curie_map."""

    def __init__(self) -> None:
        self.bases: dict[str, str] = {"semapv": "http://w3id.org/semapv/vocab/", "skos": "http://www.w3.org/2004/02/skos/core#"}
        self._patterns = _vocabulary_patterns()

    def curie(self, wanted: str, base: str, local: str) -> str:
        """`wanted` is the prefix; when it already names another base, `wanted_2`, `wanted_3`, ... name this one."""
        prefix, n = wanted, 1
        while self.bases.setdefault(prefix, base) != base:
            n += 1
            prefix = f"{wanted}_{n}"
        return f"{prefix}:{local}"

    def subject(self, modality: str, term_id: str) -> str:
        scheme, _, local = term_id.partition(":")
        if scheme == "local":
            return self.curie("local", "urn:prism-local:", local)
        return self.curie(f"prism_{re.sub(r'[^a-z0-9]+', '_', modality.lower())}", f"{NAMESPACE}{modality}/", local)

    def obj(self, url: str, vocabulary: str | None = None) -> str:
        vocabulary = vocabulary or next((k for k, p in self._patterns.items() if p.fullmatch(url)), "ext")
        base, _, local = url.rpartition("/")
        if not re.fullmatch(r"[\w.\-]+", local):  # nothing after the last "/", or "#", "?", ":": no valid CURIE; the full address stands
            return url
        return self.curie(vocabulary, f"{base}/", local)


def _cell(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _links(entry: dict):
    """(object URL, vocabulary hint or None, predicate, author, date, comment) of every link of one mapping entry."""
    same = entry.get("SameAs")
    for vocabulary, url in sorted(same.items()) if isinstance(same, dict) else ():
        if isinstance(url, str):
            yield url, vocabulary, PREDICATES["exact"], "", "", ""
    measures = entry.get("Measures")
    for m in measures if isinstance(measures, list) else ():
        if isinstance(m, dict) and isinstance(m.get("URL"), str):
            notes = [f"{k}: {m[k]}" for k in ("Status", "Higher") if isinstance(m.get(k), str) and m[k]]
            text = lambda key: m[key] if isinstance(m.get(key), str) else ""  # project data is untrusted: text only  # noqa: E731
            yield m["URL"], None, PREDICATES.get(m.get("Match"), PREDICATES["related"]), text("Source"), text("Checked"), "; ".join(notes)


def sssom_table(mappings: dict[str, dict[str, dict]]) -> str:
    """The SSSOM TSV (YAML header in `#` lines, then one row per link) of `mappings` ({modality: {ID: entry}})."""
    prefixes, rows = _Prefixes(), []
    for modality, entries in sorted(mappings.items()):
        for term_id, entry in sorted(entries.items()):
            subject = prefixes.subject(modality, term_id)
            for url, vocabulary, predicate, author, date, comment in _links(entry):
                rows.append((subject, predicate, prefixes.obj(url, vocabulary), JUSTIFICATION, author, date, comment))
    header = yaml.safe_dump({"mapping_set_id": SET_ID, "curie_map": dict(sorted(prefixes.bases.items()))}, sort_keys=False, allow_unicode=True)
    lines = ["#" + line for line in header.splitlines()]
    lines.append("\t".join(COLUMNS))
    lines += ["\t".join(_cell(c) for c in row) for row in rows]
    return "\n".join(lines) + "\n"
