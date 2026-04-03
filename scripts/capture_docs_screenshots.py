"""
Capture documentation screenshots for PRISM Studio LimeSurvey integration.

Requirements: pip install playwright && python -m playwright install chromium
Usage: python scripts/capture_docs_screenshots.py

Assumes PRISM Studio is running on http://localhost:5001
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5001"
OUT = Path("docs/img/limesurvey")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # Set project via API
        page.goto(f"{BASE}/")
        page.evaluate("""
            fetch('/api/projects/current', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: 'C:\\\\Users\\\\David\\\\Nextcloud2\\\\Documents\\\\Data Steward\\\\Abschlussprojekt\\\\funfzehn'})
            })
        """)
        time.sleep(1)

        # ── 1. Survey Export page ─────────────────────────────────
        print("1. Survey Export page...")
        page.goto(f"{BASE}/survey-generator")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        # Close quick guide if visible
        try:
            page.click("text=×", timeout=1000)
        except Exception:
            pass
        page.screenshot(path=str(OUT / "survey_export_page.png"))
        print(f"   Saved: {OUT / 'survey_export_page.png'}")

        # Select a template and scroll to buttons
        page.click("text=Appearance Anxiety Inventory (AAI)")
        time.sleep(0.5)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        page.screenshot(path=str(OUT / "survey_export_buttons.png"))
        print(f"   Saved: {OUT / 'survey_export_buttons.png'}")

        # ── 2. Template Editor with Preview ───────────────────────
        print("2. Template Editor Preview...")
        page.goto(f"{BASE}/template-editor")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Select GAD-7
        page.select_option("#globalTemplateSelect", "survey-gad7.json")
        time.sleep(2)

        # Click Preview tab
        page.click("text=Preview")
        time.sleep(1)
        page.screenshot(path=str(OUT / "template_editor_preview.png"))
        print(f"   Saved: {OUT / 'template_editor_preview.png'}")

        # Scroll down to show matrix
        page.evaluate("document.getElementById('previewContent')?.scrollIntoView()")
        time.sleep(0.5)
        page.screenshot(path=str(OUT / "template_preview_matrix.png"))
        print(f"   Saved: {OUT / 'template_preview_matrix.png'}")

        # ── 3. Template Editor with different language ────────────
        print("3. Preview DE...")
        try:
            page.select_option("#previewLangSelect", "de")
            time.sleep(1)
            page.screenshot(path=str(OUT / "template_preview_german.png"))
            print(f"   Saved: {OUT / 'template_preview_german.png'}")
        except Exception as e:
            print(f"   Skipped: {e}")

        # ── 4. Survey Converter page ─────────────────────────────
        print("4. Survey Converter page...")
        page.goto(f"{BASE}/converter")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        # Click Survey tab
        try:
            page.click("text=Survey")
            time.sleep(1)
        except Exception:
            pass
        page.screenshot(path=str(OUT / "survey_converter.png"))
        print(f"   Saved: {OUT / 'survey_converter.png'}")

        # ── 5. Word export modal ─────────────────────────────────
        print("5. Word Export Modal...")
        page.goto(f"{BASE}/template-editor")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.select_option("#globalTemplateSelect", "survey-gad7.json")
        time.sleep(2)
        # Click Validate to enable Export Word
        page.click("text=Validate")
        time.sleep(2)
        # Click Preview
        page.click("text=Preview")
        time.sleep(1)
        # Click Export Word button
        try:
            page.click("#btnExportWord", timeout=2000)
            time.sleep(1)
            page.screenshot(path=str(OUT / "word_export_modal.png"))
            print(f"   Saved: {OUT / 'word_export_modal.png'}")
        except Exception as e:
            print(f"   Skipped modal: {e}")

        browser.close()
        print(f"\nDone! Screenshots saved to {OUT}/")


if __name__ == "__main__":
    main()
