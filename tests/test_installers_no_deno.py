"""Installing PRISM no longer downloads or runs the deno.land installer (spec 2026-10-07)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEW_FIX = "Reinstall prism-validator (it includes the BIDS engine bids-validator-deno) or run with --no-bids"
OLD_PHRASES = ("legacy `bids-validator` CLI", "legacy 'bids-validator' CLI", "legacy bids-validator CLI")


def test_installers_do_not_run_the_deno_installer_script():
    for rel in ("install.sh", "scripts/setup/windows.ps1"):
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "deno.land" not in text, rel
        assert "install_deno" not in text.replace("$installdeno", "install_deno"), rel


def test_code_has_no_system_deno_or_node_validator_path():
    text = (ROOT / "app" / "src" / "bids_validator.py").read_text(encoding="utf-8")
    assert '"deno"' not in text and "jsr:" not in text and "'bids-validator'" not in text
    assert '"bids-validator"' not in text.replace("bids-validator-deno", "")


def test_error_text_points_at_the_new_fix():
    issues = (ROOT / "app/src/issues.py").read_text(encoding="utf-8")
    assert NEW_FIX in issues
    docs = (ROOT / "docs/ERROR_CODES.md").read_text(encoding="utf-8")
    assert "reinstall prism-validator, or run with `--no-bids`" in docs
    for text in (issues, docs):
        for old in OLD_PHRASES:
            assert old not in text
