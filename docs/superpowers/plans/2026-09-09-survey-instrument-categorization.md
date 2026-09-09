# Survey Instrument Categorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mandatory `Study.Category` field to the 104 official survey instrument templates, enforce it only for the curated library (never for real project data), classify every existing instrument, and group the Survey Questionnaires panel in Studio by category.

**Architecture:** A new closed-enum `Study.Category` field is added to `survey.schema.json`, required by default. A new `x-prism.officialOnlyRequired` schema annotation (the mirror image of the existing `projectOnlyRequired`) is relaxed away specifically when validating real project data, reusing the existing `apply_schema_validation_profile`/`is_official_template_path` machinery already in `schema_manager.py` and `validator.py`. All 104 library files get `Study.Category` written in by an explicit, reviewed mapping. The value propagates into the generated instrument registry index and, on the frontend, groups the Survey Questionnaires list under category headers.

**Tech Stack:** Python (Flask backend, jsonschema), vanilla JS (dynamic `import()`, no bundler), vitest for JS unit tests, pytest for Python tests.

**Spec:** `docs/superpowers/specs/2026-09-09-survey-instrument-categorization-design.md`

## Global Constraints

- `Study.Category` is a single required string, closed `enum` of exactly these 13 values: `Personality & Individual Differences`, `Mood, Anxiety & Clinical Screening`, `Well-being & Life Satisfaction`, `Social, Relationships & Attachment`, `Addictive & Problematic Behaviors`, `Self-Concept & Self-Esteem`, `Aggression, Antisocial & Dark Traits`, `Cognitive & Executive Function`, `Autism & Neurodevelopmental`, `Sleep, Health & Physical`, `Beliefs, Values & Worldview`, `Educational & Occupational`, `Other / Uncategorized`.
- Mandatory only when validating `official/library/survey/*.json` (profile `"official"`); never required on real project `survey.json` sidecars (profile `"project"`).
- Official library JSON files must be rewritten with `json.dumps(data, indent=4, ensure_ascii=False) + "\n"` to match their existing on-disk formatting exactly — verified byte-identical round-trip across all 104 current files before this plan was written.
- No new pip or npm dependencies.
- `app/static/js/survey-generator.js` is a classic (non-module) script. New JS logic must be loaded via dynamic `import()`, matching the existing `sharedApiModuleUrl`/`loadSharedFetchWithApiFallback` pattern in that file — do not add `type="module"` to its `<script>` tag (that would break its existing `document.currentScript`-based URL resolution).
- Follow existing test patterns exactly: Python tests live in `tests/`, import the same way sibling tests in the same file already do; JS tests are colocated as `*.test.js` next to the module they test and run via `npm run test:js`.

---

### Task 1: Schema — add `Study.Category`

**Files:**
- Modify: `app/schemas/stable/survey.schema.json`
- Test: `tests/test_unit.py` (extends `class TestSchemaManager`, ~line 335)

**Interfaces:**
- Produces: `survey.schema.json`'s `properties.Study.properties.Category` (enum) and `properties.Study.required` including `"Category"`, plus `x-prism.officialOnlyRequired.Study == ["Category"]`. Task 2 reads this annotation.

- [ ] **Step 1: Write the failing test**

Add to `class TestSchemaManager` in `tests/test_unit.py` (after `test_load_survey_schema`, ~line 358):

```python
    def test_survey_schema_requires_category_on_study(self, schema_dir):
        """Study.Category is mandatory and a closed enum on the survey schema."""
        schema = load_schema("survey", schema_dir, version="stable")
        study_schema = schema["properties"]["Study"]
        assert "Category" in study_schema["required"]

        category_schema = study_schema["properties"]["Category"]
        assert category_schema["type"] == "string"
        assert len(category_schema["enum"]) == 13
        assert "Personality & Individual Differences" in category_schema["enum"]
        assert "Other / Uncategorized" in category_schema["enum"]

        assert schema["x-prism"]["officialOnlyRequired"]["Study"] == ["Category"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_unit.py::TestSchemaManager::test_survey_schema_requires_category_on_study -v`
Expected: FAIL with a `KeyError: 'Category'` or similar, since the schema doesn't have the field yet.

- [ ] **Step 3: Add the field to the schema**

In `app/schemas/stable/survey.schema.json`, find the top-level `"x-prism"` block (lines 5-10) and add `officialOnlyRequired` as a sibling of `projectOnlyRequired`:

```json
  "x-prism": {
    "projectOnlyRequired": {
      "Technical": ["Language", "Respondent", "AdministrationMethod", "SoftwarePlatform", "SoftwareVersion"],
      "Study": ["TaskName", "LicenseID", "Citation"]
    },
    "officialOnlyRequired": {
      "Study": ["Category"]
    }
  },
```

Then, inside `properties.Study.properties` (after the `"ShortName"` property, ~line 93), add:

```json
        "Category": {
          "type": "string",
          "enum": [
            "Personality & Individual Differences",
            "Mood, Anxiety & Clinical Screening",
            "Well-being & Life Satisfaction",
            "Social, Relationships & Attachment",
            "Addictive & Problematic Behaviors",
            "Self-Concept & Self-Esteem",
            "Aggression, Antisocial & Dark Traits",
            "Cognitive & Executive Function",
            "Autism & Neurodevelopmental",
            "Sleep, Health & Physical",
            "Beliefs, Values & Worldview",
            "Educational & Occupational",
            "Other / Uncategorized"
          ],
          "description": "Primary content-domain grouping for browsing/filtering the instrument library. Mandatory for official library templates; not required on real collected project data."
        },
```

Finally, add `"Category"` to `properties.Study.required` (~line 354), so it reads:

```json
      "required": ["TaskName", "OriginalName", "Citation", "LicenseID", "Category"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_unit.py::TestSchemaManager::test_survey_schema_requires_category_on_study -v`
Expected: PASS

- [ ] **Step 5: Run the full existing schema test class to check for regressions**

Run: `pytest tests/test_unit.py -k Schema -v`
Expected: all PASS (in particular `test_load_survey_schema`, which only checks `Technical` is present, is unaffected).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/stable/survey.schema.json tests/test_unit.py
git commit -m "$(cat <<'EOF'
feat: add mandatory Study.Category field to survey schema

Closed 13-value enum for content-domain grouping of library instruments.
Required by default; a new x-prism.officialOnlyRequired annotation (wired
up in the next commit) will exempt real project data from this requirement.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Validation profile — relax `Category` for real project data

**Files:**
- Modify: `app/src/schema_manager.py`
- Modify: `app/src/validator.py:14,569-585`
- Test: `tests/test_unit.py` (extends `class TestOfficialTemplateRelaxation` ~line 219, and `class TestSchemaManager`)

**Interfaces:**
- Consumes: `x-prism.officialOnlyRequired` from Task 1's schema.
- Produces: `schema_manager.is_official_template_path(path: str | None) -> bool` (new free function, replaces `DatasetValidator._is_official_template_path`) and an extended `apply_schema_validation_profile(schema, profile="project")` that also relaxes `officialOnlyRequired` fields for `profile="project"`. Task 3 reuses both.

- [ ] **Step 1: Write the failing tests**

Add to `class TestSchemaManager` in `tests/test_unit.py`, right after the existing `test_apply_schema_validation_profile_official_relaxes_project_only_fields` (~line 411):

```python
    def test_apply_schema_validation_profile_project_relaxes_official_only_fields(self):
        schema = {
            "type": "object",
            "x-prism": {"officialOnlyRequired": {"Study": ["Category"]}},
            "properties": {
                "Study": {
                    "type": "object",
                    "required": ["Category", "TaskName"],
                }
            },
        }

        adjusted = apply_schema_validation_profile(schema, profile="project")
        assert "Category" not in adjusted["properties"]["Study"]["required"]
        assert "TaskName" in adjusted["properties"]["Study"]["required"]
        # Original schema remains unchanged
        assert "Category" in schema["properties"]["Study"]["required"]

    def test_apply_schema_validation_profile_official_keeps_official_only_fields(self):
        schema = {
            "type": "object",
            "x-prism": {"officialOnlyRequired": {"Study": ["Category"]}},
            "properties": {
                "Study": {
                    "type": "object",
                    "required": ["Category", "TaskName"],
                }
            },
        }

        adjusted = apply_schema_validation_profile(schema, profile="official")
        assert "Category" in adjusted["properties"]["Study"]["required"]
```

Add to `class TestOfficialTemplateRelaxation` in `tests/test_unit.py`, right after `_write_json` (~line 250, before `test_official_library_survey_template_allows_missing_software_platform`):

```python
    def _minimal_survey_schema_with_category(self):
        return {
            "type": "object",
            "x-prism": {"officialOnlyRequired": {"Study": ["Category"]}},
            "properties": {
                "Technical": {
                    "type": "object",
                    "properties": {
                        "StimulusType": {"type": "string"},
                        "FileFormat": {"type": "string"},
                        "SoftwarePlatform": {"type": "string"},
                        "Language": {"type": "string"},
                        "Respondent": {"type": "string"},
                    },
                    "required": [
                        "StimulusType",
                        "FileFormat",
                        "SoftwarePlatform",
                        "Language",
                        "Respondent",
                    ],
                },
                "Study": {
                    "type": "object",
                    "properties": {"Category": {"type": "string"}},
                    "required": ["Category"],
                },
            },
            "required": ["Technical", "Study"],
        }
```

And, in the same class, after `test_official_library_survey_template_allows_missing_software_platform` (~line 285):

```python
    def test_official_library_survey_template_requires_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset_root = tmp_path / "dataset"
            survey_dir = dataset_root / "sub-01" / "ses-01" / "survey"
            survey_dir.mkdir(parents=True, exist_ok=True)
            data_file = survey_dir / "sub-01_ses-01_task-pss_survey.tsv"
            data_file.write_text("pss1\n1\n", encoding="utf-8")

            official_library = tmp_path / "official" / "library" / "survey"
            official_library.mkdir(parents=True, exist_ok=True)
            self._write_json(
                official_library / "task-pss_survey.json",
                {
                    "Technical": {
                        "StimulusType": "Questionnaire",
                        "FileFormat": "tsv",
                        "SoftwarePlatform": "Other",
                        "Language": "en",
                        "Respondent": "self",
                    },
                    "Study": {},
                },
            )

            validator = DatasetValidator(
                schemas={"survey": self._minimal_survey_schema_with_category()},
                library_path=str(official_library),
            )

            issues = validator.validate_sidecar(
                str(data_file),
                "survey",
                str(dataset_root),
            )
            assert issues
            assert "Category" in issues[0][1]

    def test_project_library_survey_template_does_not_require_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dataset_root = tmp_path / "dataset"
            survey_dir = dataset_root / "sub-01" / "ses-01" / "survey"
            survey_dir.mkdir(parents=True, exist_ok=True)
            data_file = survey_dir / "sub-01_ses-01_task-pss_survey.tsv"
            data_file.write_text("pss1\n1\n", encoding="utf-8")

            project_library = tmp_path / "project" / "code" / "library" / "survey"
            project_library.mkdir(parents=True, exist_ok=True)
            self._write_json(
                project_library / "task-pss_survey.json",
                {
                    "Technical": {
                        "StimulusType": "Questionnaire",
                        "FileFormat": "tsv",
                        "SoftwarePlatform": "Other",
                        "Language": "en",
                        "Respondent": "self",
                    },
                    "Study": {},
                },
            )

            validator = DatasetValidator(
                schemas={"survey": self._minimal_survey_schema_with_category()},
                library_path=str(project_library),
            )

            issues = validator.validate_sidecar(
                str(data_file),
                "survey",
                str(dataset_root),
            )
            assert issues == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_unit.py -k "official_only_fields or requires_category or does_not_require_category" -v`
Expected: FAIL — `apply_schema_validation_profile` doesn't know about `officialOnlyRequired` yet, so `Category` is never relaxed for `profile="project"`, and the official-path test fails because `Category` isn't actually being enforced through the validator yet (both new schema behaviors are missing).

- [ ] **Step 3: Extend `apply_schema_validation_profile` in `app/src/schema_manager.py`**

Replace the whole function (lines 167-201) with:

```python
def apply_schema_validation_profile(schema, profile="project"):
    """Return schema adjusted for validation profile.

    Profiles:
    - project: strict schema as defined, except fields listed in
      x-prism.officialOnlyRequired are relaxed (those are only required on
      the curated official library templates, not on real collected data)
    - official: relax fields listed in x-prism.projectOnlyRequired (those
      are only required on real collected project data, not on templates)
    """
    if not isinstance(schema, dict) or profile not in ("project", "official"):
        return schema

    annotations = schema.get("x-prism", {})
    relax_key = "projectOnlyRequired" if profile == "official" else "officialOnlyRequired"
    relax = annotations.get(relax_key, {})
    if not isinstance(relax, dict) or not relax:
        return schema

    adjusted = deepcopy(schema)
    properties = adjusted.get("properties", {})
    if not isinstance(properties, dict):
        return adjusted

    for section, keys in relax.items():
        if not isinstance(keys, list):
            continue
        section_schema = properties.get(section)
        if not isinstance(section_schema, dict):
            continue
        req = section_schema.get("required")
        if not isinstance(req, list):
            continue
        section_schema["required"] = [r for r in req if r not in keys]

    return adjusted
```

Then add the extracted path-check helper right below `DEFAULT_SCHEMA_VERSION` (~line 10), and import `normalize_path` at the top:

```python
import os
import json
from copy import deepcopy

from src.cross_platform import normalize_path

# Default schema version to use when not specified
DEFAULT_SCHEMA_VERSION = "stable"


def is_official_template_path(sidecar_path):
    """Return True when a sidecar path points to the official template library."""
    if not sidecar_path:
        return False
    normalized = normalize_path(sidecar_path).lower()
    return "/official/" in normalized or normalized.endswith("/official")
```

- [ ] **Step 4: Update `app/src/validator.py` to use the extracted helper**

Change the import on line 14 from:

```python
from src.schema_manager import validate_schema_version, apply_schema_validation_profile
```

to:

```python
from src.schema_manager import (
    validate_schema_version,
    apply_schema_validation_profile,
    is_official_template_path,
)
```

Then delete the `_is_official_template_path` method (lines 569-574) entirely, and update `_schema_for_sidecar` (formerly lines 576-585) to:

```python
    def _schema_for_sidecar(self, modality: str, sidecar_path: str | None):
        """Return effective schema for a sidecar by validation profile."""
        schema = self.schemas.get(modality)
        if not schema:
            return None

        profile = "official" if is_official_template_path(sidecar_path) else "project"
        return apply_schema_validation_profile(schema, profile=profile)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_unit.py -k "official_only_fields or requires_category or does_not_require_category or ProfileRelaxation or OfficialTemplateRelaxation" -v`
Expected: all PASS.

- [ ] **Step 6: Run the full existing validator/schema test coverage to check for regressions**

Run: `pytest tests/test_unit.py -v`
Expected: all PASS, including the pre-existing `test_apply_schema_validation_profile_official_relaxes_project_only_fields`, `test_apply_schema_validation_profile_project_keeps_required_fields`, `test_official_library_survey_template_allows_missing_software_platform`, and `test_project_library_survey_template_requires_software_platform`.

- [ ] **Step 7: Commit**

```bash
git add app/src/schema_manager.py app/src/validator.py tests/test_unit.py
git commit -m "$(cat <<'EOF'
feat: relax Study.Category for real project data validation

Extends apply_schema_validation_profile to relax x-prism.officialOnlyRequired
fields under the "project" profile, mirroring the existing "official" profile
relaxation of projectOnlyRequired. Extracts is_official_template_path out of
DatasetValidator into schema_manager so it can be reused by the library
validator in the next commit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Scope `library_validator.check_uniqueness` to the same profile

**Files:**
- Modify: `app/src/library_validator.py:52-99`
- Test: `tests/test_check_uniqueness_survey_normalization.py`

**Interfaces:**
- Consumes: `schema_manager.apply_schema_validation_profile` and `schema_manager.is_official_template_path` from Task 2.
- Produces: `check_uniqueness(library_path)` now schema-checks each file against a profile-adjusted schema instead of the raw schema, so `Category` is only enforced when `library_path` is under `official/`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_check_uniqueness_survey_normalization.py`, after the imports (~line 30):

```python
FAKE_SURVEY_SCHEMA_WITH_CATEGORY = {
    "type": "object",
    "x-prism": {"officialOnlyRequired": {"Study": ["Category"]}},
    "properties": {
        "Study": {
            "type": "object",
            "required": ["Category"],
        }
    },
}
```

Then add these two test functions at the end of the file:

```python
def test_check_uniqueness_requires_category_under_official_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        schema_manager,
        "load_schema",
        lambda name, version=None: (
            FAKE_SURVEY_SCHEMA_WITH_CATEGORY if name == "survey" else {}
        ),
    )
    monkeypatch.setattr(
        normalization_module,
        "normalize_survey_template_for_validation",
        lambda template: template,
    )

    library_dir = tmp_path / "official" / "library" / "survey"
    library_dir.mkdir(parents=True)
    (library_dir / "survey-demo.json").write_text(
        json.dumps({"Study": {}}), encoding="utf-8"
    )

    assert check_uniqueness(str(library_dir)) is False


def test_check_uniqueness_does_not_require_category_outside_official_path(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        schema_manager,
        "load_schema",
        lambda name, version=None: (
            FAKE_SURVEY_SCHEMA_WITH_CATEGORY if name == "survey" else {}
        ),
    )
    monkeypatch.setattr(
        normalization_module,
        "normalize_survey_template_for_validation",
        lambda template: template,
    )

    library_dir = tmp_path / "project" / "code" / "library" / "survey"
    library_dir.mkdir(parents=True)
    (library_dir / "survey-demo.json").write_text(
        json.dumps({"Study": {}}), encoding="utf-8"
    )

    assert check_uniqueness(str(library_dir)) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_check_uniqueness_survey_normalization.py -k official_path -v`
Expected: FAIL on `test_check_uniqueness_requires_category_under_official_path` — `check_uniqueness` currently validates against the raw schema for every path, so the missing-`Category` file would actually already report an error there by coincidence; the real gap is the second test, which currently also fails since there's no profile logic at all, so the raw (un-relaxed) schema also flags the project-path file. Confirm both run and only the second one fails before proceeding (if both pass already, re-check the fixture — the mechanism under test isn't wired up yet).

- [ ] **Step 3: Update `check_uniqueness` in `app/src/library_validator.py`**

Replace the schema-compliance block (lines 54-99) with:

```python
    try:
        from .schema_manager import (
            apply_schema_validation_profile,
            is_official_template_path,
            load_schema,
        )
        from jsonschema import validate, ValidationError
        from src.survey_template_normalization import (
            normalize_survey_template_for_validation,
        )

        print("\nChecking schema compliance...")
        survey_schema = load_schema("survey", version="stable")
        biometrics_schema = load_schema("biometrics", version="stable")

        files = list(Path(library_path).glob("*.json"))
        schema_errors = 0
        for file_path in files:
            if not (
                file_path.name.startswith("survey-")
                or file_path.name.startswith("biometrics-")
            ):
                continue

            is_survey = file_path.name.startswith("survey-")
            base_schema = survey_schema if is_survey else biometrics_schema
            profile = (
                "official" if is_official_template_path(str(file_path)) else "project"
            )
            schema = apply_schema_validation_profile(base_schema, profile=profile)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if is_survey:
                    # Match the Studio Template Editor's Validate/Save
                    # pipeline so a template can't pass in the GUI and then
                    # fail here for reasons the GUI already normalizes away
                    # (implicit numeric level ranges, single-version
                    # VariantID autofill, paper/software platform mapping)
                    # — see docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-4.
                    data = normalize_survey_template_for_validation(data)
                validate(instance=data, schema=schema)
            except ValidationError as e:
                print(f"❌ Schema error in {file_path.name}: {e.message}")
                schema_errors += 1
            except Exception as e:
                print(f"❌ Error reading {file_path.name}: {e}")
                schema_errors += 1

        if schema_errors == 0:
            print("✅ SUCCESS: All files comply with the PRISM schema.")
        else:
            print(f"❌ FAILURE: Found {schema_errors} schema errors.")
            return False

    except ImportError:
        print("⚠️  Skipping schema check (jsonschema not installed).")
```

(Only the `base_schema`/`profile`/`schema` lines and the `is_official_template_path`/`apply_schema_validation_profile` import are new — the rest is unchanged from the current implementation.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_check_uniqueness_survey_normalization.py -v`
Expected: all PASS, including the two new tests and the three pre-existing ones in that file.

- [ ] **Step 5: Commit**

```bash
git add app/src/library_validator.py tests/test_check_uniqueness_survey_normalization.py
git commit -m "$(cat <<'EOF'
fix: scope check_uniqueness schema validation to official/project profile

check_uniqueness is called both against the curated official library and
against arbitrary project output/library directories from the CLI. It was
validating every file against the raw, unmodified schema regardless of
path, which would have made Study.Category (and any future
officialOnlyRequired field) incorrectly mandatory for project-local
template libraries too.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Classify all 104 official library instruments

**Files:**
- Create: `scripts/classify_survey_categories.py`
- Modify: all 104 files under `official/library/survey/survey-*.json` (via running the script)
- Test: `tests/test_survey_library_categories.py`

**Interfaces:**
- Produces: every `official/library/survey/survey-*.json` file has a `Study.Category` key set to one of the Task 1 enum values. Task 5 (registry propagation) and Task 6 (backend exposure) depend on this being complete.

- [ ] **Step 1: Write the failing test**

Create `tests/test_survey_library_categories.py`:

```python
"""Every official library instrument must carry a valid Study.Category
(see docs/superpowers/specs/2026-09-09-survey-instrument-categorization-design.md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "app") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "app"))

from app.src.schema_manager import load_schema

LIBRARY_DIR = REPO_ROOT / "official" / "library" / "survey"


def test_every_library_instrument_has_a_valid_category():
    schema = load_schema("survey", str(REPO_ROOT / "app" / "schemas"), version="stable")
    valid_categories = set(schema["properties"]["Study"]["properties"]["Category"]["enum"])

    files = sorted(LIBRARY_DIR.glob("survey-*.json"))
    assert len(files) > 0

    missing = []
    invalid = []
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        category = data.get("Study", {}).get("Category")
        if not category:
            missing.append(path.name)
        elif category not in valid_categories:
            invalid.append((path.name, category))

    assert missing == [], f"Files missing Study.Category: {missing}"
    assert invalid == [], f"Files with an invalid Study.Category: {invalid}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_survey_library_categories.py -v`
Expected: FAIL — `missing` will list all (or nearly all) 104 filenames, since none have `Study.Category` yet.

- [ ] **Step 3: Write the classification script**

Create `scripts/classify_survey_categories.py`:

```python
"""Write Study.Category into every official library survey template.

One-off classification pass — see
docs/superpowers/specs/2026-09-09-survey-instrument-categorization-design.md
for how the taxonomy and the mapping below were derived. Safe to re-run: it
overwrites Study.Category idempotently and leaves every other key untouched.
Run with:

    python scripts/classify_survey_categories.py
"""

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from pathlib import Path  # noqa: E402

SURVEY_DIR = Path(REPO_ROOT) / "official" / "library" / "survey"

PERSONALITY = "Personality & Individual Differences"
MOOD_ANXIETY = "Mood, Anxiety & Clinical Screening"
WELLBEING = "Well-being & Life Satisfaction"
SOCIAL = "Social, Relationships & Attachment"
ADDICTIVE = "Addictive & Problematic Behaviors"
SELF_CONCEPT = "Self-Concept & Self-Esteem"
DARK_TRAITS = "Aggression, Antisocial & Dark Traits"
COGNITIVE = "Cognitive & Executive Function"
AUTISM = "Autism & Neurodevelopmental"
HEALTH = "Sleep, Health & Physical"
BELIEFS = "Beliefs, Values & Worldview"
EDUCATIONAL = "Educational & Occupational"

TASK_NAME_TO_CATEGORY = {
    "aai": MOOD_ANXIETY,
    "agg-a": DARK_TRAITS,
    "aiss": PERSONALITY,
    "amas": EDUCATIONAL,
    "aq10": AUTISM,
    "ard": SOCIAL,
    "bes": SELF_CONCEPT,
    "bes-alt": EDUCATIONAL,
    "bfas": ADDICTIVE,
    "bfi-s": PERSONALITY,
    "bhps": PERSONALITY,
    "bis": PERSONALITY,
    "bite": MOOD_ANXIETY,
    "bpaq": DARK_TRAITS,
    "brcs": WELLBEING,
    "brs": WELLBEING,
    "bsas": SOCIAL,
    "bsri": PERSONALITY,
    "burnout": EDUCATIONAL,
    "cabs": DARK_TRAITS,
    "ccms": PERSONALITY,
    "ccss": SOCIAL,
    "cfs": COGNITIVE,
    "cia": MOOD_ANXIETY,
    "cirens": HEALTH,
    "cns": BELIEFS,
    "csjas": BELIEFS,
    "cudos": MOOD_ANXIETY,
    "cudq": ADDICTIVE,
    "dass": MOOD_ANXIETY,
    "dass21": MOOD_ANXIETY,
    "dmq-r": ADDICTIVE,
    "ehi": HEALTH,
    "ei": COGNITIVE,
    "erq": MOOD_ANXIETY,
    "fs": WELLBEING,
    "gad7": MOOD_ANXIETY,
    "gaene": BELIEFS,
    "gas": ADDICTIVE,
    "gp": EDUCATIONAL,
    "gq6": WELLBEING,
    "grit-s": PERSONALITY,
    "gse": SELF_CONCEPT,
    "gsqs": HEALTH,
    "gtps": MOOD_ANXIETY,
    "hs": SELF_CONCEPT,
    "hsc7": HEALTH,
    "hsns": DARK_TRAITS,
    "hsq": PERSONALITY,
    "isc": PERSONALITY,
    "las": SOCIAL,
    "lies": DARK_TRAITS,
    "loneliness-3": SOCIAL,
    "lot-r": WELLBEING,
    "lsrp": DARK_TRAITS,
    "masi": EDUCATIONAL,
    "maslow": BELIEFS,
    "mate": BELIEFS,
    "mhc-sf": WELLBEING,
    "ncs-6": COGNITIVE,
    "nmp-q": ADDICTIVE,
    "o-life": MOOD_ANXIETY,
    "oci-r": MOOD_ANXIETY,
    "ohq": WELLBEING,
    "pci": EDUCATIONAL,
    "phq9": MOOD_ANXIETY,
    "pios": MOOD_ANXIETY,
    "piu": ADDICTIVE,
    "piuq": ADDICTIVE,
    "pnsmd": SOCIAL,
    "pss": MOOD_ANXIETY,
    "pts": WELLBEING,
    "rei": COGNITIVE,
    "rosenberg": SELF_CONCEPT,
    "rrs": MOOD_ANXIETY,
    "saam": SOCIAL,
    "saps": PERSONALITY,
    "sbs-10": BELIEFS,
    "scsr": SELF_CONCEPT,
    "sd3": DARK_TRAITS,
    "sf-mjs": SOCIAL,
    "shyness": PERSONALITY,
    "skep": BELIEFS,
    "smd": ADDICTIVE,
    "soc-3": SELF_CONCEPT,
    "sos": ADDICTIVE,
    "spane": WELLBEING,
    "spq": MOOD_ANXIETY,
    "sqs": HEALTH,
    "sses": SELF_CONCEPT,
    "swlls": SOCIAL,
    "swls": WELLBEING,
    "tai5": EDUCATIONAL,
    "tipi": PERSONALITY,
    "trust": SOCIAL,
    "tsis": COGNITIVE,
    "type-d": PERSONALITY,
    "uplas": SOCIAL,
    "vast": DARK_TRAITS,
    "webexec": COGNITIVE,
    "wellbeing": WELLBEING,
    "wellbeing-multi": WELLBEING,
    "who5": WELLBEING,
    "zkpq": PERSONALITY,
}


def main() -> None:
    updated = 0
    skipped = []
    for path in sorted(SURVEY_DIR.glob("survey-*.json")):
        task_name = path.stem[len("survey-"):]
        category = TASK_NAME_TO_CATEGORY.get(task_name)
        if category is None:
            skipped.append(path.name)
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("Study", {})["Category"] = category
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False) + "\n")
        updated += 1

    print(f"Wrote Category to {updated} files.")
    if skipped:
        print(f"Skipped (no mapping entry): {skipped}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the script**

Run: `python scripts/classify_survey_categories.py`
Expected output: `Wrote Category to 104 files.` with no "Skipped" line. If a "Skipped" line appears, the `TASK_NAME_TO_CATEGORY` dict is missing an entry for a file that exists on disk — cross-check with `ls official/library/survey/survey-*.json` and add the missing mapping before proceeding.

- [ ] **Step 5: Verify only the expected line was added per file**

Run: `git diff --stat official/library/survey/ | tail -5`
Expected: 104 files changed, each with `1 insertion(+), 1 deletion(-)` (the deletion is the old closing `}` of the `Study` object gaining a trailing comma) or `2 insertions(+), 1 deletion(-)` for files where `Study` was the last key before another top-level section. Spot-check two or three files with `git diff official/library/survey/survey-aai.json` to confirm no reformatting noise — only the new `"Category": "..."` line (plus a comma) should appear.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_survey_library_categories.py -v`
Expected: PASS.

- [ ] **Step 7: Run the library validator end-to-end against the real library**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, 'app')
from app.src.library_validator import check_uniqueness
ok = check_uniqueness('official/library/survey')
sys.exit(0 if ok else 1)
"
```
Expected: exits 0, prints `✅ SUCCESS: All files comply with the PRISM schema.` (Task 3 ensures this now includes the `Category` check for this official path; if it fails, the schema error message will name the offending file.)

- [ ] **Step 8: Commit**

```bash
git add scripts/classify_survey_categories.py official/library/survey/ tests/test_survey_library_categories.py
git commit -m "$(cat <<'EOF'
feat: classify all 104 official library instruments into content categories

Applies the corpus-derived taxonomy from the design spec via a reviewable,
explicit TaskName -> Category mapping (scripts/classify_survey_categories.py).
Every file gets exactly one Study.Category; none use the "Other /
Uncategorized" fallback.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Propagate `Category` into the instrument registry

**Files:**
- Modify: `src/instrument_registry.py:22-34` (i.e. `app/src/instrument_registry.py` is not a thing — the live file is `src/instrument_registry.py`, confirmed single-copy, no dual-tree mirror)
- Modify: `app/schemas/stable/instrument-registry.schema.json`
- Modify (generated): `official/library/survey/index.json`
- Test: `tests/test_instrument_registry.py`

**Interfaces:**
- Consumes: `Study.Category` written by Task 4.
- Produces: `build_registry_index(...)["Instruments"][task_name]["Category"]`. Task 6 does not depend on this (it reads the source `survey-*.json` files directly), but the generated `index.json` is what a future UI/API consumer would use for a lightweight bulk listing.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_instrument_registry.py`, after `test_known_instrument_resolves_expected_fields` (~line 34):

```python
def test_known_instrument_includes_category():
    index = build_registry_index(OFFICIAL_SURVEY_DIR)
    aai = index["Instruments"]["aai"]
    assert aai["Category"] == "Mood, Anxiety & Clinical Screening"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_instrument_registry.py::test_known_instrument_includes_category -v`
Expected: FAIL with `KeyError: 'Category'`.

- [ ] **Step 3: Update `build_registry_index` in `src/instrument_registry.py`**

In the loop building `instruments[task_name]` (~lines 63-73), add `"Category"` to the dict:

```python
        instruments[task_name] = {
            "TaskName": task_name,
            "SourceFile": json_path.name,
            "ShortName": study.get("ShortName"),
            "OriginalName": study.get("OriginalName"),
            "Category": study.get("Category"),
            "DOI": study.get("DOI", ""),
            "Citation": study.get("Citation", ""),
            "Version": study.get("Version"),
            "Versions": [str(v) for v in (study.get("Versions") or [])],
            "Variants": _extract_variants(study),
            "Vocabulary": None,
        }
```

- [ ] **Step 4: Update `instrument-registry.schema.json`**

In `app/schemas/stable/instrument-registry.schema.json`, add a `Category` property to `Instruments.additionalProperties.properties` (after `"OriginalName"`, ~line 23):

```json
          "Category": {"type": ["string", "null"], "description": "Study.Category from the source template, when present."},
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_instrument_registry.py -v`
Expected: all PASS.

- [ ] **Step 6: Regenerate the real registry index**

Run: `python scripts/generate_instrument_registry.py`
Expected output: `Wrote official/library/survey/index.json (104 instruments)`.

- [ ] **Step 7: Spot-check the regenerated index**

Run: `python3 -c "import json; d = json.load(open('official/library/survey/index.json')); print(d['Instruments']['aai']['Category'])"`
Expected: `Mood, Anxiety & Clinical Screening`

- [ ] **Step 8: Commit**

```bash
git add src/instrument_registry.py app/schemas/stable/instrument-registry.schema.json official/library/survey/index.json tests/test_instrument_registry.py
git commit -m "$(cat <<'EOF'
feat: propagate Study.Category into the generated instrument registry

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Expose `Category` to the Survey Generator backend API

**Files:**
- Modify: `app/src/web/blueprints/tools_template_info_helpers.py:154-168`
- Test: `tests/test_extract_template_info_category.py`

**Interfaces:**
- Consumes: `Study.Category` from the source `survey-*.json` file (works for any file, official or project — the field is simply passed through if present, defaulting to `""` like the other `study_info` fields).
- Produces: `extract_template_info(...)["study"]["Category"]`, consumed by `app/static/js/survey-generator.js` in Task 8 as `file.study.Category`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract_template_info_category.py`:

```python
"""extract_template_info must pass Study.Category through to the frontend
so the Survey Questionnaires panel can group by it (Task 8)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.tools_template_info_helpers import extract_template_info


def test_extract_template_info_includes_category_when_present(tmp_path):
    template_path = tmp_path / "survey-demo.json"
    template_path.write_text(
        json.dumps({"Study": {"Category": "Well-being & Life Satisfaction"}}),
        encoding="utf-8",
    )

    info = extract_template_info(str(template_path), "survey-demo.json")

    assert info["study"]["Category"] == "Well-being & Life Satisfaction"


def test_extract_template_info_defaults_category_to_empty_string(tmp_path):
    template_path = tmp_path / "survey-demo.json"
    template_path.write_text(json.dumps({"Study": {}}), encoding="utf-8")

    info = extract_template_info(str(template_path), "survey-demo.json")

    assert info["study"]["Category"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract_template_info_category.py -v`
Expected: FAIL with `KeyError: 'Category'`.

- [ ] **Step 3: Update `extract_template_info`**

In `app/src/web/blueprints/tools_template_info_helpers.py`, add `"Category"` to the `study_info` dict (~line 154):

```python
            study_info = {
                "Authors": study.get("Authors", []),
                "Category": study.get("Category", ""),
                "Citation": study.get("Citation", ""),
                "DOI": study.get("DOI", ""),
                "License": study.get("License", ""),
                "LicenseID": study.get("LicenseID", ""),
                "LicenseURL": study.get("LicenseURL", ""),
                "ItemCount": study.get("ItemCount"),
                "AgeRange": study.get("AgeRange", ""),
                "AdministrationTime": study.get("AdministrationTime", ""),
                "ScoringTime": study.get("ScoringTime", ""),
                "Norming": study.get("Norming", ""),
                "Reliability": study.get("Reliability", ""),
                "Validity": study.get("Validity", ""),
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extract_template_info_category.py -v`
Expected: PASS.

- [ ] **Step 5: Run the broader survey-generator backend test coverage to check for regressions**

Run: `pytest tests/test_survey_generator_library_paths.py tests/test_tools_survey_customizer_handlers.py -v`
Expected: all PASS (these tests use a locally-stubbed `_extract_template_info`, not the real one, so they're unaffected — but running them confirms nothing else in that area broke).

- [ ] **Step 6: Commit**

```bash
git add app/src/web/blueprints/tools_template_info_helpers.py tests/test_extract_template_info_category.py
git commit -m "$(cat <<'EOF'
feat: expose Study.Category through extract_template_info

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Pure category-grouping module (frontend)

**Files:**
- Create: `app/static/js/modules/survey/category-grouping.js`
- Test: `app/static/js/modules/survey/category-grouping.test.js`

**Interfaces:**
- Produces: `SURVEY_CATEGORY_ORDER: string[]` and `groupFilesByCategory(files: {study?: {Category?: string}}[]) -> {category: string, files: object[]}[]`, sorted by the fixed category order (unknown categories sorted after all known ones, alphabetically among themselves), with files missing a category grouped under `"Uncategorized"`. Task 8 imports both.

- [ ] **Step 1: Write the failing test**

Create `app/static/js/modules/survey/category-grouping.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { groupFilesByCategory, SURVEY_CATEGORY_ORDER } from './category-grouping.js';

describe('groupFilesByCategory', () => {
    it('groups files under their Study.Category, preserving within-group order', () => {
        const files = [
            { filename: 'a', study: { Category: 'Well-being & Life Satisfaction' } },
            { filename: 'b', study: { Category: 'Personality & Individual Differences' } },
            { filename: 'c', study: { Category: 'Personality & Individual Differences' } },
        ];
        const groups = groupFilesByCategory(files);
        expect(groups.map(g => g.category)).toEqual([
            'Personality & Individual Differences',
            'Well-being & Life Satisfaction',
        ]);
        expect(groups[0].files.map(f => f.filename)).toEqual(['b', 'c']);
    });

    it('falls back to Uncategorized when Category is missing or study is absent', () => {
        const files = [{ filename: 'x', study: {} }, { filename: 'y' }];
        const groups = groupFilesByCategory(files);
        expect(groups).toEqual([
            { category: 'Uncategorized', files: [files[0], files[1]] },
        ]);
    });

    it('sorts categories outside SURVEY_CATEGORY_ORDER after all known ones', () => {
        const files = [
            { filename: 'z', study: { Category: 'Some New Category' } },
            { filename: 'a', study: { Category: 'Autism & Neurodevelopmental' } },
        ];
        const groups = groupFilesByCategory(files);
        expect(groups.map(g => g.category)).toEqual([
            'Autism & Neurodevelopmental',
            'Some New Category',
        ]);
    });

    it('exports exactly the 13 schema categories in schema order', () => {
        expect(SURVEY_CATEGORY_ORDER).toEqual([
            'Personality & Individual Differences',
            'Mood, Anxiety & Clinical Screening',
            'Well-being & Life Satisfaction',
            'Social, Relationships & Attachment',
            'Addictive & Problematic Behaviors',
            'Self-Concept & Self-Esteem',
            'Aggression, Antisocial & Dark Traits',
            'Cognitive & Executive Function',
            'Autism & Neurodevelopmental',
            'Sleep, Health & Physical',
            'Beliefs, Values & Worldview',
            'Educational & Occupational',
            'Other / Uncategorized',
        ]);
    });

    it('returns an empty array for an empty or missing file list', () => {
        expect(groupFilesByCategory([])).toEqual([]);
        expect(groupFilesByCategory(undefined)).toEqual([]);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:js -- category-grouping`
Expected: FAIL — `category-grouping.js` doesn't exist yet.

- [ ] **Step 3: Write the module**

Create `app/static/js/modules/survey/category-grouping.js`:

```js
export const SURVEY_CATEGORY_ORDER = [
    'Personality & Individual Differences',
    'Mood, Anxiety & Clinical Screening',
    'Well-being & Life Satisfaction',
    'Social, Relationships & Attachment',
    'Addictive & Problematic Behaviors',
    'Self-Concept & Self-Esteem',
    'Aggression, Antisocial & Dark Traits',
    'Cognitive & Executive Function',
    'Autism & Neurodevelopmental',
    'Sleep, Health & Physical',
    'Beliefs, Values & Worldview',
    'Educational & Occupational',
    'Other / Uncategorized',
];

const UNCATEGORIZED_LABEL = 'Uncategorized';

function categoryOrderIndex(name) {
    const idx = SURVEY_CATEGORY_ORDER.indexOf(name);
    return idx === -1 ? SURVEY_CATEGORY_ORDER.length : idx;
}

export function groupFilesByCategory(files) {
    const groups = new Map();
    (files || []).forEach(file => {
        const category = (file.study && file.study.Category) || UNCATEGORIZED_LABEL;
        if (!groups.has(category)) groups.set(category, []);
        groups.get(category).push(file);
    });

    return Array.from(groups.entries())
        .sort((a, b) => {
            const diff = categoryOrderIndex(a[0]) - categoryOrderIndex(b[0]);
            return diff !== 0 ? diff : a[0].localeCompare(b[0]);
        })
        .map(([category, groupFiles]) => ({ category, files: groupFiles }));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:js -- category-grouping`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/modules/survey/category-grouping.js app/static/js/modules/survey/category-grouping.test.js
git commit -m "$(cat <<'EOF'
feat: add pure groupFilesByCategory helper for Survey Questionnaires panel

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Wire category grouping into the Survey Questionnaires panel

**Files:**
- Modify: `app/static/js/survey-generator.js:1-30,140-263,266-309,314-328`
- Modify: `app/static/css/survey-generator.css`

**Interfaces:**
- Consumes: `groupFilesByCategory`/`SURVEY_CATEGORY_ORDER` from Task 7, `file.study.Category` from Task 6.
- Produces: no new exported interface — this is the final DOM-facing task. Manual browser verification closes it out (no automated DOM test exists for this file today; this task follows that established precedent).

- [ ] **Step 1: Add the dynamic-import loader for the grouping module**

In `app/static/js/survey-generator.js`, right after the existing `sharedApiModuleUrl`/`loadSharedFetchWithApiFallback` block (~line 28-41), add:

```js
    const categoryGroupingModuleUrl = new URL('./modules/survey/category-grouping.js', surveyGeneratorScriptUrl).href;
    let categoryGroupingModulePromise = null;

    function loadCategoryGrouping() {
        if (!categoryGroupingModulePromise) {
            categoryGroupingModulePromise = import(categoryGroupingModuleUrl);
        }
        return categoryGroupingModulePromise;
    }
```

- [ ] **Step 2: Add a category badge to `createTemplateRow`**

In `createTemplateRow` (~line 182-189), add the category badge to the existing badge row, right after the `itemCount` badge:

```js
                        <span class="tpl-name">${escapeHtml(origName || file.filename)}</span>
                        ${sourceBadgeHtml(file.source)}
                        <span class="badge bg-secondary" style="font-size:0.65rem;">${itemCount} items</span>
                        ${file.study && file.study.Category ? `<span class="badge bg-info text-dark" style="font-size:0.6rem;">${escapeHtml(file.study.Category)}</span>` : ''}
                        ${fileLangs.map(l => `<span class="lang-badge ${l === currentLanguage ? 'lang-badge-available' : ''}" style="font-size:0.6rem;">${l.toUpperCase()}</span>`).join('')}
```

- [ ] **Step 3: Make `renderLibrary` group the `survey` section by category**

Replace `renderLibrary` (~lines 266-309) with:

```js
    async function renderLibrary() {
        if (!currentLibraryData) return;
        const { groupFilesByCategory } = await loadCategoryGrouping();

        let hasAnyFiles = false;
        let hasAnyVisible = false;
        Object.keys(sectionConfig).forEach(key => {
            const cfg = sectionConfig[key];
            const container = document.getElementById(cfg.container);
            const listEl = document.getElementById(cfg.list);
            const countEl = document.getElementById(cfg.count);
            listEl.innerHTML = '';

            const files = currentLibraryData[key];
            if (files && files.length > 0) {
                hasAnyFiles = true;
                // Count files that have all export languages
                const visibleFiles = files.filter(f => hasAllExportLanguages(f.detected_languages || ['en']));
                const totalFiles = files.length;

                container.classList.remove('d-none');
                countEl.textContent = visibleFiles.length < totalFiles
                    ? `(${visibleFiles.length}/${totalFiles})`
                    : `(${totalFiles})`;

                let renderedIndex = 0;
                const appendRow = (file) => {
                    const row = createTemplateRow(file, renderedIndex++, key);
                    listEl.appendChild(row);
                    if (hasAllExportLanguages(file.detected_languages || ['en'])) hasAnyVisible = true;
                };

                if (key === 'survey') {
                    groupFilesByCategory(files).forEach(({ category, files: groupFiles }) => {
                        const header = document.createElement('div');
                        header.className = 'tpl-category-header';
                        header.textContent = `${category} (${groupFiles.length})`;
                        listEl.appendChild(header);
                        groupFiles.forEach(appendRow);
                    });
                } else {
                    files.forEach(appendRow);
                }
            } else {
                container.classList.add('d-none');
            }
        });

        if (hasAnyFiles) {
            libraryContent.classList.remove('d-none');
            libraryEmpty.classList.add('d-none');
        } else {
            libraryContent.classList.add('d-none');
            libraryEmpty.classList.remove('d-none');
        }
        updateGenerateBtn();
        applySearchFilter();
    }
```

- [ ] **Step 4: Make `applySearchFilter` collapse empty category headers**

Replace `applySearchFilter` (~lines 314-328) with:

```js
    function applySearchFilter() {
        const query = templateSearch.value.trim().toLowerCase();
        document.querySelectorAll('.tpl-row').forEach(row => {
            if (!query) {
                row.classList.remove('tpl-hidden-search');
                return;
            }
            const fn = row.dataset.filename || '';
            const on = row.dataset.originalName || '';
            const desc = row.dataset.description || '';
            const match = fn.includes(query) || on.includes(query) || desc.includes(query);
            if (match) row.classList.remove('tpl-hidden-search');
            else row.classList.add('tpl-hidden-search');
        });

        document.querySelectorAll('.tpl-category-header').forEach(header => {
            let sibling = header.nextElementSibling;
            let hasVisibleRow = false;
            while (sibling && !sibling.classList.contains('tpl-category-header')) {
                if (sibling.classList.contains('tpl-row') && !sibling.classList.contains('tpl-hidden-search')) {
                    hasVisibleRow = true;
                    break;
                }
                sibling = sibling.nextElementSibling;
            }
            header.classList.toggle('d-none', !hasVisibleRow);
        });
    }
```

- [ ] **Step 5: Add the category header style**

In `app/static/css/survey-generator.css`, after the `.tpl-desc` rule block, add:

```css
    .tpl-category-header {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: #6c757d;
        padding: 0.5rem 0.2rem 0.15rem;
        margin-top: 0.3rem;
        border-bottom: 1px solid #e9ecef;
    }
    .tpl-category-header:first-child {
        margin-top: 0;
    }
```

- [ ] **Step 6: Run the full JS test suite to check for regressions**

Run: `npm run test:js`
Expected: all PASS, including `category-grouping.test.js` from Task 7 (this file has no other automated tests to regress).

- [ ] **Step 7: Manually verify in the browser**

Run: `python prism-studio.py` (starts Studio on port 5001), open `http://localhost:5001` in a browser, navigate to the Survey Generator page (Prepare Data → Survey Generator, or whatever nav path currently reaches `survey_generator.html`).

Verify:
- The Survey Questionnaires list now shows category headers (e.g. "Mood, Anxiety & Clinical Screening (16)") grouping the instruments, in the fixed schema order.
- Each survey row shows a category badge alongside the existing Global/Matrix/items/language badges.
- Typing in the template search box still filters rows correctly, and a category header with zero remaining visible rows disappears.
- "Select all" / "Clear" for the Survey Questionnaires section still selects/clears every row regardless of which category group it's in.
- The Biometrics & Physio and Other sections are unaffected (still flat lists, no headers).

Stop the server (Ctrl+C) once verified.

- [ ] **Step 8: Commit**

```bash
git add app/static/js/survey-generator.js app/static/css/survey-generator.css
git commit -m "$(cat <<'EOF'
feat: group Survey Questionnaires panel by instrument category

Loads the new category-grouping module via dynamic import (matching this
file's existing pattern for shared/api.js, since it's a classic script,
not a module). Search filtering and select-all/clear behavior are
unchanged; empty category groups collapse under an active search filter.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** Schema + enum (Task 1) · library-only validation via `officialOnlyRequired` (Task 2) · `check_uniqueness` profile scoping, a gap the spec's Task 6 test-location note didn't originally spell out but is required for the "library-only" decision to actually hold (Task 3) · classify all 104 instruments (Task 4) · registry propagation (Task 5) · UI badge + grouping (Tasks 6-8). All spec sections have a corresponding task.

**Type/name consistency:** `is_official_template_path`, `apply_schema_validation_profile`, `groupFilesByCategory`, `SURVEY_CATEGORY_ORDER`, `study_info["Category"]` / `file.study.Category` are used identically across every task that references them.

**Ordering:** Task 1 (schema) intentionally lands before Task 4 (classification), which temporarily makes the schema stricter than the on-disk data for one commit in the sequence — verified safe: no existing test or CI check (`tests/verify_repo.py`'s `check_library_uniqueness` checks variable-name uniqueness only, not schema compliance) runs full schema validation against the real `official/library/survey/` directory before Task 4 adds the missing field.
