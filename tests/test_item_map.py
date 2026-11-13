import pytest

from src.item_map import ItemMapError, item_alias_map, load_item_map, save_item_map, suggest, template_items

ITEMS = ["ADS01", "ADS02", "ADS03"]

def _pairs(rows):
    return {r["item"]: (r["column"], r["why"]) for r in rows}

def test_same_number_pairs_whatever_the_name():
    assert _pairs(suggest(ITEMS, ["id", "A01", "A02", "A03"])) == {
        "ADS01": ("A01", "number"), "ADS02": ("A02", "number"), "ADS03": ("A03", "number")}

def test_separators_and_zero_padding_are_ignored():
    assert _pairs(suggest(ITEMS, ["ADS_1", "ADS_2", "ADS_3"]))["ADS02"] == ("ADS_2", "number")

def test_a_missing_number_falls_back_to_ascending_order():
    got = _pairs(suggest(ITEMS, ["A01", "A02", "A05"]))
    assert got["ADS03"] == ("A05", "order")

def test_no_column_left_gives_none():
    assert _pairs(suggest(ITEMS, ["A01", "A02"]))["ADS03"] == (None, "none")

def test_two_groups_are_never_mixed():
    got = _pairs(suggest(ITEMS, ["B01", "B02", "A01", "A02", "A03"]))
    assert [c for c, _ in got.values()] == ["A01", "A02", "A03"]

def test_names_with_several_numbers_pair_on_all_of_them():
    got = _pairs(suggest(["ADS1_1", "ADS1_2"], ["Q1x1", "Q1x2"]))
    assert got == {"ADS1_1": ("Q1x1", "number"), "ADS1_2": ("Q1x2", "number")}

def test_a_column_with_the_items_own_name_is_same_and_not_reused():
    got = _pairs(suggest(ITEMS, ["ADS01", "A02", "A03"]))
    assert got["ADS01"] == ("ADS01", "same") and got["ADS02"] == ("A02", "number")

def test_a_saved_entry_wins_when_its_column_is_in_the_file():
    got = _pairs(suggest(ITEMS, ["A01", "A02", "A03"], saved={"ADS01": "A03"}))
    assert got["ADS01"] == ("A03", "saved") and got["ADS03"][0] != "A03"

def test_template_items_skips_sections_and_alias_entries():
    t = {"Study": {}, "Technical": {}, "ADS01": {"Description": "x"}, "old": {"AliasOf": "ADS01"}}
    assert template_items(t) == ["ADS01"]

def test_save_then_load_round_trips_and_drops_identical_names(tmp_path):
    path = save_item_map(tmp_path, "ads", {"ADS01": "A01", "ADS02": "ADS02", "ADS03": ""}, ITEMS)
    assert path == tmp_path / "code" / "item_maps" / "ads.json"
    assert load_item_map(tmp_path, "ads") == {"ADS01": "A01"}

@pytest.mark.parametrize("mapping", [{"NOPE": "A01"}, {"ADS01": "A01", "ADS02": "A01"}])
def test_save_refuses_unknown_items_and_a_column_used_twice(tmp_path, mapping):
    with pytest.raises(ItemMapError):
        save_item_map(tmp_path, "ads", mapping, ITEMS)

@pytest.mark.parametrize("task", ["../x", "a/b", "", "ads.json"])
def test_the_task_name_cannot_leave_the_folder(tmp_path, task):
    with pytest.raises(ItemMapError):
        save_item_map(tmp_path, task, {"ADS01": "A01"}, ITEMS)

def test_saving_an_empty_mapping_removes_the_file(tmp_path):
    save_item_map(tmp_path, "ads", {"ADS01": "A01"}, ITEMS)
    assert save_item_map(tmp_path, "ads", {}, ITEMS) is None
    assert not (tmp_path / "code" / "item_maps" / "ads.json").exists()

@pytest.mark.parametrize("content", ["[1]", "{not json", '{"ADS01": 3}'])
def test_an_invalid_file_is_skipped_and_reported(tmp_path, capsys, content):
    folder = tmp_path / "code" / "item_maps"; folder.mkdir(parents=True)
    (folder / "ads.json").write_text(content, encoding="utf-8")
    assert load_item_map(tmp_path, "ads") == {} and item_alias_map(tmp_path) == {}
    assert "WARNING" in capsys.readouterr().out

def test_alias_map_is_column_to_item_over_all_tasks(tmp_path):
    save_item_map(tmp_path, "ads", {"ADS01": "A01"}, ITEMS)
    save_item_map(tmp_path, "bdi", {"BDI01": "B01"}, ["BDI01"])
    assert item_alias_map(tmp_path) == {"A01": "ADS01", "B01": "BDI01"}

def test_two_tasks_claiming_one_column_is_an_error_naming_both(tmp_path):
    save_item_map(tmp_path, "ads", {"ADS01": "X1"}, ITEMS)
    save_item_map(tmp_path, "bdi", {"BDI01": "X1"}, ["BDI01"])
    with pytest.raises(ItemMapError, match="ads.*bdi|bdi.*ads"):
        item_alias_map(tmp_path)
