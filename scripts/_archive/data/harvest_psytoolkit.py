#!/usr/bin/env python3
"""
Harvest surveys from PsyToolkit survey library and convert to PRISM format.

This script fetches psychological questionnaires from psytoolkit.org and
converts them into PRISM's bilingual JSON schema format.

Usage:
    python scripts/data/harvest_psytoolkit.py --all
    python scripts/data/harvest_psytoolkit.py --survey phq9 gad7
    python scripts/data/harvest_psytoolkit.py --list
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Required packages not installed.")
    print("Run: pip install requests beautifulsoup4")
    sys.exit(1)


# Survey mapping: URL slug -> PRISM identifier
# URLs follow pattern: https://www.psytoolkit.org/survey-library/{slug}.html
# Scraped from https://www.psytoolkit.org/survey-library/ on 2026-01-20
PSYTOOLKIT_SURVEYS = {
    "big5-tipi": "tipi",
    "big5-bfi-s": "bfi-s",
    "zkpq-50-cc": "zkpq",
    "personality-d": "type-d",
    "maslow": "maslow",
    "ccms-conscientiousness": "ccms",
    "emotional-intelligence": "ei",
    "emotional-regulation-erq": "erq",
    "empathy-arc": "eq",
    "systemizing-arc": "sq",
    "panas": "panas",
    "spane": "spane",
    "humor-hsq": "hsq",
    "happiness-shs": "shs",
    "happiness-ohq": "ohq",
    "satisfaction-with-life": "swls",
    "gratitude-gq6": "gq6",
    "aggression-buss-perry": "bpaq",
    "love-satisfaction-swlls": "swlls",
    "jealousy-sf-mjs": "sf-mjs",
    "attachment-saam": "saam",
    "risk-rps": "rps",
    "relationship-satisfaction-pnsmd": "pnsmd",
    "flourishing-scale": "fs",
    "pts": "pts",
    "pmi": "pmi",
    "trust": "trust",
    "stress-pss": "pss",
    "vams-mood-scales": "vams",
    "short-autism-spectrum-quotient": "aq10",
    "asrs": "asrs",
    "depression-cudos": "cudos",
    "depression-phq": "phq9",
    "mhc-sf": "mhc-sf",
    "appearance-aai": "aai",
    "anxiety-gad7": "gad7",
    "depression-anxiety-stress-dass": "dass",
    "dass21": "dass21",
    "math-anxiety-amas": "amas",
    "tai5": "tai5",
    "spider-fear-fsq": "fsq",
    "spider-fear-spq": "spq",
    "nmp-q": "nmp-q",
    "anger-cas": "cas",
    "schizotypy-short-olife": "o-life",
    "hypoglycemia-hsc7": "hsc7",
    "paranoia-gpts": "gtps",
    "eating-cia": "cia",
    "dyslexia-bda": "dyslexia",
    "procrastination-gp": "gp",
    "procrastination-pci": "pci",
    "addiction-bergen-facebook": "bfas",
    "obsessiveness-oci-r": "oci-r",
    "webexec": "webexec",
    "irritability-bite": "bite",
    "loneliness-tils": "loneliness-3",
    "loneliness-uplas": "uplas",
    "social-media-disorder-scale": "smd",
    "who5": "who5",
    "caffeine-cudq": "cudq",
    "addiction-internet-piu": "piu",
    "addiction-internet-piuq": "piuq",
    "narcism-npi16": "npi-16",
    "narcism-hsns": "hsns",
    "psychopathy-lsrps": "lsrp",
    "histrionic-bhps": "bhps",
    "scrupulosity-pios": "pios",
    "short-dark-triad": "sd3",
    "vast": "vast",
    "everyday-lying": "lies",
    "bfs": "bfs",
    "flexibility-cfs": "cfs",
    "evolution-gaene": "gaene",
    "evolution-mate": "mate",
    "supernatural-sbs": "sbs-10",
    "skepticism-skep": "skep",
    "social-intelligence-tsis": "tsis",
    "need-for-cognition-ncs6": "ncs-6",
    "single-item-sleep-quality-scale": "sqs",
    "chronotype-cirens": "cirens",
    "lseq": "lseq",
    "gsqs": "gsqs",
    "handedness-ehi": "ehi",
    "sex-role-bem": "bsri",
    "hypermasculinity-shvq": "shvq",
    "hypermasculinity-hvq": "hvq",
    "connectedness-nature": "cns",
    "love-styles-hendrick-sf": "las",
    "sexual-attitudes-scale-bsas": "bsas",
    "sensation-seeking-aiss": "aiss",
    "rumination": "rrs",
    "thinking-style-rei": "rei",
    "impulsiveness-barratt": "bis",
    "self-esteem-rosenberg": "rosenberg",
    "self-esteem-sses": "sses",
    "resilience-brcs": "brcs",
    "resilience-brs": "brs",
    "political-conservatism": "conservatism",
    "optimism-lotr": "lot-r",
    "generalized-self-efficacy-gse": "gse",
    "dominance-ard": "ard",
    "shyness-mcss": "shyness",
    "self-consciousness-scale-scsr": "scsr",
    "perfectionism-saps": "saps",
    "locus-of-control-rotter": "locus",
    "spheres-of-control-scale": "soc-3",
    "body-esteem-bes": "bes",
    "coop-comp-ccss": "ccss",
    "nurturant-fathering": "nfs",
    "grit-short": "grit-s",
    "healthy-selfishness": "hs",
    "critical-social-justice-scale": "csjas",
    "bes": "bes-alt",
    "masi": "masi",
    "teacher-burnout": "burnout",
    "depression-epds": "epds",
    "alcohol-sobriety-sos": "sos",
    "dsmqr": "dsmqr",
    "children-happiness": "chs",
    "aggression-adolescents": "agg-a",
    "alcohol-dmq-r": "dmq-r",
    "addiction-gaming-gas": "gas",
    "impulsiveness-isc": "isc",
    "cabs": "cabs",
}

BASE_URL = "https://www.psytoolkit.org/survey-library/"


class PsyToolkitHarvester:
    """Harvests and converts PsyToolkit surveys to PRISM format."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_survey_page(self, slug: str) -> Optional[str]:
        """Fetch the HTML content of a survey page."""
        url = urljoin(BASE_URL, f"{slug}.html")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"✗ Failed to fetch {slug}: {e}")
            return None

    def parse_survey_code(self, html: str) -> Optional[Dict]:
        """Extract survey items from PsyToolkit code block."""
        soup = BeautifulSoup(html, "html.parser")

        # Find the code block
        code_block = soup.find("pre") or soup.find("code")
        if not code_block:
            return None

        code = code_block.get_text()

        # Parse scale definition
        scale_match = re.search(r"scale:\s*(\w+)\s*\n((?:-.+\n)+)", code)
        if not scale_match:
            return None

        scale_name = scale_match.group(1)
        levels_text = scale_match.group(2)
        levels = [
            line.strip("- ").strip()
            for line in levels_text.split("\n")
            if line.strip().startswith("-")
        ]

        # Parse items
        items_match = re.search(r"q:(.+?)(?:\n\n|\nl:|$)", code, re.DOTALL)
        if not items_match:
            return None

        items_text = items_match.group(1)
        items = []

        # Extract individual items
        for line in items_text.split("\n"):
            line = line.strip()
            if line.startswith("-") and not line.startswith("- {"):
                item_text = line.strip("- ").strip()
                is_reversed = "{reverse}" in item_text
                item_text = re.sub(r"\{reverse\}\s*", "", item_text)
                items.append({"text": item_text, "reversed": is_reversed})

        return {"scale_name": scale_name, "levels": levels, "items": items}

    def extract_metadata(self, html: str, slug: str) -> Dict:
        """Extract metadata from the survey page."""
        soup = BeautifulSoup(html, "html.parser")

        metadata = {
            "slug": slug,
            "title": "",
            "authors": [],
            "year": None,
            "doi": "",
            "citation": "",
            "description": "",
        }

        # Extract title
        h1 = soup.find("h1")
        if h1:
            metadata["title"] = h1.get_text().strip()

        # Extract references section
        refs_section = soup.find("h2", string=re.compile("References?"))
        if refs_section:
            refs_list = refs_section.find_next("ul")
            if refs_list:
                first_ref = refs_list.find("li")
                if first_ref:
                    ref_text = first_ref.get_text()
                    metadata["citation"] = ref_text.strip()

                    # Extract authors (before year in parentheses)
                    authors_match = re.match(r"^([^(]+)\((\d{4})\)", ref_text)
                    if authors_match:
                        authors_str = authors_match.group(1).strip()
                        metadata["authors"] = [
                            a.strip().rstrip(".") for a in authors_str.split(",")
                        ]
                        metadata["year"] = int(authors_match.group(2))

                    # Extract DOI
                    doi_match = re.search(r"doi\.org/(10\.\S+)", ref_text)
                    if doi_match:
                        metadata["doi"] = f"https://doi.org/{doi_match.group(1)}"

        return metadata

    def convert_to_prism(
        self, survey_data: Dict, metadata: Dict, prism_id: str
    ) -> Dict:
        """Convert parsed survey to PRISM bilingual JSON format."""

        prism_survey = {
            "Study": {
                "OriginalName": {
                    "en": metadata["title"],
                    "de": metadata["title"],  # TODO: Add German translations
                },
                "Abbreviation": prism_id.upper(),
                "Authors": metadata["authors"],
                "Year": metadata["year"],
                "DOI": metadata["doi"],
                "Citation": metadata["citation"],
                "NumberOfItems": len(survey_data["items"]),
                "License": {
                    "en": "Freely available for research purposes (verify with original publication)",
                    "de": "Frei verfügbar für Forschungszwecke (mit Originalpublikation überprüfen)",
                },
                "Source": f"https://www.psytoolkit.org/survey-library/{metadata['slug']}.html",
                "Instructions": {
                    "en": "Please read each statement and select the response that best describes you.",
                    "de": "Bitte lesen Sie jede Aussage und wählen Sie die Antwort, die Sie am besten beschreibt.",
                },
            }
        }

        # Add items
        for idx, item in enumerate(survey_data["items"], start=1):
            item_id = f"{prism_id.upper()}{idx:02d}"

            # Create levels dict
            levels = {}
            for level_idx, level_text in enumerate(survey_data["levels"]):
                levels[str(level_idx)] = {
                    "en": level_text,
                    "de": level_text,  # TODO: Add German translations
                }

            prism_survey[item_id] = {
                "Description": {
                    "en": item["text"],
                    "de": item["text"],  # TODO: Add German translations
                },
                "Reversed": item["reversed"],
                "Levels": levels,
            }

        return prism_survey

    def harvest_survey(self, slug: str, prism_id: str) -> bool:
        """Harvest a single survey and save to PRISM format."""
        print(f"Harvesting {slug} → {prism_id}...", end=" ")

        # Fetch page
        html = self.fetch_survey_page(slug)
        if not html:
            return False

        # Parse survey code
        survey_data = self.parse_survey_code(html)
        if not survey_data:
            print("✗ Failed to parse survey code")
            return False

        # Extract metadata
        metadata = self.extract_metadata(html, slug)

        # Convert to PRISM format
        prism_survey = self.convert_to_prism(survey_data, metadata, prism_id)

        # Save to file
        output_file = self.output_dir / f"survey-{prism_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(prism_survey, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved to {output_file.name}")
        return True

    def harvest_all(self):
        """Harvest all surveys in the mapping."""
        success_count = 0
        fail_count = 0

        print(f"\nHarvesting {len(PSYTOOLKIT_SURVEYS)} surveys from PsyToolkit...\n")

        for slug, prism_id in PSYTOOLKIT_SURVEYS.items():
            if self.harvest_survey(slug, prism_id):
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'=' * 60}")
        print(f"Harvest complete: {success_count} successful, {fail_count} failed")
        print(f"Output directory: {self.output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Harvest surveys from PsyToolkit and convert to PRISM format"
    )
    parser.add_argument("--all", action="store_true", help="Harvest all surveys")
    parser.add_argument(
        "--survey",
        nargs="+",
        help="Harvest specific surveys by PRISM ID (e.g., phq9 gad7)",
    )
    parser.add_argument(
        "--list", action="store_true", help="List all available surveys"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "official" / "library" / "survey",
        help="Output directory for harvested surveys",
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable surveys:")
        print("=" * 60)
        for slug, prism_id in sorted(PSYTOOLKIT_SURVEYS.items()):
            print(f"  {prism_id:20s} → {slug}")
        print(f"\nTotal: {len(PSYTOOLKIT_SURVEYS)} surveys")
        return

    harvester = PsyToolkitHarvester(args.output)

    if args.all:
        harvester.harvest_all()
    elif args.survey:
        # Find surveys by PRISM ID
        for prism_id in args.survey:
            prism_id = prism_id.lower()
            # Find corresponding slug
            slug = None
            for s, p in PSYTOOLKIT_SURVEYS.items():
                if p == prism_id:
                    slug = s
                    break

            if slug:
                harvester.harvest_survey(slug, prism_id)
            else:
                print(
                    f"✗ Survey '{prism_id}' not found. Use --list to see available surveys."
                )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
