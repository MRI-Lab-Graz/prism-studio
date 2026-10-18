"""A semicolon-separated .csv (German Excel export) must import with "Auto-detect"."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import pytest

pytest.importorskip("pandas")
pytest.importorskip("flask")

from src.web.blueprints.conversion_participants_io import _read_participants_input_table  # noqa: E402

ROWS = "participant_id;age;iq\n" + "".join(f"P{i};{20 + i};10{i % 10},5\n" for i in range(1, 12))


def _read(tmp_path, separator_option, name="people.csv"):
    path = tmp_path / name
    path.write_text(ROWS, encoding="utf-8")
    return _read_participants_input_table(
        input_path=path, suffix=path.suffix, sheet_arg=0, separator_option=separator_option
    )


def test_auto_detect_finds_the_semicolon(tmp_path):
    assert list(_read(tmp_path, "auto").columns) == ["participant_id", "age", "iq"]


def test_an_explicit_separator_is_still_honoured(tmp_path):
    assert list(_read(tmp_path, "semicolon").columns) == ["participant_id", "age", "iq"]


def _client():
    import io  # noqa: F401
    from flask import Flask

    from src.web.blueprints import conversion_participants_blueprint as module

    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(module.conversion_participants_bp)
    return app.test_client()


@pytest.mark.parametrize("content", [b"", b"participant_id,age\n"])
def test_an_unusable_file_is_a_400_that_says_why(content):
    import io

    response = _client().post(
        "/api/participants-detect-id",
        data={"file": (io.BytesIO(content), "people.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "empty" in response.get_json()["error"].lower()
