import os
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
app_path = str(root / "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.project_ready import REQUIRED_FIELDS
from src.web.blueprints.projects_metadata_helpers import CREATION_BLOCKING_FIELDS


def test_backend_constant_derives_from_required_fields():
    derived = {}
    for section, field in REQUIRED_FIELDS:
        derived.setdefault(section, set()).add(field)
    assert CREATION_BLOCKING_FIELDS == derived


def test_js_has_no_private_copy():
    js = (root / "app/static/js/modules/projects/metadata.js").read_text(encoding="utf-8")
    assert not re.search(r"creationBlockingFields\s*=\s*\{\s*Basics", js)


def test_get_response_exposes_creation_blocking_fields():
    src = (root / "app/src/web/blueprints/projects_study_metadata_handlers.py").read_text(encoding="utf-8")
    assert '"creation_blocking_fields"' in src
