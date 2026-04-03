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


def set_project(page):
    """Set active project via JS in the browser session."""
    page.goto(f"{BASE}/")
    page.evaluate("""
        fetch('/api/projects/current', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: 'C:\\\\Users\\\\David\\\\Nextcloud2\\\\Documents\\\\Data Steward\\\\Abschlussprojekt\\\\funfzehn'})
        })
    """)
    time.sleep(1)


def close_claude_banner(page):
    """Close the Claude-in-Chrome notification if visible."""
    try:
        page.click("text=×", timeout=500)
    except Exception:
        pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        set_project(page)

        # ═══════════════════════════════════════════════════════════
        # STEP 1: Survey Export Page
        # ═══════════════════════════════════════════════════════════
        print("Step 1: Survey Export page...")
        page.goto(f"{BASE}/survey-generator")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Close quick guide
        try:
            close_btn = page.locator(".btn-close, [aria-label='Close']").first
            close_btn.click(timeout=1000)
            time.sleep(0.5)
        except Exception:
            pass

        page.screenshot(path=str(OUT / "01_survey_export_page.png"))
        print(f"   -> 01_survey_export_page.png")

        # Select a template (AAI)
        page.click("text=Appearance Anxiety Inventory (AAI)")
        time.sleep(0.5)

        # Scroll to export buttons
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        page.screenshot(path=str(OUT / "02_survey_export_buttons.png"))
        print(f"   -> 02_survey_export_buttons.png")

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Survey Customizer
        # ═══════════════════════════════════════════════════════════
        print("Step 2: Survey Customizer...")

        # We need to select templates and go to customizer
        # First scroll back up and select a few templates
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)

        # Click Customize & Export button
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        try:
            page.click("text=Customize & Export", timeout=3000)
            time.sleep(3)
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            page.screenshot(path=str(OUT / "03_customizer_overview.png"))
            print(f"   -> 03_customizer_overview.png")

            # Scroll to show LimeSurvey settings section
            page.evaluate("""
                const el = document.getElementById('lsSettingsSection');
                if (el) el.scrollIntoView({behavior: 'instant'});
            """)
            time.sleep(1)
            page.screenshot(path=str(OUT / "04_customizer_ls_settings.png"))
            print(f"   -> 04_customizer_ls_settings.png")

            # Scroll to show question-level settings
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)

            # Try to open a tool settings panel
            try:
                page.click(".tool-toggle, [title*='tool'], [title*='Tool']", timeout=2000)
                time.sleep(1)
                page.screenshot(path=str(OUT / "05_customizer_question_settings.png"))
                print(f"   -> 05_customizer_question_settings.png")
            except Exception:
                print("   (skipped question settings - no toggle found)")

            # Show export buttons area
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            page.screenshot(path=str(OUT / "06_customizer_export_area.png"))
            print(f"   -> 06_customizer_export_area.png")

        except Exception as e:
            print(f"   Customizer skipped: {e}")

        # ═══════════════════════════════════════════════════════════
        # STEP 7: Template Editor - Import .lss
        # ═══════════════════════════════════════════════════════════
        print("Step 7: Template Editor (import flow)...")
        page.goto(f"{BASE}/template-editor")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        page.screenshot(path=str(OUT / "07_template_editor_import.png"))
        print(f"   -> 07_template_editor_import.png")

        # Load a template to show preview
        try:
            page.select_option("#globalTemplateSelect", "survey-gad7.json")
            time.sleep(2)

            # Click Preview tab
            page.click("text=Preview")
            time.sleep(1)

            # Scroll to preview content
            page.evaluate("""
                const pc = document.getElementById('previewContent');
                if (pc) pc.scrollIntoView({behavior: 'instant'});
            """)
            time.sleep(0.5)
            page.screenshot(path=str(OUT / "08_template_preview_matrix.png"))
            print(f"   -> 08_template_preview_matrix.png")

            # Switch to German
            try:
                page.select_option("#previewLangSelect", "de")
                time.sleep(1)
                page.screenshot(path=str(OUT / "09_template_preview_german.png"))
                print(f"   -> 09_template_preview_german.png")
            except Exception:
                pass

            # Show Word Export modal
            try:
                # First validate to enable button
                page.click("text=Validate")
                time.sleep(2)
                page.click("text=Preview")
                time.sleep(1)
                page.click("#btnExportWord", timeout=2000)
                time.sleep(1)
                page.screenshot(path=str(OUT / "10_word_export_modal.png"))
                print(f"   -> 10_word_export_modal.png")
                # Close modal
                page.keyboard.press("Escape")
                time.sleep(0.5)
            except Exception as e:
                print(f"   Word modal skipped: {e}")

        except Exception as e:
            print(f"   Template editor skipped: {e}")

        # ═══════════════════════════════════════════════════════════
        # Survey Converter page
        # ═══════════════════════════════════════════════════════════
        print("Survey Converter...")
        page.goto(f"{BASE}/converter")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Click Survey tab
        try:
            page.click("text=Survey", timeout=2000)
            time.sleep(1)
        except Exception:
            pass
        page.screenshot(path=str(OUT / "11_survey_converter.png"))
        print(f"   -> 11_survey_converter.png")

        # ═══════════════════════════════════════════════════════════
        # GIF: Survey Export workflow
        # ═══════════════════════════════════════════════════════════
        print("\nGenerating workflow GIF...")
        page2 = ctx.new_page()

        # Set project in new page
        page2.goto(f"{BASE}/")
        page2.evaluate("""
            fetch('/api/projects/current', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: 'C:\\\\Users\\\\David\\\\Nextcloud2\\\\Documents\\\\Data Steward\\\\Abschlussprojekt\\\\funfzehn'})
            })
        """)
        time.sleep(1)

        gif_frames = []

        # Frame 1: Survey Export page
        page2.goto(f"{BASE}/survey-generator")
        page2.wait_for_load_state("networkidle")
        time.sleep(3)
        gif_frames.append(page2.screenshot())

        # Frame 2: Select templates
        page2.click("text=Appearance Anxiety Inventory (AAI)")
        time.sleep(0.5)
        page2.click("text=Aggressive behavior scale")
        time.sleep(0.5)
        gif_frames.append(page2.screenshot())

        # Frame 3: Scroll to buttons
        page2.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        gif_frames.append(page2.screenshot())

        # Save GIF frames as individual PNGs (for manual GIF creation)
        for i, frame in enumerate(gif_frames):
            path = OUT / f"gif_workflow_frame_{i+1}.png"
            with open(path, "wb") as f:
                f.write(frame)
        print(f"   -> {len(gif_frames)} GIF frames saved")

        page2.close()

        browser.close()
        print(f"\nDone! All screenshots saved to {OUT}/")
        print("\nScreenshot inventory:")
        for f in sorted(OUT.glob("*.png")):
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name:45s} {size_kb:6.0f} KB")


if __name__ == "__main__":
    main()
