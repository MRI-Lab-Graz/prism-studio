"""
Capture step-by-step screenshots with REAL interactions.
Uses headed browser (visible) with explicit waits for each UI state.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5001"
OUT = Path("docs/img/limesurvey")
OUT.mkdir(parents=True, exist_ok=True)

for f in OUT.glob("*.png"):
    f.unlink()
print(f"Cleared {OUT}/")

N = [0]


def save(page, name, desc=""):
    N[0] += 1
    fname = f"{N[0]:02d}_{name}"
    path = OUT / f"{fname}.png"
    page.screenshot(path=str(path))
    kb = path.stat().st_size / 1024
    print(f"  [{N[0]:02d}] {fname}.png ({kb:.0f}KB) - {desc}")
    return fname


def main():
    with sync_playwright() as p:
        # HEADED browser so we get real rendering
        browser = p.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # Set project via fetch
        page.goto(f"{BASE}/")
        page.wait_for_load_state("networkidle")
        page.evaluate("""() => {
            return fetch('/api/projects/current', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: 'C:\\\\Users\\\\David\\\\Nextcloud2\\\\Documents\\\\Data Steward\\\\Abschlussprojekt\\\\funfzehn'})
            }).then(r => r.json())
        }""")
        time.sleep(1)

        # ============================================================
        print("\n--- EXPORT WORKFLOW ---")
        # ============================================================

        # 1. Survey Export page overview
        page.goto(f"{BASE}/survey-generator")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        save(
            page, "export_page", "Survey Export page with settings and template library"
        )

        # 2. Close quick guide, show settings area
        try:
            page.locator("button:has-text('x'), .btn-close").first.click(timeout=1000)
            time.sleep(0.5)
        except Exception:
            pass

        # 3. Enable DE language
        page.locator("text=DE").first.click()
        time.sleep(1)
        save(page, "languages_de_en", "DE and EN both selected as export languages")

        # 4. Select GAD-7 template
        gad_row = page.locator("text=Generalized Anxiety Disorder")
        gad_row.scroll_into_view_if_needed()
        time.sleep(0.5)

        # Click the checkbox for GAD-7
        gad_checkbox = (
            page.locator("text=Generalized Anxiety Disorder")
            .locator("..")
            .locator("input[type=checkbox], .form-check-input")
            .first
        )
        try:
            gad_checkbox.click(timeout=2000)
        except Exception:
            # Try clicking the row itself
            page.locator("text=Generalized Anxiety Disorder").first.click()
        time.sleep(1)
        save(
            page,
            "template_gad7_selected",
            "GAD-7 selected showing 7 items, DE/EN, Matrix badge",
        )

        # 5. Scroll down to export buttons
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        save(
            page,
            "export_buttons_visible",
            "Export buttons: Boilerplate, Quick Export (.lss), Customize & Export",
        )

        # 6. Navigate to Customizer directly (needs session state from export page)
        # The Customizer requires templates to be stored in session first
        # We load it with the templates already selected from the survey-generator
        page.evaluate("""() => {
            const btn = document.getElementById('customizeExportBtn');
            if (btn) { btn.disabled = false; btn.click(); }
        }""")
        time.sleep(2)
        # If navigation didn't happen, go directly
        if "survey-customizer" not in page.url:
            page.goto(f"{BASE}/survey-customizer")
            page.wait_for_load_state("networkidle")
            time.sleep(3)
        else:
            page.wait_for_load_state("networkidle")
            time.sleep(3)
        save(
            page,
            "customizer_loaded",
            "Survey Customizer: groups panel (left), questions panel (right)",
        )

        # 7. Show questions area
        try:
            questions_panel = page.locator(
                "#questionsContainer, .questions-panel"
            ).first
            if questions_panel.count() > 0:
                questions_panel.scroll_into_view_if_needed()
                time.sleep(1)
        except Exception:
            page.evaluate("window.scrollBy(0, 300)")
            time.sleep(1)
        save(
            page,
            "customizer_questions",
            "Questions with mandatory toggles and matrix grouping",
        )

        # 8. Try to open per-question tool settings
        try:
            cog = page.locator(
                "[title*='tool'], [title*='Tool'], .tool-toggle, .fa-cog"
            ).first
            cog.click(timeout=2000)
            time.sleep(1)
            save(
                page,
                "customizer_question_tool_settings",
                "Per-question LimeSurvey settings: type, validation, relevance, CSS",
            )
        except Exception:
            print("  (no tool toggle found)")

        # 9-12. LimeSurvey Settings sections
        for section_name, desc in [
            (
                "Welcome & End Messages",
                "Welcome & End message settings with template dropdowns",
            ),
            ("Data Policy", "Data Policy / Consent settings with GDPR templates"),
            (
                "Navigation & Presentation",
                "Navigation: progress bar, question numbering, back button",
            ),
        ]:
            try:
                page.evaluate("window.scrollBy(0, 300)")
                time.sleep(0.5)
                page.get_by_text(section_name, exact=False).first.click(timeout=2000)
                time.sleep(1)
                slug = section_name.lower().replace(" & ", "_").replace(" ", "_")
                save(page, f"customizer_{slug}", desc)
            except Exception as e:
                print(f"  (skipped {section_name}: {e})")

        # Action buttons at bottom
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        save(
            page,
            "customizer_action_buttons",
            "Action buttons: Reset, Preview Questionnaire, Export Word, Export Survey",
        )

        # ============================================================
        print("\n--- IMPORT WORKFLOW ---")
        # ============================================================

        # 13. Converter - Survey tab (navigate directly)
        page.goto(f"{BASE}/converter")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        # Click the Survey tab button in the modality tabs
        try:
            page.get_by_role("button", name="Survey").click(timeout=3000)
            time.sleep(2)
        except Exception:
            try:
                page.locator(
                    ".nav-link:has-text('Survey'), button:has-text('Survey')"
                ).first.click(timeout=2000)
                time.sleep(2)
            except Exception:
                pass
        save(
            page,
            "converter_survey_tab",
            "Survey tab: upload .lsa/.csv, sourcedata dropdown, session ID",
        )

        # 14. Scroll to show advanced options
        page.evaluate("window.scrollBy(0, 300)")
        time.sleep(0.5)
        save(
            page,
            "converter_survey_options",
            "Survey conversion: participant ID, session, advanced options",
        )

        # ============================================================
        print("\n--- TEMPLATE EDITOR ---")
        # ============================================================

        try:
            # 15. Template Editor - load GAD-7
            page.goto(f"{BASE}/template-editor")
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            page.select_option("#globalTemplateSelect", "survey-gad7.json")
            time.sleep(2)
            save(
                page,
                "editor_gad7_loaded",
                "Template Editor with GAD-7 loaded, validation status, languages",
            )

            # 16. Click Preview tab
            page.get_by_role("link", name="Preview").click()
            time.sleep(1)
            page.evaluate("""
                const pc = document.getElementById('previewContent');
                if (pc) pc.scrollIntoView({behavior: 'instant'});
            """)
            time.sleep(0.5)
            save(
                page,
                "preview_gad7_english",
                "GAD-7 preview: title, authors, instructions, matrix table (EN)",
            )

            # 17. Switch to German
            try:
                page.select_option("#previewLangSelect", "de")
                time.sleep(1)
                save(
                    page,
                    "preview_gad7_german",
                    "GAD-7 preview in German: localized items and response options",
                )
            except Exception:
                pass

            # 18. Word Export modal
            try:
                page.get_by_role("link", name="Editor").click()
                time.sleep(0.5)
                page.get_by_role("button", name="Validate").click()
                time.sleep(2)
                page.get_by_role("link", name="Preview").click()
                time.sleep(1)
                page.evaluate("""
                    const pc = document.getElementById('previewContent');
                    if (pc) pc.scrollIntoView({behavior: 'instant'});
                """)
                time.sleep(0.5)
                page.locator("#btnExportWord").click()
                time.sleep(1)
                save(
                    page,
                    "word_export_modal",
                    "Word Export: participant ID, randomization, font size, column width",
                )
            except Exception as e:
                print(f"  Word modal: {e}")
        except Exception as e:
            print(f"  Template editor section error: {e}")

        browser.close()

        print(f"\nDone! {N[0]} screenshots in {OUT}/")


if __name__ == "__main__":
    main()
