"""StudioTheme (JS) and the Jinja macros must emit the same markup."""
import json
import re
import subprocess
from pathlib import Path

import jinja2
import pytest

ROOT = Path(__file__).resolve().parent.parent
THEME_JS = ROOT / "app" / "static" / "js" / "studio-theme.js"
ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / "app" / "templates")))


def _norm(html):
    return re.sub(r">\s+<", "><", re.sub(r"\s+", " ", html)).strip()


def _js(fn, arg):
    code = (
        # package.json says "type": "module", so require() can't load the browser script
        f"const m={{exports:{{}}}};new Function('module',require('fs').readFileSync({json.dumps(str(THEME_JS))},'utf8'))(m);const t=m.exports;"
        f"process.stdout.write(t.{fn}(JSON.parse(process.argv[1])));"
    )
    return subprocess.run(
        ["node", "-e", code, json.dumps(arg)], capture_output=True, text=True, check=True
    ).stdout


def _macro(name, **kwargs):
    tpl = ENV.from_string(
        "{% from 'includes/ui/macros.html' import " + name + " %}{{ " + name + "(**kw) }}"
    )
    return tpl.render(kw=kwargs)


def _same(js_fn, macro, arg, **kw):
    assert _norm(_js(js_fn, arg)) == _norm(_macro(macro, **kw))


def test_field_label_required_with_tip():
    _same("fieldLabelHtml", "field_label",
          {"text": "Authors", "tier": "required", "tip": "Add one."},
          text="Authors", tier="required", tip="Add one.")


def test_field_label_no_tier_no_tip():
    _same("fieldLabelHtml", "field_label", {"text": "Name"}, text="Name")


def test_tip_is_escaped():
    tip = 'a "b" <c> & d\ne'
    html = _js("fieldLabelHtml", {"text": "X", "tip": tip})
    assert "<c>" not in html and "&#34;b&#34;" in html
    _same("fieldLabelHtml", "field_label", {"text": "X", "tip": tip}, text="X", tip=tip)


def test_tally_complete_is_green():
    html = _js("tally", {"required": [3, 3]})
    assert "bg-success" in html and "Required 3/3" in html
    _same("tally", "tally", {"required": [3, 3], "core": [1, 2], "fair": [0, 4]},
          required=(3, 3), core=(1, 2), fair=(0, 4))


def test_tally_skips_zero_total():
    assert _js("tally", {"required": [0, 0], "core": [0, 0]}) == ""
    assert _norm(_macro("tally", required=(0, 0), core=(0, 0))) == ""
