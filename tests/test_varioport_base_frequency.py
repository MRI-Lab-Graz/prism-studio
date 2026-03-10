import io
import struct
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import read_varioport_header


def _build_mock_varioport_stream(file_base_rate: int) -> io.BytesIO:
    payload = bytearray(256)

    # Global header fields
    struct.pack_into(">H", payload, 2, 64)  # hdrlen
    struct.pack_into(">H", payload, 4, 64)  # choffs
    struct.pack_into(">B", payload, 6, 7)  # hdrtype
    struct.pack_into(">B", payload, 7, 1)  # chcnt
    struct.pack_into(">H", payload, 20, file_base_rate)  # file_scnrate

    # Single 40-byte channel definition at offset 64
    ch = bytearray(40)
    ch[0:6] = b"EKG   "
    ch[6:10] = b"mV  "
    ch[11] = 1  # dsize_code=1 -> dsize=2
    ch[12] = 2  # scnfac
    ch[14] = 1  # strfac
    struct.pack_into(">H", ch, 16, 1)  # mul
    struct.pack_into(">H", ch, 18, 0)  # doffs
    struct.pack_into(">H", ch, 20, 1)  # div
    struct.pack_into(">I", ch, 24, 0)  # offs_val
    struct.pack_into(">I", ch, 28, 0)  # chlen

    payload[64:104] = ch
    return io.BytesIO(payload)


def test_read_varioport_header_uses_512_default_base_rate():
    stream = _build_mock_varioport_stream(file_base_rate=200)

    _, _, _, channels = read_varioport_header(stream, override_base_freq=None)

    assert len(channels) == 1
    assert channels[0]["fs"] == pytest.approx(256.0)  # 512 / (2 * 1)


def test_read_varioport_header_respects_override_base_rate():
    stream = _build_mock_varioport_stream(file_base_rate=200)

    _, _, _, channels = read_varioport_header(stream, override_base_freq=512)

    assert len(channels) == 1
    assert channels[0]["fs"] == pytest.approx(256.0)  # 512 / (2 * 1)
