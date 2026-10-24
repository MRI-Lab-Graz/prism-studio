"""LimeSurvey stores numbers as DECIMAL(30,10): '23.0000000000' must read as '23'."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.participants_converter import load_participant_source  # noqa: E402


def test_trailing_decimal_zeros_are_trimmed(tmp_path):
    source = tmp_path / "source.tsv"
    source.write_text(
        "id\tAlter\tvo2max\tlabel\n"
        "1\t23.0000000000\t44.5000000000\tv1.0x\n"
        "2\t-7.0\t29.9\tn/a\n",
        encoding="utf-8",
    )

    df, _ = load_participant_source(source)

    assert list(df["Alter"].astype(str)) == ["23", "-7"]
    assert list(df["vo2max"].astype(str)) == ["44.5", "29.9"]
    assert list(df["label"].astype(str))[0] == "v1.0x"
