import json
from pathlib import Path

import pandas as pd
import pytest

from src.converters import excel_to_biometrics as converter
from src.converters.excel_base import (
    clean_variable_name,
    detect_language,
    find_column_idx,
    parse_levels,
)


def test_bootstrap_import_path_adds_repo_and_app(monkeypatch) -> None:
    monkeypatch.setattr(converter.sys, "path", ["already-present"])

    converter._bootstrap_import_path()

    repo_root = str(Path(converter.__file__).resolve().parents[2])
    app_root = str(Path(converter.__file__).resolve().parents[2] / "app")
    assert repo_root in converter.sys.path
    assert app_root in converter.sys.path


def test_excel_base_helpers_cover_alias_levels_and_language() -> None:
    header = [" Variable Name ", "Beschreibung", "Allowed Values"]

    assert find_column_idx(header, {"variable name", "item_id"}) == 0
    assert find_column_idx(header, {"missing"}) is None
    assert clean_variable_name("  reaction_time  ") == "reaction_time"
    assert parse_levels("1=Never; 2=Sometimes") == {"1": "Never", "2": "Sometimes"}
    assert parse_levels("1=Never, 2=Sometimes") == {"1": "Never", "2": "Sometimes"}
    assert parse_levels("not structured") is None
    assert parse_levels("") is None
    assert detect_language(["äußerst wichtig"]) == "de"
    assert detect_language(["während des Tests"]) == "de"
    assert detect_language(["Always available"]) == "en"
    assert detect_language([]) == "en"


@pytest.mark.parametrize(
    ("units_cell", "scaling_cell", "description_cell", "expected"),
    [
        ("kg", None, None, "kg"),
        (None, "cm; (min: 18 cm; max: 126 cm)", None, "cm"),
        (None, "Likert scale", None, "score"),
        (None, None, None, "n/a"),
    ],
)
def test_infer_units_covers_common_fallbacks(units_cell, scaling_cell, description_cell, expected) -> None:
    assert converter._infer_units(units_cell, scaling_cell, description_cell) == expected


def test_translation_and_scalar_parsers_cover_edge_cases() -> None:
    assert converter.translate_text("Imported biometrics data") == "Importierte biometrische Daten"
    assert converter.format_group_name("cmj") == "CMJ"
    assert converter.format_group_name("balance") == "Balance"
    assert converter._clean_key(None) is None
    assert converter._clean_key(" item ") == "item"
    assert converter._parse_float("1,5") == 1.5
    assert converter._parse_float("not-a-number") is None
    assert converter._parse_minmax(None, None, "min: 1; max: 9") == (1.0, 9.0)


def test_allowed_values_and_datatype_inference_cover_numeric_and_text_cases() -> None:
    assert converter._parse_allowed_values(None) is None
    assert converter._parse_allowed_values(["1", None, "2"]) == ["1", "2"]
    assert converter._parse_allowed_values("1-3") == [1, 2, 3]
    assert converter._parse_allowed_values("1=Never; 2=Sometimes") == [1, 2]
    assert converter._parse_allowed_values("left; right") == ["left", "right"]
    assert converter._parse_levels("0=No; 1=Yes") == {"0": "No", "1": "Yes"}
    assert converter._infer_datatype("string", "kg", None, None, None) == "string"
    assert converter._infer_datatype(None, "kg", [1, 2, 3], None, None) == "integer"
    assert converter._infer_datatype(None, "kg", [1.5, 2.5], None, None) == "float"
    assert converter._infer_datatype(None, "n/a", None, None, None) == "string"
    assert converter._infer_datatype(None, "kg", None, 1.5, 5.0) == "float"


def test_process_excel_biometrics_writes_i18n_sidecar_with_header(monkeypatch, tmp_path) -> None:
    frame = pd.DataFrame(
        [
            [
                "variable",
                "description",
                "units",
                "datatype",
                "min",
                "max",
                "allowedvalues",
                "group",
                "alias_of",
                "session",
                "run",
                "scale",
                "test_name",
                "study_description",
                "protocol",
                "instructions_en",
                "instructions_de",
                "reference",
                "estimated_duration",
                "equipment",
                "supervisor",
                "warn_min",
                "warn_max",
            ],
            [
                "pre_cmj_jump_1",
                "How well do you think you have performed this task?",
                "score",
                "integer",
                "1",
                "5",
                "1=very bad; 5=very good",
                "cmj",
                "baseline_jump",
                "visit1",
                "2",
                "1=very bad; 5=very good",
                "Countermovement Jump",
                "Imported biometrics data",
                "Protocol A",
                "Do your best",
                "Geben Sie Ihr Bestes",
                "doi:123",
                "10 min",
                "Force plate",
                "trainer",
                "0",
                "6",
            ],
            [
                "participant_id",
                "Participant code",
                "n/a",
                "string",
                None,
                None,
                None,
                "participants",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ],
            [
                "skip_me",
                "Should not be exported",
                "kg",
                "float",
                None,
                None,
                None,
                "skip",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ],
        ],
        dtype=object,
    )
    monkeypatch.setattr(converter.pd, "read_excel", lambda *args, **kwargs: frame)

    output_dir = tmp_path / "library"
    converter.process_excel_biometrics("dummy.xlsx", str(output_dir), equipment="Fallback device", supervisor="investigator")

    sidecar_path = output_dir / "biometrics-cmj.json"
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert not (output_dir / "biometrics-participants.json").exists()
    assert sidecar["Technical"]["Equipment"] == "Force plate"
    assert sidecar["Technical"]["Supervisor"] == "trainer"
    assert sidecar["Study"]["OriginalName"] == "Countermovement Jump"
    assert sidecar["Study"]["Reference"] == "doi:123"
    assert sidecar["Study"]["EstimatedDuration"] == "10 min"
    assert sidecar["Study"]["Instructions"] == {
        "en": "Do your best",
        "de": "Geben Sie Ihr Bestes",
    }
    assert sidecar["I18n"]["DefaultLanguage"] == "en"

    item = sidecar["pre_cmj_jump_1"]
    assert item["AliasOf"] == "baseline_jump"
    assert item["SessionHint"] == "ses-1"
    assert item["RunHint"] == "run-2"
    assert item["AllowedValues"] == [1, 5]
    assert item["Levels"]["1"]["de"] == "sehr schlecht"
    assert item["WarnMinValue"] == 0.0
    assert item["WarnMaxValue"] == 6.0
    assert item["Description"]["de"] == "Wie gut haben Sie diese Aufgabe Ihrer Meinung nach ausgeführt?"


def test_process_excel_biometrics_supports_positional_rows_and_inferred_hints(monkeypatch, tmp_path) -> None:
    frame = pd.DataFrame(
        [
            [
                "post_balance_2",
                "Measures dynamic balance and anterior reach",
                None,
                None,
                None,
                None,
                "1-3",
                "balance",
                None,
                None,
                None,
            ],
            [
                "mid_balance_score",
                "Participant self-assessment of performance",
                None,
                None,
                None,
                None,
                None,
                "balance",
                None,
                None,
                None,
            ],
        ],
        dtype=object,
    )
    monkeypatch.setattr(converter.pd, "read_excel", lambda *args, **kwargs: frame)

    output_dir = tmp_path / "library"
    converter.process_excel_biometrics("dummy.xlsx", str(output_dir))

    sidecar = json.loads((output_dir / "biometrics-balance.json").read_text(encoding="utf-8"))
    post_item = sidecar["post_balance_2"]
    mid_item = sidecar["mid_balance_score"]

    assert post_item["SessionHint"] == "ses-3"
    assert post_item["RunHint"] == "run-2"
    assert post_item["AllowedValues"] == [1, 2, 3]
    assert post_item["Units"] == "n/a"
    assert post_item["DataType"] == "integer"
    assert sidecar["Study"]["OriginalName"] == "Balance assessment"
    assert sidecar["Study"]["Description"]["de"] == "Importierte balance biometrische Daten"
    assert mid_item["SessionHint"] == "ses-2"


def test_process_excel_biometrics_exits_on_read_error(monkeypatch, tmp_path) -> None:
    def _raise(*args, **kwargs):
        raise ValueError("bad excel")

    monkeypatch.setattr(converter.pd, "read_excel", _raise)

    with pytest.raises(SystemExit) as exc_info:
        converter.process_excel_biometrics("broken.xlsx", str(tmp_path))

    assert exc_info.value.code == 1