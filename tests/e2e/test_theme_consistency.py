"""Every page looks like the project page: the same kind of element gets the same computed style.

/projects is the reference (CLAUDE.md). For each shared element kind that the reference page shows, every other
page that shows it must compute the same font, colours, border and radius. A page that restyles a button, card or
field on its own fails here and names the page, the element and the property.
"""

import pytest

from tests.e2e.conftest import _new_page
from tests.e2e.test_every_page_loads import PAGES

REFERENCE = "/projects"
KINDS = {  # element kind -> selector (first visible match is measured)
    "body": "body",
    "navbar": ".navbar",
    "h1": "h1",
    "h2": "h2",
    "h5": "h5",
    "label": "label.form-label",
    "primary button": ".btn-primary",
    "outline button": ".btn-outline-secondary",
    "card": ".card",
    "card header": ".card-header",
    "select": "select.form-select",
    "text input": "input.form-control",
    "link": "a:not(.btn):not(.nav-link):not(.dropdown-item):not(.navbar-brand)",
    "badge": ".badge",
}
PROPS = ["fontFamily", "fontSize", "fontWeight", "color", "backgroundColor", "borderTopColor", "borderTopWidth", "borderTopLeftRadius"]
PROBE = """([kinds, props]) => {
  const out = {};
  for (const [kind, sel] of Object.entries(kinds)) {
    const el = [...document.querySelectorAll(sel)].find(e => {
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !e.closest('[hidden], .d-none');
    });
    if (!el) continue;
    const s = getComputedStyle(el);
    out[kind] = Object.fromEntries(props.map(p => [p, s[p]]));
  }
  return out;
}"""
# What a page may show differently on purpose: the badge colour says what kind of status it is.
ALLOWED = {"badge": {"color", "backgroundColor", "borderTopColor"}, "link": {"color"}, "card": {"borderTopColor"},
           "card header": {"color", "backgroundColor", "borderTopColor"}}  # each section picks its variant: bg-success, bg-warning, bg-info


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
        for prop in PROPS
        if prop not in ALLOWED.get(kind, ()) and here[kind][prop] != want[prop]
    ]
    assert not differences, "\n".join(differences)
