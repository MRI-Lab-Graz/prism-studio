"""LICENSE must be the plain AGPL-3.0 text: a custom header in front of it makes GitHub (and the JOSS
bot) report the license as "Other"; the copyright line lives in README.md instead."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_license_starts_with_the_agpl_title():
    first_line = next(line for line in (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines() if line.strip())
    assert first_line.strip() == "GNU AFFERO GENERAL PUBLIC LICENSE"


def test_license_ends_with_the_agpl_text_not_a_note():
    last_line = [line for line in (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines() if line.strip()][-1]
    assert last_line.strip() == "<https://www.gnu.org/licenses/>."
