"""A small uploaded ZIP can expand to gigabytes (and was read fully into memory)."""

import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.web import upload


class _Upload:
    def __init__(self, data: bytes):
        self._data = data

    def save(self, path):
        Path(path).write_bytes(self._data)


def _zip(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return buf.getvalue()


def test_normal_zip_is_extracted(tmp_path):
    data = _zip({"ds/dataset_description.json": '{"Name": "x"}'})
    root = upload.process_zip_upload(_Upload(data), str(tmp_path), "ds.zip")
    assert (Path(root) / "dataset_description.json").is_file()


def test_zip_that_expands_beyond_the_cap_is_rejected_before_extracting(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "MAX_ZIP_UNCOMPRESSED_BYTES", 1000)
    data = _zip({"ds/dataset_description.json": "{}", "ds/big.json": "0" * 5000})  # tiny when deflated
    assert len(data) < 1000
    with pytest.raises(ValueError, match="too large"):
        upload.process_zip_upload(_Upload(data), str(tmp_path), "bomb.zip")
    assert not (tmp_path / "ds" / "big.json").exists()
