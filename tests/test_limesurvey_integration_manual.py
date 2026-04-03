"""
Comprehensive integration test for all LimeSurvey flows.
Tests against running PRISM Studio instance (http://localhost:5001).

Run with: python tests/test_limesurvey_integration_manual.py
"""
import io
import json
import os
import sys
import tempfile

import requests

BASE = "http://localhost:5001"
PASS = 0
FAIL = 0
WARN = 0

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [OK] {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    global PASS, FAIL, WARN
    s = requests.Session()

    # Set project
    r = s.post(f"{BASE}/api/projects/current",
        json={"path": r"C:\Users\David\Nextcloud2\Documents\Data Steward\Abschlussprojekt\funfzehn"})
    if r.status_code != 200:
        print("FATAL: Could not set project")
        return

    # ── 1. SURVEY EXPORT (.lss generation) ───────────────────────
    section("1. Survey Export - Quick Export (.lss)")

    # Load library templates
    templates_to_test = [
        "official/library/survey/survey-gad7.json",
        "official/library/survey/survey-tipi.json",
        "official/library/survey/survey-dass21.json",
    ]

    for tpath in templates_to_test:
        name = os.path.basename(tpath)
        with open(tpath, "r", encoding="utf-8") as f:
            template = json.load(f)

        # Check template has items
        items = [k for k in template if k not in ("Study", "Technical", "Scoring",
                 "LimeSurvey", "Metadata", "MatrixGrouping", "TemplateVersion",
                 "_aliases", "_reverse_aliases")]
        if not items:
            warn(f"{name}: No items found in template (different format)")
            continue

        # Test Word export
        r = s.post(f"{BASE}/api/template-editor/export-questionnaire",
            json={"template": template, "language": "en", "options": {
                "show_participant_id": True, "header_repeat_every": 10}})
        if r.status_code == 200 and len(r.content) > 1000:
            ok(f"{name}: Word export OK ({len(r.content)} bytes)")
        else:
            fail(f"{name}: Word export failed ({r.status_code})")

        # Test Word export German
        r = s.post(f"{BASE}/api/template-editor/export-questionnaire",
            json={"template": template, "language": "de"})
        if r.status_code == 200:
            ok(f"{name}: Word export DE OK")
        else:
            fail(f"{name}: Word export DE failed")

    # ── 2. .LSS IMPORT ───────────────────────────────────────────
    section("2. LimeSurvey .lss Import")

    lss_files = [
        r"C:\Users\David\Downloads\limesurvey_survey_756459.lss",
    ]

    for lss_path in lss_files:
        if not os.path.exists(lss_path):
            warn(f"Skipping {os.path.basename(lss_path)} (not found)")
            continue

        name = os.path.basename(lss_path)

        # Import as combined
        with open(lss_path, "rb") as f:
            r = s.post(f"{BASE}/api/limesurvey-to-prism",
                files={"file": (name, f, "application/xml")},
                data={"mode": "combined"})
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                qcount = data.get("question_count", 0)
                ok(f"{name} combined: {qcount} questions imported")
            else:
                fail(f"{name} combined: success=false")
        else:
            fail(f"{name} combined: HTTP {r.status_code}")

        # Import as groups
        with open(lss_path, "rb") as f:
            r = s.post(f"{BASE}/api/limesurvey-to-prism",
                files={"file": (name, f, "application/xml")},
                data={"mode": "groups"})
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                gcount = data.get("questionnaire_count", 0)
                ok(f"{name} groups: {gcount} questionnaires")
            else:
                fail(f"{name} groups: success=false")
        else:
            fail(f"{name} groups: HTTP {r.status_code}")

    # ── 3. SURVEY EXPORT (.lss from library) ─────────────────────
    section("3. Survey Export - Generate .lss from Library")

    r = s.get(f"{BASE}/api/list-library-files")
    if r.status_code == 200:
        data = r.json()
        file_count = len(data.get("files", []))
        ok(f"Library listing: {file_count} files")
    else:
        fail(f"Library listing: HTTP {r.status_code}")

    # ── 4. SYSTEM VARIABLES DETECTION ────────────────────────────
    section("4. LimeSurvey System Variables Detection")

    sys.path.insert(0, "app")
    from src.converters.survey_processing import (
        _extract_limesurvey_columns,
        _is_limesurvey_system_column,
        LIMESURVEY_SYSTEM_COLUMNS,
    )

    # Test all documented system columns
    for col in sorted(LIMESURVEY_SYSTEM_COLUMNS):
        if _is_limesurvey_system_column(col):
            ok(f"Detects '{col}'")
        else:
            fail(f"Does NOT detect '{col}'")

    # Test timing patterns
    timing_cols = ["grouptime10", "grouptime999", "questiontime301",
                   "GroupTime42", "duration_total", "interviewtime"]
    for col in timing_cols:
        if _is_limesurvey_system_column(col):
            ok(f"Detects timing '{col}'")
        else:
            fail(f"Does NOT detect timing '{col}'")

    # Test false positives
    false_pos = ["PANAS01", "GAD701", "participant_id", "age", "Q1"]
    for col in false_pos:
        if not _is_limesurvey_system_column(col):
            ok(f"Correctly ignores '{col}'")
        else:
            fail(f"False positive: '{col}' detected as system column")

    # ── 5. TOOL-LIMESURVEY FILE WRITING ──────────────────────────
    section("5. Tool-LimeSurvey File Writing")

    import pandas as pd
    from src.converters.survey_io import _write_tool_limesurvey_files

    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path
        df = pd.DataFrame({
            "participant_id": ["sub-01", "sub-02", "sub-03"],
            "submitdate": ["2026-03-15 10:30:00", "2026-03-15 11:00:00", None],
            "startdate": ["2026-03-15 10:00:00", "2026-03-15 10:30:00", "2026-03-15 12:00:00"],
            "seed": ["42", "99", "77"],
            "token": ["abc", "def", "ghi"],
            "interviewtime": [1800, 900, 300],
            "grouptime10": [600, 400, 200],
            "completed": ["Y", "Y", "N"],
        })

        output_root = Path(tmpdir) / "out"
        output_root.mkdir()

        n = _write_tool_limesurvey_files(
            df=df,
            ls_system_cols=["submitdate", "startdate", "seed", "token",
                           "interviewtime", "grouptime10", "completed"],
            res_id_col="participant_id",
            res_ses_col=None,
            session="1",
            output_root=output_root,
            normalize_sub_fn=lambda x: str(x),
            normalize_ses_fn=lambda x: f"ses-{x}",
            ensure_dir_fn=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[-1],
            build_bids_survey_filename_fn=lambda *a, **kw: "dummy.tsv",
            ls_metadata={"survey_id": "999", "tool_version": "6.0.0", "survey_title": "Test"},
        )

        if n == 3:
            ok(f"Wrote {n} TSV files")
        else:
            fail(f"Expected 3 TSV files, got {n}")

        # Check sub-01
        sub01_dir = output_root / "sub-01" / "ses-1" / "survey"
        tsv_files = list(sub01_dir.glob("*tool-limesurvey*.tsv"))
        json_files = list(sub01_dir.glob("*tool-limesurvey*.json"))

        if tsv_files:
            ok("TSV file created for sub-01")
        else:
            fail("No TSV file for sub-01")

        if json_files:
            ok("JSON sidecar created for sub-01")
            with open(json_files[0], "r") as f:
                sidecar = json.load(f)
            if sidecar.get("Metadata", {}).get("ToolVersion") == "6.0.0":
                ok("JSON sidecar has correct ToolVersion")
            else:
                fail("JSON sidecar missing ToolVersion")
            if "Timings" in sidecar and "grouptime10" in sidecar["Timings"]:
                ok("JSON sidecar has Timings section with grouptime")
            else:
                fail("JSON sidecar missing Timings")
            if "DerivedFields" in sidecar:
                ok("JSON sidecar has DerivedFields")
            else:
                fail("JSON sidecar missing DerivedFields")
        else:
            fail("No JSON sidecar for sub-01")

        # Check incomplete response (sub-03)
        sub03_dir = output_root / "sub-03" / "ses-1" / "survey"
        tsv3 = list(sub03_dir.glob("*tool-limesurvey*.tsv"))
        if tsv3:
            import csv
            with open(tsv3[0], "r") as f:
                row = list(csv.DictReader(f, delimiter="\t"))[0]
            if row.get("CompletionStatus") == "incomplete":
                ok("Incomplete response correctly marked")
            else:
                fail(f"Expected 'incomplete', got '{row.get('CompletionStatus')}'")
            if row.get("submitdate") == "n/a":
                ok("Missing submitdate = 'n/a'")
            else:
                fail(f"Expected 'n/a' submitdate, got '{row.get('submitdate')}'")
        else:
            fail("No TSV for incomplete response sub-03")

    # ── 6. TEMPLATE PREVIEW ──────────────────────────────────────
    section("6. Template Editor Preview (API check)")

    with open("official/library/survey/survey-gad7.json", "r", encoding="utf-8") as f:
        gad7 = json.load(f)

    # Word export with various options
    for opts_name, opts in [
        ("default", {}),
        ("with PID", {"show_participant_id": True, "show_date_field": True}),
        ("randomized", {"randomize_items": True, "random_seed": 42}),
        ("compact font", {"font_size": 8, "item_column_pct": 60}),
        ("no codes", {"show_item_codes": False}),
    ]:
        r = s.post(f"{BASE}/api/template-editor/export-questionnaire",
            json={"template": gad7, "language": "en", "options": opts})
        if r.status_code == 200 and len(r.content) > 5000:
            ok(f"Word export '{opts_name}': {len(r.content)} bytes")
        else:
            fail(f"Word export '{opts_name}': {r.status_code}")

    # ── SUMMARY ──────────────────────────────────────────────────
    section("SUMMARY")
    total = PASS + FAIL + WARN
    print(f"  Passed: {PASS}")
    print(f"  Failed: {FAIL}")
    print(f"  Warnings: {WARN}")
    print(f"  Total: {total}")
    if FAIL == 0:
        print("\n  ALL TESTS PASSED")
    else:
        print(f"\n  {FAIL} TESTS FAILED")


if __name__ == "__main__":
    main()
