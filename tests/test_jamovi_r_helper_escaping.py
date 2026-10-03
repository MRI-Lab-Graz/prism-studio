"""The generated Jamovi/R helper script embeds names/labels from survey
templates. A shared template must not be able to break out of the R string
literals (or a '#' comment) and run code when the script is executed."""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from src.recipes_surveys import _r_str, _write_jamovi_r_helper

HOSTILE = "0',system('touch pwnedR'),'"


def test_r_str_escapes_quote_backslash_and_newlines():
    assert _r_str("a'b") == "'a\\'b'"
    assert _r_str("a\\b") == "'a\\\\b'"
    assert _r_str("a\nb\rc") == "'a\\nb\\rc'"
    # backslash-quote must not turn into an escaped backslash followed by a bare quote
    assert _r_str("\\'") == "'\\\\\\''"


def _write(tmp_path):
    out = tmp_path / "h.R"
    _write_jamovi_r_helper(
        out,
        data_filename=HOSTILE + ".csv",
        variable_labels={HOSTILE: "label\rsystem('touch pwnedR')"},
        value_labels={HOSTILE: {HOSTILE: "lab\\'),system('touch pwnedR'),('"}},
    )
    return out


def test_hostile_values_do_not_appear_unescaped(tmp_path):
    text = _write(tmp_path).read_text()
    code = "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    assert not re.search(r"(?<!\\)',system\(", code)  # a quote not preceded by a backslash
    assert "\r" not in text
    # the '#' comment line for the variable description stays a single line
    assert all(
        not line.lstrip().startswith("system(") for line in text.splitlines()
    )


@pytest.mark.skipif(not shutil.which("Rscript"), reason="Rscript not installed")
def test_parsed_r_contains_no_system_call(tmp_path):
    out = _write(tmp_path)
    res = subprocess.run(
        ["Rscript", "-e", f"cat('system' %in% all.names(parse(file='{out}')))"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.stdout.strip() == "FALSE", res.stderr
