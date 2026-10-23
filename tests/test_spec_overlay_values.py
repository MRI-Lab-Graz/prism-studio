"""Local schema additions: spec_overlay operations and `prism_tools.py spec local add-values|remove-values` (layer 2, B3)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.spec_overlay import (  # noqa: E402
    OverlayError, add_local_values, find_unknown_values, list_local_items, remove_local_values,
)

REPO = Path(__file__).resolve().parent.parent
FIELD = "Technical.SpecimenType"


def _patch_file(root: Path) -> Path:
    return root / "code" / "specification" / "patches" / "biosample.json"


def _sidecar(root: Path, name="biosample-sweat_biosample.json", specimen="sweat", method="swab") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps({"Technical": {"SpecimenType": specimen, "CollectionMethod": method}}), encoding="utf-8")


def _read(root: Path) -> dict:
    return json.loads(_patch_file(root).read_text(encoding="utf-8"))


def test_add_writes_the_patch(tmp_path):
    result = add_local_values(tmp_path, FIELD, ["sweat"])
    assert result["skipped"] == [] and result["written"] == _patch_file(tmp_path)
    assert _read(tmp_path) == {"operations": [{"op": "add_enum_values", "path": FIELD, "values": ["sweat"]}]}


def test_adding_twice_merges_without_duplicates(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    add_local_values(tmp_path, FIELD, ["sweat", "tears"])
    assert _read(tmp_path)["operations"] == [{"op": "add_enum_values", "path": FIELD, "values": ["sweat", "tears"]}]


def test_an_official_value_is_skipped_and_nothing_is_written(tmp_path):
    result = add_local_values(tmp_path, FIELD, ["saliva"])
    assert result["skipped"] == ["saliva"] and result["written"] is None and not _patch_file(tmp_path).exists()


def test_official_and_new_values_together(tmp_path):
    result = add_local_values(tmp_path, FIELD, ["saliva", "sweat"])
    assert result["skipped"] == ["saliva"] and _read(tmp_path)["operations"][0]["values"] == ["sweat"]


@pytest.mark.parametrize("field,values", [
    ("Technical.Nope", ["x"]), ("Technical.StorageTemperature", ["x"]), ("../etc", ["x"]),
    (FIELD, ["Sweat"]), (FIELD, ["a b"]), (FIELD, []), (FIELD, ["x\n"]),
])
def test_bad_fields_and_values_are_refused_and_write_nothing(tmp_path, field, values):
    with pytest.raises(OverlayError):
        add_local_values(tmp_path, field, values)
    assert not _patch_file(tmp_path).exists()


def test_a_broken_existing_patch_is_not_overwritten(tmp_path):
    _patch_file(tmp_path).parent.mkdir(parents=True)
    _patch_file(tmp_path).write_text("{nope", encoding="utf-8")
    with pytest.raises(OverlayError):
        add_local_values(tmp_path, FIELD, ["sweat"])
    assert _patch_file(tmp_path).read_text(encoding="utf-8") == "{nope"


def test_a_symlinked_specification_folder_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "code").mkdir()
    (tmp_path / "p" / "code" / "specification").symlink_to(outside)
    with pytest.raises(OverlayError, match="symbolic link"):
        add_local_values(tmp_path / "p", FIELD, ["sweat"])
    assert list(outside.iterdir()) == []


def test_remove_one_value_then_the_last_removes_the_file(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat", "tears"])
    remove_local_values(tmp_path, FIELD, ["sweat"])
    assert _read(tmp_path)["operations"][0]["values"] == ["tears"]
    remove_local_values(tmp_path, FIELD, ["tears"])
    assert not _patch_file(tmp_path).exists()


def test_removing_a_value_that_is_not_there_is_an_error(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    with pytest.raises(OverlayError, match="tears"):
        remove_local_values(tmp_path, FIELD, ["tears"])


def test_find_unknown_values(tmp_path):
    _sidecar(tmp_path)
    found = find_unknown_values(tmp_path)
    assert [(f["field"], f["value"]) for f in found] == [(FIELD, "sweat")]
    add_local_values(tmp_path, FIELD, ["sweat"])
    assert find_unknown_values(tmp_path) == []


def test_find_unknown_values_reports_once_per_sidecar_and_skips_other_folders(tmp_path):
    _sidecar(tmp_path)
    _sidecar(tmp_path / "sub-01", "biosample-sweat_biosample.json")
    _sidecar(tmp_path / "derivatives" / "x", "biosample-tears_biosample.json", specimen="tears")
    _sidecar(tmp_path / "code" / "y", "biosample-tears_biosample.json", specimen="tears")
    found = find_unknown_values(tmp_path)
    assert sorted(f["value"] for f in found) == ["sweat", "sweat"] and len({f["sidecar"] for f in found}) == 2


def test_find_unknown_values_ignores_values_that_cannot_be_added(tmp_path):
    _sidecar(tmp_path, specimen="Sweat Gland")  # not lowercase: a typo to fix, not an addition
    assert find_unknown_values(tmp_path) == []


def test_list_shows_layer_2_with_status(tmp_path):
    add_local_values(tmp_path, FIELD, ["sweat"])
    items = [i for i in list_local_items(tmp_path) if i["layer"] == 2]
    assert [(i["id"], i["status"]) for i in items] == [(f"{FIELD}: sweat", "local")]
    _patch_file(tmp_path).write_text(json.dumps(
        {"operations": [{"op": "add_enum_values", "path": FIELD, "values": ["saliva"]}]}), encoding="utf-8")
    assert [i["status"] for i in list_local_items(tmp_path) if i["layer"] == 2] == ["now-official"]
    _patch_file(tmp_path).write_text("{nope", encoding="utf-8")
    assert [i["status"] for i in list_local_items(tmp_path) if i["layer"] == 2] == ["invalid"]


# --- the command line ---------------------------------------------------------------------------------

def _run(*args):
    result = subprocess.run([sys.executable, str(REPO / "prism_tools.py"), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout


def test_cli_add_list_remove(tmp_path):
    code, out = _run("spec", "local", "add-values", "--project", str(tmp_path), "--field", FIELD, "--value", "sweat", "--value", "tears", "--json")
    assert code == 0 and json.loads(out)["success"]
    assert _read(tmp_path)["operations"][0]["values"] == ["sweat", "tears"]
    code, out = _run("spec", "local", "list", "--project", str(tmp_path), "--json")
    assert [i["id"] for i in json.loads(out)["items"] if i["layer"] == 2] == [f"{FIELD}: sweat", f"{FIELD}: tears"]
    code, out = _run("spec", "local", "remove-values", "--project", str(tmp_path), "--field", FIELD, "--value", "sweat", "--value", "tears", "--json")
    assert code == 0 and not _patch_file(tmp_path).exists()


def test_cli_refuses_a_bad_field_with_exit_1(tmp_path):
    code, out = _run("spec", "local", "add-values", "--project", str(tmp_path), "--field", "Technical.Nope", "--value", "x", "--json")
    assert code == 1 and json.loads(out)["success"] is False


def test_cli_says_when_everything_is_official(tmp_path):
    code, out = _run("spec", "local", "add-values", "--project", str(tmp_path), "--field", FIELD, "--value", "saliva")
    assert code == 0 and "official" in out and not _patch_file(tmp_path).exists()
