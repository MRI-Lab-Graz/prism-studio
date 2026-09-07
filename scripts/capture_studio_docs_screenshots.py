#!/usr/bin/env python3
"""Regenerate the Studio Guide screenshots under docs/_static/screenshots/.

Requires PRISM Studio already running (``python prism-studio.py``, default
http://localhost:5001) and Playwright's Chromium browser installed
(``playwright install chromium``).

Usage:
    python scripts/capture_studio_docs_screenshots.py
    python scripts/capture_studio_docs_screenshots.py --base-url http://localhost:5001 \
        --project-path examples/wellbeing_multi_demo

Each entry in SHOTS below maps directly to a file already referenced by a
doc page under docs/ -- see that file's "docs/*.md" comment for where it's
used. Add a new entry (and update the matching .md) rather than repurposing
an existing filename.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "_static" / "screenshots"
DEFAULT_BASE_URL = "http://localhost:5001"
DEFAULT_PROJECT_PATH = REPO_ROOT / "examples" / "wellbeing_multi_demo"


def set_current_project(page: Page, base_url: str, path: str) -> None:
    page.request.post(f"{base_url}/api/projects/current", data={"path": path})


def clear_current_project(page: Page, base_url: str) -> None:
    set_current_project(page, base_url, "")


def shoot(page: Page, *filenames: str) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)  # let CSS transitions/spinners settle
    png = page.screenshot(full_page=True)
    for name in filenames:
        out_path = OUT_DIR / name
        out_path.write_bytes(png)
        print(f"  wrote {name} ({len(png) // 1024} KB)")


# --- no-project shots: the pre-project-creation flow (Chapter 1 / Quick Start) ---


def capture_no_project_shots(page: Page, base_url: str) -> None:
    print("\n[no project] home + landing")
    page.goto(f"{base_url}/")
    shoot(page, "prism-studio-home.png", "prism-studio-landing-create.png")

    print("[no project] projects page, cards collapsed")
    page.goto(f"{base_url}/projects")
    shoot(page, "prism-studio-project-newproject.png", "prism-studio-projects.png")

    print("[no project] Create New Project card expanded")
    page.click("#card-create")
    page.wait_for_selector("#section-create", state="visible")
    shoot(page, "prism-studio-projects-createInfo.png")

    print("[no project] Study Metadata card revealed")
    page.fill("#projectName", "demo_project")
    page.dispatch_event("#projectName", "input")
    page.wait_for_selector("#studyMetadataCard", state="visible", timeout=5000)
    page.click("#studyMetadataCard .card-header")
    page.wait_for_selector("#studyMetadataSection.show", state="visible")
    page.click("#smCoreSetupGroup button")
    page.wait_for_selector("#smCoreSetupGroupBody.show", state="visible")
    page.locator("#smBasics").scroll_into_view_if_needed()
    shoot(page, "prism-studio-project-metadata.png")


# --- project-loaded shots ---


def capture_converter_shots(page: Page, base_url: str) -> None:
    print("\n[project] converter tabs")
    page.goto(f"{base_url}/converter")
    shoot(page, "prism-studio-converter.png", "prism-studio-converter-participants.png")

    tabs = [
        ("survey-tab", "prism-studio-converter-survey.png"),
        ("biometrics-tab", "prism-studio-converter-biometrics.png"),
        ("physio-tab", "prism-studio-converter-physio.png"),
        ("eyetracking-tab", "prism-studio-converter-eyetracking.png"),
        ("environment-tab", "prism-studio-converter-environment.png"),
    ]
    for tab_id, filename in tabs:
        page.click(f"#{tab_id}")
        page.wait_for_timeout(300)
        shoot(page, filename)


def capture_validator_shots(page: Page, base_url: str) -> None:
    print("\n[project] validator start + results")
    page.goto(f"{base_url}/validate")
    shoot(page, "prism-studio-validator.png")

    page.click("#uploadBtn")
    page.wait_for_url("**/results/**", timeout=120_000)
    shoot(page, "prism-studio-validator-results.png")


SIMPLE_PROJECT_SHOTS = [
    ("/file-management", "prism-studio-file-management.png"),
    ("/recipe-builder", "prism-studio-recipe-builder.png"),
    ("/template-editor", "prism-studio-template-editor.png"),
    ("/editor/", "prism-studio-json-editor.png"),
    ("/projects/share", "prism-studio-export.png"),
    ("/prism-app-runner", "prism-studio-app-runner.png"),
    ("/specifications", "prism-studio-specifications.png"),
    ("/survey-generator", "prism-studio-survey-export.png"),
]


def capture_simple_project_shots(page: Page, base_url: str) -> None:
    print("\n[project] single-state pages")
    for route, filename in SIMPLE_PROJECT_SHOTS:
        page.goto(f"{base_url}{route}")
        shoot(page, filename)


def main() -> int:
    global OUT_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--project-path",
        default=str(DEFAULT_PROJECT_PATH),
        help="Existing PRISM project to load for the project-dependent shots.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(OUT_DIR),
        help="Where to write screenshots (default: docs/_static/screenshots).",
    )
    args = parser.parse_args()
    OUT_DIR = Path(args.out_dir)

    project_path = Path(args.project_path).expanduser().resolve()
    if not (project_path / "project.json").exists():
        print(f"error: {project_path} has no project.json -- not a PRISM project", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()

        try:
            page.goto(args.base_url, timeout=5000)
        except Exception:
            print(
                f"error: could not reach {args.base_url} -- start PRISM Studio first "
                "(`python prism-studio.py`)",
                file=sys.stderr,
            )
            return 1

        clear_current_project(page, args.base_url)
        capture_no_project_shots(page, args.base_url)

        set_current_project(page, args.base_url, str(project_path))
        capture_converter_shots(page, args.base_url)
        capture_validator_shots(page, args.base_url)
        capture_simple_project_shots(page, args.base_url)

        browser.close()

    print(f"\nDone. Screenshots written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
