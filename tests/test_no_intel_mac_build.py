"""Intel macOS is not built or offered any more.

Homebrew no longer bottles Intel macOS, so the Intel build compiled openssl and
cmake from source and hung the release; GitHub drops Intel runners in 2027.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _text(*parts):
    return REPO.joinpath(*parts).read_text(encoding="utf-8")


def test_build_workflow_has_no_intel_mac_build():
    wf = _text(".github", "workflows", "build.yml")
    for needle in ("MacOS Intel", "AppleIntel", "x86_64", "Intel macOS"):
        assert needle not in wf, needle
    assert "prism-studio-macOS-AppleSilicon" in wf  # Apple Silicon is still built


def test_user_docs_do_not_offer_an_intel_download():
    for parts in (("README.md",), ("docs", "INSTALLATION.md"), ("docs", "TUTORIAL_BEGINNER_0_INSTALL.md")):
        assert "AppleIntel" not in _text(*parts), parts


def test_current_release_notes_exist_and_name_only_shipped_downloads():
    notes = _text("docs", "RELEASE_NOTES_v1.19.2.md")
    assert "AppleIntel" not in notes
    assert "prism-studio-macOS-AppleSilicon.zip" in notes
