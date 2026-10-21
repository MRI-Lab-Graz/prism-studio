import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "src"))

from schema_manager import load_all_schemas  # noqa: E402


def _copy_schemas(tmp_path: Path) -> str:
    dest = tmp_path / "schemas"
    shutil.copytree(REPO / "app" / "schemas", dest)
    return str(dest)


def _archive_survey(schema_dir: str, version: str) -> None:
    stable = json.loads((Path(schema_dir) / "stable" / "survey.schema.json").read_text())
    stable["version"] = version
    target = Path(schema_dir) / "archive" / "survey"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{version}.schema.json").write_text(json.dumps(stable))


def test_default_load_is_unchanged(tmp_path):
    schemas = load_all_schemas(_copy_schemas(tmp_path))
    assert schemas["survey"]["_validator_info"]["version_tag"] == "stable"


def test_one_modality_can_be_loaded_at_an_archived_version(tmp_path):
    schema_dir = _copy_schemas(tmp_path)
    _archive_survey(schema_dir, "1.0.0")
    schemas = load_all_schemas(schema_dir, modality_versions={"survey": "1.0.0"})
    assert schemas["survey"]["_validator_info"]["schema_version"] == "1.0.0"
    assert schemas["biometrics"]["_validator_info"]["version_tag"] == "stable"


def test_aliases_follow_the_overridden_schema(tmp_path):
    schema_dir = _copy_schemas(tmp_path)
    archive = Path(schema_dir) / "archive" / "physio"
    archive.mkdir(parents=True)
    phys = json.loads((Path(schema_dir) / "stable" / "physio.schema.json").read_text())
    phys["version"] = "1.0.0"
    (archive / "1.0.0.schema.json").write_text(json.dumps(phys))
    schemas = load_all_schemas(schema_dir, modality_versions={"physio": "1.0.0"})
    assert "physiological" not in schemas
    assert schemas["physio"]["version"] == "1.0.0"
