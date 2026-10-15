from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = sorted((REPO / "proposals").glob("*/fixture"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.parent.name)
def test_proposal_fixture_validates(fixture: Path, monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(REPO / "app" / "src"))
    from runner import validate_dataset

    issues, stats = validate_dataset(str(fixture), run_bids=False)
    errors = [i[1] for i in issues if i[0] == "ERROR"]
    assert errors == [], f"{fixture.parent.name}: the fixture must validate"
    # The validator silently skips a modality folder it does not know, so
    # "no errors" alone would pass for an unregistered modality.
    modalities = [p.name for p in (fixture / "sub-01").iterdir() if p.is_dir()]
    assert modalities, f"{fixture.parent.name}: the fixture has no modality folder"
    unregistered = [m for m in modalities if stats.modalities.get(m, 0) < 1]
    assert not unregistered, (
        f"{fixture.parent.name}: modality {unregistered} is not registered yet; "
        f"follow its REGISTRATION.md"
    )
