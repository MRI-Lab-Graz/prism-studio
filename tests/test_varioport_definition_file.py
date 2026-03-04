import sys
from pathlib import Path


project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import (
    _find_companion_definition_file,
    _parse_varioport_definition_file,
    _select_type7_channels_from_definition,
)


def test_find_companion_definition_file_prefers_same_stem(tmp_path):
    raw_file = tmp_path / "sub-01_task-rest.raw"
    raw_file.write_bytes(b"RAW")

    matching_def = tmp_path / "sub-01_task-rest.def"
    matching_def.write_text("SA\nSE\n", encoding="utf-8")

    other_def = tmp_path / "other.def"
    other_def.write_text("SA\nSE\n", encoding="utf-8")

    found = _find_companion_definition_file(raw_file)

    assert found == matching_def


def test_parse_definition_file_extracts_channels_and_placeholders(tmp_path):
    definition = tmp_path / "EcgRespPuls.def"
    definition.write_text(
        "\n".join(
            [
                "SA",
                "C01 ekg    uV   $05 $01 $01 $0f $02 $07",
                "C02 EDA    uS   $05 $81 $01 $04 $02 $07",
                "C03 resp   nu   $05 $01 $01 $04 $02 $07",
                "C22 ntused nu   $05 $81 $01 $08 $01 $00",
                "C65 Marker bit  $82 $00 $20 $00 $10 $00",
                "SE",
            ]
        ),
        encoding="utf-8",
    )

    parsed = _parse_varioport_definition_file(definition)
    by_index = parsed["channels_by_index"]

    assert parsed["file"] == str(definition)
    assert by_index[0]["name"] == "ekg"
    assert by_index[1]["unit"] == "uS"
    assert by_index[21]["is_placeholder"] is True
    assert by_index[64]["is_marker"] is True
    assert by_index[0]["is_ecg"] is True
    assert by_index[0]["scn"] == 1
    assert by_index[0]["mux"] == 7


def test_type7_selector_prefers_ecg_mux_scn_group(tmp_path):
    definition = tmp_path / "EcgRespPuls.def"
    definition.write_text(
        "\n".join(
            [
                "SA",
                "C01 ekg    uV   $05 $01 $01 $0f $02 $07",
                "C02 EDA    uS   $05 $81 $01 $04 $02 $07",
                "C03 resp   nu   $05 $01 $01 $04 $02 $07",
                "C08 EKG    uv   $05 $81 $01 $04 $02 $06",
                "C22 ntused nu   $05 $81 $01 $08 $01 $00",
                "SE",
            ]
        ),
        encoding="utf-8",
    )

    parsed = _parse_varioport_definition_file(definition)
    channels = [
        {"index": 0, "name": "C01"},
        {"index": 1, "name": "C02"},
        {"index": 2, "name": "C03"},
        {"index": 7, "name": "C08"},
        {"index": 21, "name": "C22"},
    ]

    selected, meta = _select_type7_channels_from_definition(channels, parsed)
    selected_indices = {c["index"] for c in selected}

    assert selected_indices == {0, 1, 2}
    assert meta["anchor_channel"].lower() == "ekg"
    assert meta["anchor_mux"] == 7
    assert meta["anchor_scn"] == 1
    assert "EKG" in meta["dropped_channels"]
