# Accessibility checklist: making one Studio page WCAG 2.2 AA

Goal: the **validator page** (`/validate`) meets WCAG 2.2 level AA. Then we repeat this for the next page.
This file is for whoever does the manual part; read it once, then work down the list.

**WCAG 2.2 AA** is the W3C standard that the EU rules (EN 301 549) and most accessibility laws point to.
Tool results ("axe passes") are not the same as conformance: axe finds roughly a third of the problems.
The rest is the manual checks below.

## 1. Set up (once)

```bash
pip install -r requirements.txt -r requirements-dev.txt
npm ci
python -m playwright install chromium
python app/prism-studio.py        # the address (with the port) is printed on start
```

Open the validator: **Validate** in the top menu.

## 2. What is already done and tested

These are fixed and guarded by tests; do not redo them, but do not break them:

| Point | WCAG | Test |
|---|---|---|
| One `<h1>` per page (the page header) | 1.3.1, 2.4.6 | `tests/e2e/test_validate_wcag22.py` |
| Links in running text are underlined | 1.4.1 | same file |
| No `aria-label` on elements that cannot have one | 4.1.2 | same file |
| The sticky navbar never covers the focused control | 2.4.11 | same file |
| No serious or critical axe violation, all 15 pages | various | `tests/e2e/test_accessibility.py` |
| Visible focus ring; skip link as first Tab stop | 2.4.7, 2.4.1 | `tests/e2e/test_keyboard_focus.py` |
| Text contrast 4.5:1 (theme colours) | 1.4.3 | `tests/e2e/test_accessibility.py` |

Run them any time:

```bash
python -m pytest tests/e2e/test_validate_wcag22.py tests/e2e/test_accessibility.py tests/e2e/test_keyboard_focus.py -q
```

## 3. Manual checks (your part)

Work on `/validate`. For each point write **pass** or **fail** in the table in section 5.
Do each check with a real project open, and again with no project open.

### 3.1 Keyboard only (no mouse)
- Press **Tab** through the whole page. Every button, link and field must be reachable, in a sensible order.
- You must always see where the focus is (green outline), and it must never disappear behind the top bar.
- **Shift+Tab** goes back. **Enter / Space** activates buttons. **Esc** closes dialogs.
- Open the folder picker: focus must stay inside it, and return to the button that opened it when it closes.

### 3.2 Zoom and reflow (WCAG 1.4.4, 1.4.10)
- Browser zoom to **200%**, then **400%** (Cmd/Ctrl and +). Nothing may be cut off, and at 400% there must be
  no sideways scrolling (except wide tables, which may scroll by themselves).

### 3.3 Text spacing (WCAG 1.4.12)
- Install the "Text Spacing Editor" browser extension, or paste this in the console:
  `document.documentElement.style.cssText='line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important'`
- No text may be clipped or overlap.

### 3.4 Navbar contrast (WCAG 1.4.3), the three items axe could not decide
- Measure the colours with the browser inspector (click a colour swatch, it shows the ratio) for: the brand text,
  the menu items (also the active one), the project badge. Ratio needs to be **4.5:1** or more (3:1 for text 18pt+).
- If one fails, do not fix it yourself in the page: tell the maintainer, because the navbar is a shared theme part.

### 3.5 Screen reader (VoiceOver on Mac, NVDA on Windows)
VoiceOver: **Cmd+F5** starts and stops it. **VO** = Ctrl+Option. Turn on the *Caption Panel* in VoiceOver Utility
so you can read what it says.
- **Tab** through the page: each control is announced with a name and its role ("Browse for file, button").
- **VO+U** (rotor): Headings list shows a sensible outline; Landmarks list shows navigation and main.
- Start a validation. The progress and the result must be **spoken without you moving the focus**.
- Open the folder picker; the dialog title is announced.
- Reload the page, press Tab once: you hear "Skip to main content".

### 3.6 Errors (WCAG 3.3.1, 3.3.3)
- Run the validator on a folder that is not a dataset, and on one with errors. The message must say what went
  wrong and where, in text (not only by colour), and a screen reader must hear it.

### 3.7 Other 2.2 points
- Any drag-and-drop has another way to do the same by click (2.5.7).
- Click targets are at least 24x24 px (2.5.8); axe checks this, just confirm by eye on small icon buttons.
- Help text and contact links are in the same place on every page (3.2.6).

## 4. How to report and fix

- **Report** each failure in the table: what you did, what you heard or saw, what you expected.
- **Fix** (small ones): one finding per branch, one pull request each. Rules of this repo:
  1. Write a **failing test first** and watch it fail (`tests/e2e/...`), then fix. See `CLAUDE.md`, "Always use TDD".
  2. Colours, spacing, focus: change the **theme** (`app/static/css/studio-theme.css`), never a single page.
  3. Page layout and parts: use the macros in `app/templates/includes/ui/macros.html`.
  4. Run the tests in section 2 and the page's own e2e tests before opening the pull request.
- Ask the maintainer before: changing theme colours or tokens, touching `base.html`, anything in the navbar.

## 5. Results (copy per page, fill in)

| Check | Result | Notes (steps, what you heard/saw) |
|---|---|---|
| 3.1 Keyboard only | | |
| 3.2 Zoom 200% / 400% | | |
| 3.3 Text spacing | | |
| 3.4 Navbar contrast | | |
| 3.5 Screen reader | | |
| 3.6 Errors | | |
| 3.7 Other 2.2 points | | |

## 6. Done means

- All tests in section 2 pass; every row in section 5 is **pass**, or has a fix merged or a written reason.
- The maintainer has reviewed it. Then the page can be listed as conformant in the accessibility statement.
