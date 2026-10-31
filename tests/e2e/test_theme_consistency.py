"""Every page looks like the project page: the same kind of element gets the same computed style.

/projects is the reference (CLAUDE.md). For each shared element kind that the reference page shows, every other
page that shows it must compute the same font, colours, border and radius. A page that restyles a button, card or
field on its own fails here and names the page, the element and the property.

Not compared yet: h1, h5, links and the size of fields. COMPARE says what is checked per kind.
"""

import pytest

from tests.e2e.conftest import _new_page
from tests.e2e.test_every_page_loads import PAGES

REFERENCE = "/projects"
KINDS = {  # element kind -> selector (the most common style among its matches is measured; $ marks where state exclusions go)
    "body": "body",
    "navbar": ".navbar",
    "h1": "h1",
    "h2": "h2",
    "h5": "h5",
    "label": "label.form-label",
    "primary button": ".btn-primary$",
    "outline button": ".btn-outline-secondary$",
    "card": ".card",
    "card header": ".card-header",
    "select": "select.form-select$",
    "text input": "input.form-control$",
    "badge": ".badge",
}
PROPS = ["fontFamily", "fontSize", "fontWeight", "color", "backgroundColor", "borderTopColor", "borderTopWidth", "borderTopLeftRadius"]
PROBE = """([kinds, props]) => {
  // The most common value per property among a kind's elements: one odd element (a disabled button, a field marked
  // invalid) does not decide what the page looks like. Computed style exists for collapsed (display:none) elements
  // too, and the project page keeps most of its fields folded.
  const plain = ':not(:disabled):not([readonly]):not(.disabled):not(.is-invalid):not(.is-valid):not(.btn-sm):not(.btn-lg):not(.form-select-sm):not(.form-control-sm):not(.form-control-plaintext)';
  const out = {};
  for (const [kind, sel] of Object.entries(kinds)) {
    const els = [...document.querySelectorAll(sel.replace('$', plain))]
      .filter(e => !e.closest('template, .modal, .dropdown-menu'));
    if (!els.length) continue;
    const counts = {};
    for (const e of els) {
      const s = getComputedStyle(e);
      for (const p of props) { counts[p] = counts[p] || {}; counts[p][s[p]] = (counts[p][s[p]] || 0) + 1; }
    }
    out[kind] = Object.fromEntries(props.map(p => [p, Object.entries(counts[p]).sort((a, b) => b[1] - a[1])[0][0]]));
  }
  return out;
}
"""
# Only what should be the same everywhere is compared. Size, weight and corner radius of fields, labels and badges
# depend on where they sit (a small badge, a folded study-metadata field), colours on what they say (status).
FONT = ["fontFamily"]
COMPARE = {
    "body": PROPS,
    "navbar": PROPS,
    "h1": ["fontFamily", "fontSize", "fontWeight", "color"],
    "h2": ["fontFamily", "fontWeight"],  # size and colour: a muted h6-style heading is a legitimate h2
    "h5": ["fontFamily", "fontSize", "fontWeight", "color"],
    "card": ["fontFamily", "backgroundColor", "borderTopWidth", "borderTopLeftRadius"],
    "card header": ["fontFamily", "fontSize", "fontWeight", "borderTopWidth", "borderTopLeftRadius"],
    "primary button": ["fontFamily", "fontSize", "fontWeight", "borderTopLeftRadius"],
    "outline button": ["fontFamily", "fontWeight"],
    "label": FONT,
    "select": ["fontFamily", "backgroundColor"],
    "text input": ["fontFamily", "backgroundColor"],
    "badge": ["fontFamily", "fontWeight"],
}


def _measure(page, studio_url, path):
    page.goto(f"{studio_url}{path}", wait_until="networkidle")
    return page.evaluate(PROBE, [KINDS, PROPS])


@pytest.fixture(scope="module")
def reference(browser, studio_url, tmp_path_factory):
    root = tmp_path_factory.mktemp("theme-ref")
    (root / "code" / "library" / "survey").mkdir(parents=True)
    (root / "project.json").write_text('{"Basics": {"Name": "e2e", "Authors": ["Lovelace, Ada"], "Keywords": ["a","b","c"]}, "StudyDesign": {"Timepoints": "single"}}')
    (root / "dataset_description.json").write_text('{"Name": "e2e", "BIDSVersion": "1.10.0"}')
    context, page, _ = _new_page(browser, studio_url, root)
    measured = _measure(page, studio_url, REFERENCE)
    context.close()
    return measured


@pytest.mark.parametrize("path", [p for p in PAGES if p != REFERENCE])
def test_page_styles_match_the_project_page(app_page, studio_url, reference, path):
    here = _measure(app_page, studio_url, path)
    differences = [
        f"{kind}.{prop}: {path}={here[kind][prop]!r} but {REFERENCE}={want[prop]!r}"
        for kind, want in reference.items()
        if kind in here
        for prop in COMPARE[kind]
        if here[kind][prop] != want[prop]
    ]
    assert not differences, "\n".join(differences)
