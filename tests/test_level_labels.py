"""Labels containing commas must survive the codebook import, and losses are reported."""

import openpyxl
import pytest

from src.converters.excel_base import level_problems, parse_levels
from src.converters.excel_to_biometrics import process_excel_biometrics
from src.converters.excel_to_survey import extract_excel_templates


@pytest.mark.parametrize(
    "cell,expected",
    [
        (
            "2 = öfter, 3 = meistens, die ganze Zeit",
            {"2": "öfter", "3": "meistens, die ganze Zeit"},
        ),
        (
            "0 = ja, 1 = ja, aber woanders, 2 = nein, selbes Zimmer, nicht selbes Bett",
            {"0": "ja", "1": "ja, aber woanders", "2": "nein, selbes Zimmer, nicht selbes Bett"},
        ),
        (
            "1 = gar nicht, 2 = 0,5 Jahre, 3 = 1 Jahr",
            {"1": "gar nicht", "2": "0,5 Jahre", "3": "1 Jahr"},
        ),
        # anchor-only scales: the bare codes in between are not part of the label
        ("0 = nie, 1, 2, 3, 4, 5 = immer", {"0": "nie", "5": "immer"}),
        ("A1 = gar nicht, A2, A3, A4 = sehr", {"A1": "gar nicht", "A4": "sehr"}),
        ("0=never,1,2,3,4=always", {"0": "never", "4": "always"}),
        ("4 = always, 3, 2, 1, 0 = never", {"4": "always", "0": "never"}),
        ("m=man, with beard, f=woman", {"m": "man, with beard", "f": "woman"}),
        ("1=Never, 2=Sometimes", {"1": "Never", "2": "Sometimes"}),
        ("1=a, b; 2=c", {"1": "a, b", "2": "c"}),
    ],
)
def test_parse_levels_keeps_whole_labels(cell, expected):
    assert parse_levels(cell) == expected


def test_clean_cells_report_nothing():
    assert level_problems("0 = nie, 1, 2, 3, 4, 5 = immer") == []
    assert level_problems("1=a; 2=b") == []
    assert level_problems("cm") == []
    assert level_problems(None) == []


def test_dropped_text_and_equal_labels_are_reported():
    assert "Scale:" in level_problems("Scale:, 1=a, 2=b")[0]
    assert "other" in level_problems("1=a; other")[0]
    assert "ja" in level_problems("0=ja; 1=ja")[0]
    assert "1" in level_problems("1=a; 1=b")[0]


def test_a_code_swallowed_into_a_label_is_reported():
    assert "'='" in level_problems("1=yes, not sure=maybe")[0]


def test_import_reports_problems(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Variable name", "Description_de", "Scaling"])
    ws.append(["ABC01", "Frage", "0 = ja, 1 = ja"])
    path = tmp_path / "book.xlsx"
    wb.save(path)

    found = []
    extract_excel_templates(path, check_collisions=False, problems=found)

    assert len(found) == 1 and found[0].startswith("ABC01")
    assert found[0] in capsys.readouterr().out


def test_biometrics_import_reports_problems(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["item_id", "description", "units", "scaling"])
    ws.append(["jump_1", "Jump", "score", "0=ja;1=ja"])
    path = tmp_path / "bio.xlsx"
    wb.save(path)

    process_excel_biometrics(str(path), str(tmp_path / "out"))

    assert "jump_1: several codes" in capsys.readouterr().out
