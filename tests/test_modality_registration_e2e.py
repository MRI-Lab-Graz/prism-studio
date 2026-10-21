import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = REPO / "examples" / "modality_proposal"

_VALIDATE = (
    "import json, sys\n"
    "sys.path.insert(0, 'app/src'); sys.path.insert(1, '.')\n"
    "from runner import validate_dataset\n"
    "issues, stats = validate_dataset(sys.argv[1], run_bids=False)\n"
    "print(json.dumps({'errors': [i[1] for i in issues if i[0] == 'ERROR'],\n"
    "                  'modalities': stats.modalities}))\n"
)


def _copy_repo(dest: Path) -> Path:
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(REPO / "app" / "src", dest / "app" / "src", ignore=ignore)
    shutil.copytree(REPO / "app" / "schemas", dest / "app" / "schemas")
    shutil.copytree(REPO / "src", dest / "src", ignore=ignore)
    return dest


def _validate(repo: Path, dataset: Path) -> dict:
    run = subprocess.run(
        [sys.executable, "-c", _VALIDATE, str(dataset)],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_following_registration_md_makes_the_fixture_validate(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO / "app" / "src"))
    from src.modality_contribution import build_modality_artifacts, read_proposal

    proposal = read_proposal(EXAMPLE_DIR / "bloodwork.yml")
    out = tmp_path / "proposal"
    build_modality_artifacts(
        proposal, EXAMPLE_DIR / "bloodwork_sample.tsv", EXAMPLE_DIR / "bloodwork.yml", out
    )
    repo = _copy_repo(tmp_path / "repo")
    fixture = out / "fixture"

    # Before registration the validator silently skips the unknown modality
    # folder: no errors, but nothing is counted as bloodwork data either.
    before = _validate(repo, fixture)
    assert "bloodwork" not in before["modalities"]

    # Apply the maintainer steps exactly as REGISTRATION.md prints them.
    md = (out / "REGISTRATION.md").read_text(encoding="utf-8")
    snippet = json.loads(re.search(r"```json\n(.*?)\n```", md, re.S).group(1))
    stable = repo / "app" / "schemas" / "stable"
    shutil.copyfile(out / "bloodwork.schema.json", stable / "bloodwork.schema.json")
    entities_path = stable / "entities.schema.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["modalities"].update(snippet)
    entities_path.write_text(json.dumps(entities, indent=2), encoding="utf-8")

    after = _validate(repo, fixture)
    assert after["errors"] == []
    assert after["modalities"].get("bloodwork", 0) >= 1


def test_extension_registration_makes_the_fixture_validate(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO / "app" / "src"))
    from src.modality_contribution import build_modality_artifacts, read_proposal

    proposal = read_proposal(EXAMPLE_DIR / "bloodpanel.yml")
    out = tmp_path / "proposal"
    build_modality_artifacts(proposal, EXAMPLE_DIR / "bloodpanel_sample.tsv", EXAMPLE_DIR / "bloodpanel.yml", out)
    repo = _copy_repo(tmp_path / "repo")
    md = (out / "REGISTRATION.md").read_text(encoding="utf-8")
    snippet = json.loads(re.search(r"```json\n(.*?)\n```", md, re.S).group(1))
    entities_path = repo / "app" / "schemas" / "stable" / "entities.schema.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["modalities"].update(snippet)
    entities_path.write_text(json.dumps(entities, indent=2), encoding="utf-8")

    after = _validate(repo, out / "fixture")
    assert after["errors"] == []
    assert after["modalities"].get("biometrics", 0) >= 1
