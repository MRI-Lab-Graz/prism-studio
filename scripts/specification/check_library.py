"""Check every instrument template under library/survey/.

Usage: python scripts/check_library.py [--repo DIR]
Prints one line per problem (naming the file) and exits 1 when there is any.
Rules: (a) Study.License quotes the rights holder, (b) Study.Source is an absolute https URL,
(c) Study.LicenseChecked is YYYY-MM-DD, (d) Study.LicenseTerms is a list of short strings,
(e) only languages named in Study.LicenseLanguages, (e2) descriptive Study metadata (Description, Notes,
LicenseTerms, ...) is English (a quotation in quote marks of up to 300 characters may be in another language): other languages only in items, Levels, Instructions, OriginalName, bibliographic
data, the quoted Study.License evidence and the instruction and bibliographic sections of
ArchiveMetadata (ARCHIVE_TEXT_EXEMPT), (f) no Study.ItemCount, Study.Subscales or item Reversed, (g) bibliographic
completeness: Study.Authors is a non-empty list, Study.Year an integer and Study.Citation a real citation (not the
placeholder "Official webpage"), (h) no text-extraction artefacts in any string of a template: no Latin ligature
characters (U+FB00-FB06), soft hyphen (U+00AD) or zero-width characters (U+200B-U+200D, U+FEFF); the message names the
field and the code point. Normal umlauts, ss, quotes and the ellipsis are fine.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

TEXT_FIELDS = ("Description", "Levels", "Instructions", "OriginalName")
LANG = re.compile(r"[a-z]{2,3}")
LOOSE_LANG = re.compile(r"[A-Za-z]{2,3}")
NON_LANGUAGE_KEYS = {"min", "max"}  # AdministrationTime / ScoringTime / AgeRange
# Descriptive metadata of a template is English; only the instrument's own text (items, Levels, Instructions,
# OriginalName), bibliographic data and the quoted Study.License evidence may be in other languages.
ENGLISH_FIELDS = ("Description", "Construct", "Reliability", "Validity", "Norming", "Notes", "PermissionsNote",
                  "RecallPeriod", "Keywords", "LicenseTerms", "ArchiveMetadata", "AdministrationTime",
                  "ScoringTime", "AgeRange")
# Open Test Archive imports keep these ArchiveMetadata sections as quoted: the instruction to respondents and
# test administrators is instrument text (like Study.Instructions), the other three are bibliographic data (like
# Study.References). Keys are compared exactly; every other section, field or nested text stays English.
ARCHIVE_TEXT_EXEMPT = frozenset({"Durchführung/Instruktion", "Wichtige neuere Publikationen", "Rezensionen",
                                 "Orginalfassung/Anderssprachlige Fassungen"})
ENGLISH_ONLY = ("{}: text looks German; descriptive metadata must be English "
                "(items, instructions and the original name may be in another language)")
_DE = set("""der die das und nicht mit von zu den dem des ein eine einer eines ist sind wird werden wurde wurden auch
für auf im als bei oder wie sich aus nach über durch bis zur zum ich wir sie es er sein ihre ihr dass wenn aber
noch nur sehr mehr kann können hat haben fragebogen deren dieser diese dieses einem einen jedoch sowie wobei
zwischen unter gegen ohne sowohl weil dabei hier
erwachsene kinder jugendliche selbstbeurteilung fremdbeurteilung forschung praxis testleiter einsatz verfahren
dauer kostenlos verfügbar auswertung klinischen einzeln gruppe""".split())
_DE_WEAK = {"minuten", "stunden", "jahre", "jahren", "etwa", "ca"}  # German only counts next to a real German word
_EN = set("""the of and to in is are was were for with on as by that this these it its be or not from at which an a have
has had can may such than also between into their they we our been being but if when where who whose while each
both other more most only very over under after before through about""".split())
_DE, _EN = _DE - _EN, _EN - _DE
GERMAN_WORD = re.compile(r"[a-zäöüß]+")


SHORT_QUOTE = re.compile(r'"[^"]{0,300}"|„[^“”]{0,300}[“”]|“[^”]{0,300}”|‚[^‘’]{0,300}[‘’]')


def looks_german(text: str) -> bool:
    """Cheap heuristic: German function words (and umlauts) clearly outweigh English ones. Not a language detector.
    Quoted passages of at most 300 characters are quotations and are not counted; longer ones are."""
    text = SHORT_QUOTE.sub(" ", text)
    words = GERMAN_WORD.findall(text.lower())
    de = sum(w in _DE for w in words)
    de += de and sum(w in _DE_WEAK for w in words)
    en = sum(w in _EN for w in words)
    umlauts = sum(text.lower().count(c) for c in "äöüß")
    if len(words) <= 2:
        return de >= 1 and en == 0
    if len(words) < 25:
        return (de >= 2 and en == 0) or (de >= 3 and de >= 2 * en) or (umlauts >= 2 and de >= 1)
    return (de >= 3 and de > 1.5 * en) or (de >= 3 and de >= en and umlauts * 100 / len(words) >= 3)


def _strings(value, label):
    """Yield (label, text) for every string in value."""
    if isinstance(value, str):
        yield label, value
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v, label)
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, label)


ARTEFACTS = re.compile("[\ufb00-\ufb06\u00ad\u200b-\u200d\ufeff]")


def artefact_problems(value, path="") -> list[str]:
    """Rule (h): one line per string that holds a ligature, soft hyphen or zero-width character."""
    if isinstance(value, str):
        return [f"{path or '(template)'}: contains U+{ord(c):04X}, a text-extraction artefact; use the plain characters"
                for c in dict.fromkeys(ARTEFACTS.findall(value))]
    items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    return [line for k, v in items for line in artefact_problems(v, f"{path}.{k}" if path else str(k))]


def english_problems(study: dict) -> list[str]:
    """Descriptive Study metadata must be English, except the ARCHIVE_TEXT_EXEMPT sections of ArchiveMetadata."""
    out = []
    for field in ENGLISH_FIELDS:
        value, label = study.get(field), f"Study.{field}"
        if field == "ArchiveMetadata" and isinstance(value, dict) and isinstance(value.get("sections"), dict):
            value = {**value, "sections": {k: v for k, v in value["sections"].items() if k not in ARCHIVE_TEXT_EXEMPT}}
        if isinstance(value, dict) and field != "ArchiveMetadata":
            # an object form may only be {"en": ...}; {min, max} numbers are data
            for k, v in value.items():
                if k == "en":
                    out += [ENGLISH_ONLY.format(label) for _, t in _strings(v, label) if looks_german(t)]
                elif not (k in NON_LANGUAGE_KEYS and not isinstance(v, (dict, list))):
                    out.append(f"{label}: only an 'en' text is allowed, found {k!r}; descriptive metadata must be English")
        else:
            out += [ENGLISH_ONLY.format(label) for _, t in _strings(value, label) if looks_german(t)]
    return out


def _langs_skip(path, k):
    return path == "Study." and k in ENGLISH_FIELDS


NON_ITEMS = ("Technical", "Metadata", "I18n", "Study", "Normative")
QUOTE = re.compile(r'["“][^"”]{10,}["”]')


def _langs(value, path, allowed, out, level_map=False):
    """The root, each root-level block or item (keys are property names) is never a language object. Report language keys, in any dict below value with a lowercase 2-3 letter key, or only 2-3 letter keys (a pure {min, max} object is data, and a field like DOI among longer names is no language),, that are not allowed."""
    if isinstance(value, list):
        for i, v in enumerate(value):
            _langs(v, f"{path}{i}.", allowed, out)
    elif isinstance(value, dict):
        if value and not level_map and path.count(".") > 1 and not set(value) <= NON_LANGUAGE_KEYS and (
            any(LANG.fullmatch(k) for k in value) or all(LOOSE_LANG.fullmatch(k) for k in value)
        ):
            where = path.rstrip(".")
            for k in value:
                if not LOOSE_LANG.fullmatch(k):
                    out.append(f"{where}: mixed language object (key {k!r} next to language keys)")
                elif k != k.lower():
                    out.append(f"{where}: language key {k!r} must be lowercase")
                elif k not in allowed:
                    out.append(f"{where}: language {k!r} is not in Study.LicenseLanguages")
        for k, v in value.items():
            if not (path == "" and k in ("Technical", "I18n")) and not _langs_skip(path, k):
                # keys of a Levels map are level codes (a level 'no' is not a language)
                _langs(v, f"{path}{k}.", allowed, out, level_map=(k == "Levels"))


def template_problems(data: dict) -> list[str]:
    study = data.get("Study") or {}
    out = []
    lic = study.get("License")
    lic = " ".join(map(str, lic.values())) if isinstance(lic, dict) else lic
    if not (isinstance(lic, str) and QUOTE.search(lic)):
        out.append("Study.License must quote the rights holder's statement")
    src = study.get("Source")
    u = urlparse(src) if isinstance(src, str) else None
    if not (u and u.scheme == "https" and u.netloc):
        out.append("Study.Source must be an absolute https URL")
    checked = study.get("LicenseChecked")
    try:
        ok = isinstance(checked, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked)
        ok = ok and datetime.date.fromisoformat(checked)
    except ValueError:
        ok = False
    if not ok:
        out.append("Study.LicenseChecked must be a date YYYY-MM-DD")
    terms = study.get("LicenseTerms")
    if not (isinstance(terms, list) and terms and all(isinstance(t, str) and 0 < len(t) <= 300 for t in terms)):
        out.append("Study.LicenseTerms must be a non-empty list of short strings")
    langs = study.get("LicenseLanguages")
    if not (isinstance(langs, list) and langs and all(isinstance(x, str) and LANG.fullmatch(x) for x in langs)):
        out.append("Study.LicenseLanguages must be a non-empty list of language codes such as ['en']")
        langs = []
    tech = (data.get("Technical") or {}).get("Language")
    i18n = (data.get("I18n") or {}).get("Languages")
    if not isinstance(tech, str):
        out.append("Technical.Language must be set (a string)")
    if not isinstance(i18n, list):
        out.append("I18n.Languages must be set and must be a list")
    used = ([tech] if isinstance(tech, str) else []) + (i18n if isinstance(i18n, list) else [])
    out += [f"language {x!r} is not in Study.LicenseLanguages" for x in used if x not in langs]
    _langs(data, "", langs, out)
    out += english_problems(study)
    if not (isinstance(study.get("Authors"), list) and study["Authors"]):
        out.append("Study.Authors must be a non-empty list")
    year = study.get("Year")
    if not (isinstance(year, int) and not isinstance(year, bool)):
        out.append("Study.Year must be an integer")
    cit = study.get("Citation")
    if not (isinstance(cit, str) and cit.strip() and cit.strip().lower() != "official webpage"):
        out.append("Study.Citation must be a real citation, not empty or 'Official webpage'")
    for key in ("ItemCount", "Subscales"):
        if key in study:
            out.append(f"Study.{key} must not be set")
    out += [f"{k}.Reversed must not be set" for k, v in data.items()
            if k not in NON_ITEMS and isinstance(v, dict) and "Reversed" in v]
    return out + artefact_problems(data)


def check(repo: Path) -> list[str]:
    lines = []
    for f in sorted((Path(repo) / "library" / "survey").glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as exc:
            lines.append(f"{f.name}: not valid JSON ({exc})")
            continue
        lines += [f"{f.name}: {p}" for p in template_problems(data)]
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    lines = check(Path(ap.parse_args(argv).repo))
    print("\n".join(lines))
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
