import json
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from src.batch_convert import _create_physio_sidecar


def test_create_physio_sidecar_emits_prism_required_keys(tmp_path):
    source = tmp_path / "sub-01_task-rest.edf"
    source.write_bytes(b"EDF")

    output_json = tmp_path / "task-rest_physio.json"
    _create_physio_sidecar(
        source,
        output_json,
        task_name="task-rest",
        sampling_rate=256.0,
        extra_meta={"Channels": ["ekg", "resp", "Marker"]},
    )

    sidecar = json.loads(output_json.read_text(encoding="utf-8"))

    assert "Technical" in sidecar
    assert sidecar["Technical"]["SamplingFrequency"] == 256.0
    assert sidecar["Technical"]["Columns"] == ["ekg", "resp", "Marker"]
    assert "Metadata" in sidecar
    assert sidecar["Metadata"]["SchemaVersion"] == "1.2.0"
    assert "CreationDate" in sidecar["Metadata"]
    assert sidecar["Study"]["TaskName"] == "rest"
