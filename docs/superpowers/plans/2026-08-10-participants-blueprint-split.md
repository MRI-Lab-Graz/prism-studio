# Split conversion_participants_blueprint.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 2,748-line `app/src/web/blueprints/conversion_participants_blueprint.py` into five focused files, and consolidate two near-duplicate participants.tsv/participants.json-writing code paths into one shared function.

**Architecture:** Move existing helper functions verbatim into four new sibling files grouped by concern (`_io`, `_mapping`, `_merge`, `_convert`), leaving `conversion_participants_blueprint.py` as thin route handlers that import from them. Then use TDD to extract four genuinely new functions — two that consolidate duplicated logic (`_check_existing_participants_files`, `_write_participants_outputs`) and two that pull inline blocks out of `api_participants_preview`'s 393-line body (`_resolve_additional_preview_columns`, `_diagnose_preview_error`).

**Tech Stack:** Python 3, Flask, pytest, pandas.

## Global Constraints

- Flat sibling files only, no nested package — matches the existing convention (`conversion_physio_handlers.py`, `conversion_participants_helpers.py` already live this way). Source: approved design spec.
- Tasks 1–4 are pure code motion: zero behavior change. The full existing suite (`tests/test_web_blueprints_conversion.py` and the participants converter test files) must stay green **without modification** after each task.
- Tasks 5–8 each extract one genuinely new function. Per `CLAUDE.md`'s "extract and add a dedicated test" rule and this session's TDD skill: write the failing test first, watch it fail for the right reason, then implement.
- After creating each new module, verify it has no shadow file under top-level `src/` per `CLAUDE.md`'s drift-check: `python3 -c "import src.web.blueprints.<module> as m; print(m.__file__)"` must print the path under `app/src/web/blueprints/`.
- No new dependencies. No behavior changes beyond the two named consolidations.

---

### Task 1: Extract upload/IO helpers into `conversion_participants_io.py`

**Files:**
- Create: `app/src/web/blueprints/conversion_participants_io.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py`
- Test: `tests/test_web_blueprints_conversion.py` (regression, unmodified)

**Interfaces:**
- Produces (importable from `conversion_participants_io.py`): `_save_participants_upload_to_temp`, `_normalize_separator_option`, `_expected_delimiter_for_suffix`, `_read_participants_input_table`, `_get_excel_sheet_metadata`, `_resolve_participants_sheet_arg`, `_classify_time_style`, `_detect_mixed_time_style_columns`, `_format_mixed_time_style_message`, plus module constants `_SUPPORTED_PARTICIPANTS_UPLOAD_SUFFIXES`, `_SUPPORTED_PARTICIPANTS_UPLOAD_MESSAGE`.

- [ ] **Step 1: Confirm the regression baseline is green**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`
Expected: all currently-passing participants tests PASS (this is your baseline — note the count).

- [ ] **Step 2: Create `conversion_participants_io.py`**

Cut these from `conversion_participants_blueprint.py` (currently lines 70–306, but locate by function name — grep `^def _save_participants_upload_to_temp` etc., since exact line numbers will differ once you start editing) and paste into the new file, verbatim, in the same relative order: `_save_participants_upload_to_temp`, `_normalize_separator_option`, `_expected_delimiter_for_suffix`, `_read_participants_input_table`, `_get_excel_sheet_metadata`, `_resolve_participants_sheet_arg`, `_classify_time_style`, `_detect_mixed_time_style_columns`, `_format_mixed_time_style_message`. Also cut the two module-level constants `_SUPPORTED_PARTICIPANTS_UPLOAD_SUFFIXES` and `_SUPPORTED_PARTICIPANTS_UPLOAD_MESSAGE` (currently lines 56–65).

Add this import block at the top of the new file:

```python
import re
import shutil
import tempfile
from pathlib import Path

from flask import request
from werkzeug.utils import secure_filename

from src.converters.file_reader import infer_tabular_kind, read_tabular_file

from .conversion_utils import (
    expected_delimiter_for_suffix as _shared_expected_delimiter_for_suffix,
)
from .conversion_utils import normalize_separator_option as _shared_normalize_separator
```

- [ ] **Step 3: Update `conversion_participants_blueprint.py`'s imports**

Remove `import re`, `import shutil`, `import tempfile` from the top of `conversion_participants_blueprint.py` if nothing else in the file still uses them (check with `grep -n 're\.\|shutil\.\|tempfile\.' conversion_participants_blueprint.py` — `shutil.rmtree` is still used in the route bodies for temp-dir cleanup, so keep `import shutil`; drop `re`/`tempfile` only if unused elsewhere). Remove the now-unused `from .conversion_utils import (expected_delimiter_for_suffix as ..., normalize_separator_option as ...)` and `from werkzeug.utils import secure_filename` and `from src.converters.file_reader import infer_tabular_kind, read_tabular_file` lines (these move to `conversion_participants_io.py`).

Add:

```python
from .conversion_participants_io import (
    _detect_mixed_time_style_columns,
    _expected_delimiter_for_suffix,
    _format_mixed_time_style_message,
    _get_excel_sheet_metadata,
    _normalize_separator_option,
    _read_participants_input_table,
    _resolve_participants_sheet_arg,
    _save_participants_upload_to_temp,
)
```

(`_classify_time_style` and the two `_SUPPORTED_PARTICIPANTS_UPLOAD_*` constants are only used inside `conversion_participants_io.py` itself — don't import them into the blueprint.)

- [ ] **Step 4: Verify the module resolves live (drift check)**

Run: `python3 -c "import src.web.blueprints.conversion_participants_io as m; print(m.__file__)"`
Expected: prints a path ending in `app/src/web/blueprints/conversion_participants_io.py`.

- [ ] **Step 5: Run the regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`
Expected: same pass count as Step 1, zero failures.

- [ ] **Step 6: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_io.py app/src/web/blueprints/conversion_participants_blueprint.py
git commit -m "refactor: extract participants upload/IO helpers into conversion_participants_io.py"
```

---

### Task 2: Extract mapping/schema helpers into `conversion_participants_mapping.py`

**Files:**
- Create: `app/src/web/blueprints/conversion_participants_mapping.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py`
- Test: `tests/test_web_blueprints_conversion.py` (regression, unmodified)

**Interfaces:**
- Consumes: `_read_participants_input_table` from `conversion_participants_io` (Task 1).
- Produces: `_normalize_column_token`, `_rekey_neurobagel_schema_to_output_columns`, `_canonicalize_preview_id_column`, `_parse_requested_column_list`, `_resolve_excluded_output_columns`, `_collect_preview_column_values`, `_load_existing_participants_schema`, `_load_saved_participants_mapping`, `_normalize_legacy_participants_mapping`, `_resolve_web_participant_import_mapping`.

- [ ] **Step 1: Confirm baseline green**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`

- [ ] **Step 2: Create `conversion_participants_mapping.py`**

Cut these functions (locate by name; originally lines 315–888 before Task 1's edits shifted things) verbatim, same order: `_normalize_column_token`, `_rekey_neurobagel_schema_to_output_columns`, `_canonicalize_preview_id_column`, `_parse_requested_column_list`, `_resolve_excluded_output_columns`, `_collect_preview_column_values`, `_load_existing_participants_schema`, `_load_saved_participants_mapping`, `_normalize_legacy_participants_mapping`, `_resolve_web_participant_import_mapping`.

Add this import block:

```python
import json
import re
from pathlib import Path

from flask import session

from src.participants_id_selection import resolve_participants_id_selection
from src.participants_paths import participants_mapping_candidates

from .conversion_participants_helpers import (
    _detect_repeated_questionnaire_prefixes,
    _filter_participant_relevant_columns,
    _is_likely_questionnaire_column,
    _load_project_participant_filter_config,
    _load_survey_template_item_ids,
    _normalize_column_name,
)
from .conversion_participants_io import _read_participants_input_table
from .conversion_utils import resolve_effective_library_path
```

- [ ] **Step 3: Update `conversion_participants_blueprint.py`'s imports**

Remove the now-unused `from .conversion_participants_helpers import (...)` block and `from src.participants_id_selection import resolve_participants_id_selection` and `from src.participants_paths import participants_mapping_candidates` and `from .conversion_utils import resolve_effective_library_path` lines — check first with `grep -n` whether the blueprint still calls any of `_detect_repeated_questionnaire_prefixes`, `_filter_participant_relevant_columns`, `_generate_neurobagel_schema`, `_is_likely_questionnaire_column`, `_load_project_participant_filter_config`, `_load_survey_template_item_ids`, `_normalize_column_name`, `resolve_effective_library_path` directly in a route body — `api_participants_preview` does call `_load_project_participant_filter_config`, `_load_survey_template_item_ids`, `_detect_repeated_questionnaire_prefixes`, `_is_likely_questionnaire_column`, `_normalize_column_name`, `_filter_participant_relevant_columns`, `_generate_neurobagel_schema`, and `resolve_effective_library_path` directly (these stay imported in the blueprint — they are not part of this move, they belong to `conversion_participants_helpers.py` which already existed before this refactor).

Add:

```python
from .conversion_participants_mapping import (
    _canonicalize_preview_id_column,
    _collect_preview_column_values,
    _parse_requested_column_list,
    _rekey_neurobagel_schema_to_output_columns,
    _resolve_web_participant_import_mapping,
)
```

(`_normalize_column_token`, `_resolve_excluded_output_columns`, `_load_existing_participants_schema`, `_load_saved_participants_mapping`, `_normalize_legacy_participants_mapping` are only called internally within `conversion_participants_mapping.py` and by `conversion_participants_merge.py` in Task 3 — don't import them into the blueprint.)

- [ ] **Step 4: Verify drift check**

Run: `python3 -c "import src.web.blueprints.conversion_participants_mapping as m; print(m.__file__)"`
Expected: path ends in `app/src/web/blueprints/conversion_participants_mapping.py`.

- [ ] **Step 5: Run regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`
Expected: same pass count as Step 1.

- [ ] **Step 6: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_mapping.py app/src/web/blueprints/conversion_participants_blueprint.py
git commit -m "refactor: extract participants mapping/schema helpers into conversion_participants_mapping.py"
```

---

### Task 3: Extract merge helpers into `conversion_participants_merge.py`

**Files:**
- Create: `app/src/web/blueprints/conversion_participants_merge.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py`
- Test: `tests/test_web_blueprints_conversion.py` (regression, unmodified)

**Interfaces:**
- Consumes: `_resolve_excluded_output_columns`, `_rekey_neurobagel_schema_to_output_columns`, `_canonicalize_preview_id_column`, `_load_existing_participants_schema`, `_parse_requested_column_list`, `_resolve_web_participant_import_mapping` from `conversion_participants_mapping` (Task 2); `_normalize_separator_option`, `_expected_delimiter_for_suffix`, `_save_participants_upload_to_temp`, `_resolve_participants_sheet_arg` from `conversion_participants_io` (Task 1).
- Produces: `_build_participants_merge_schema_preview`, `_project_relative_merge_paths`, `_parse_participants_merge_request`, `_participants_id_required_response`, `_validate_participants_merge_request_context`, `_build_existing_participants_preview_payload`, `_convert_existing_participants_files`.

- [ ] **Step 1: Confirm baseline green**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`

- [ ] **Step 2: Create `conversion_participants_merge.py`**

Cut these functions verbatim, same order: `_build_participants_merge_schema_preview`, `_project_relative_merge_paths`, `_parse_participants_merge_request`, `_participants_id_required_response`, `_validate_participants_merge_request_context`, `_build_existing_participants_preview_payload`, `_convert_existing_participants_files`.

`_resolve_excluded_output_columns` (from Task 2's mapping.py) is used inside this group but was correctly left in `conversion_participants_mapping.py` — import it, don't move it.

Add this import block:

```python
import json
from pathlib import Path

from flask import Response, jsonify, request, session

from src.converters.file_reader import read_tabular_file

from .conversion_participants_helpers import (
    _generate_neurobagel_schema,
    _load_project_participant_filter_config,
)
from .conversion_participants_io import (
    _expected_delimiter_for_suffix,
    _normalize_separator_option,
    _resolve_participants_sheet_arg,
    _save_participants_upload_to_temp,
)
from .conversion_participants_mapping import (
    _canonicalize_preview_id_column,
    _load_existing_participants_schema,
    _parse_requested_column_list,
    _rekey_neurobagel_schema_to_output_columns,
    _resolve_excluded_output_columns,
    _resolve_web_participant_import_mapping,
)
from .conversion_utils import resolve_effective_library_path
```

Note: `_merge_neurobagel_schema_for_columns` (imported at the top of the original blueprint as `merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns` from `src.participants_backend`) is used by `_convert_existing_participants_files` — add `from src.participants_backend import merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns` to this import block too.

- [ ] **Step 3: Update `conversion_participants_blueprint.py`'s imports**

Add:

```python
from .conversion_participants_merge import (
    _build_existing_participants_preview_payload,
    _build_participants_merge_schema_preview,
    _convert_existing_participants_files,
    _parse_participants_merge_request,
    _participants_id_required_response,
    _project_relative_merge_paths,
    _validate_participants_merge_request_context,
)
```

Leave the blueprint's own `from src.participants_backend import (...)` block as-is except you may now remove `merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns` if nothing left in the blueprint file calls it directly (check with `grep -n _merge_neurobagel_schema_for_columns conversion_participants_blueprint.py` — it's still called from `api_participants_convert`'s file-mode branch and `_run_participants_convert_job`, both of which move in Tasks 4 and 6, so for now leave this import in place; it will be cleaned up naturally once those bodies move).

- [ ] **Step 4: Verify drift check**

Run: `python3 -c "import src.web.blueprints.conversion_participants_merge as m; print(m.__file__)"`
Expected: path ends in `app/src/web/blueprints/conversion_participants_merge.py`.

- [ ] **Step 5: Run regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`
Expected: same pass count as Step 1.

- [ ] **Step 6: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_merge.py app/src/web/blueprints/conversion_participants_blueprint.py
git commit -m "refactor: extract participants merge helpers into conversion_participants_merge.py"
```

---

### Task 4: Extract async job worker into `conversion_participants_convert.py`

**Files:**
- Create: `app/src/web/blueprints/conversion_participants_convert.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py`
- Test: `tests/test_web_blueprints_conversion.py` (regression, unmodified)

**Interfaces:**
- Consumes: `_rekey_neurobagel_schema_to_output_columns` from `conversion_participants_mapping`; `_convert_existing_participants_files` from `conversion_participants_merge`.
- Produces: `_run_participants_convert_job`, `_participants_job_store` (module-level `ConversionJobStore` instance — this moves here from the blueprint to avoid a circular import, since the blueprint's routes need to call it too and this module will own the convert-job logic).

- [ ] **Step 1: Confirm baseline green**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`

- [ ] **Step 2: Create `conversion_participants_convert.py`**

Cut `_run_participants_convert_job` (the worker-thread body). Also cut the module-level line `_participants_job_store = ConversionJobStore(log_level_key="level")` from the blueprint.

Add this import block:

```python
import json
import shutil
from typing import Any

from src.participants_backend import convert_dataset_participants
from src.participants_backend import (
    merge_neurobagel_schema_for_columns as _merge_neurobagel_schema_for_columns,
)

from .conversion_job_store import ConversionJobStore
from .conversion_participants_mapping import _rekey_neurobagel_schema_to_output_columns
from .conversion_participants_merge import _convert_existing_participants_files

_participants_job_store = ConversionJobStore(log_level_key="level")
```

- [ ] **Step 3: Update `conversion_participants_blueprint.py`'s imports**

Remove `from .conversion_job_store import ConversionJobStore` (no longer used directly in the blueprint). Add:

```python
from .conversion_participants_convert import (
    _participants_job_store,
    _run_participants_convert_job,
)
```

- [ ] **Step 4: Verify drift check**

Run: `python3 -c "import src.web.blueprints.conversion_participants_convert as m; print(m.__file__)"`
Expected: path ends in `app/src/web/blueprints/conversion_participants_convert.py`.

- [ ] **Step 5: Run regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v`
Expected: same pass count as Step 1.

- [ ] **Step 6: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_convert.py app/src/web/blueprints/conversion_participants_blueprint.py
git commit -m "refactor: extract participants async job worker into conversion_participants_convert.py"
```

---

### Task 5: TDD — consolidate the duplicated "existing files" guard into `_check_existing_participants_files`

**Files:**
- Modify: `app/src/web/blueprints/conversion_participants_convert.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py` (routes `api_participants_convert`, `api_participants_convert_start`)
- Create: `tests/test_conversion_participants_convert_helpers.py`

**Interfaces:**
- Produces: `_check_existing_participants_files(project_root: Path, mode: str, force_overwrite: bool) -> tuple[Path, Path, list[str], tuple[Response, int] | None]` — returns `(participants_tsv, participants_json, existing_files, error_response)`; `error_response` is `None` when the caller may proceed, otherwise the `(jsonify(...), 409)` tuple the route should return immediately.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_conversion_participants_convert_helpers.py`:

```python
from src.web.blueprints.conversion_participants_convert import (
    _check_existing_participants_files,
)


def test_no_existing_files_returns_no_error(tmp_path):
    participants_tsv, participants_json, existing_files, error_response = (
        _check_existing_participants_files(tmp_path, mode="file", force_overwrite=False)
    )

    assert participants_tsv == tmp_path / "participants.tsv"
    assert participants_json == tmp_path / "participants.json"
    assert existing_files == []
    assert error_response is None


def test_existing_tsv_without_force_overwrite_blocks_with_409(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\n")

    _, _, existing_files, error_response = _check_existing_participants_files(
        tmp_path, mode="file", force_overwrite=False
    )

    assert existing_files == [str(tmp_path / "participants.tsv")]
    assert error_response is not None
    _, status_code = error_response
    assert status_code == 409


def test_existing_tsv_with_force_overwrite_allows_proceed():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / "participants.tsv").write_text("participant_id\n")

        _, _, existing_files, error_response = _check_existing_participants_files(
            project_root, mode="file", force_overwrite=True
        )

        assert existing_files == [str(project_root / "participants.tsv")]
        assert error_response is None


def test_existing_mode_bypasses_force_overwrite_requirement(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\n")

    _, _, existing_files, error_response = _check_existing_participants_files(
        tmp_path, mode="existing", force_overwrite=False
    )

    assert error_response is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversion_participants_convert_helpers.py -v`
Expected: FAIL with `ImportError: cannot import name '_check_existing_participants_files'`.

- [ ] **Step 3: Implement `_check_existing_participants_files`**

Add to `conversion_participants_convert.py` (add `from pathlib import Path` and `from flask import jsonify, Response` to its imports if not already present):

```python
def _check_existing_participants_files(
    project_root: Path, mode: str, force_overwrite: bool
) -> tuple[Path, Path, list[str], "tuple[Response, int] | None"]:
    """Return (participants_tsv, participants_json, existing_files, error_response).

    error_response is None when the request may proceed; otherwise it's the
    (response, status_code) tuple the caller should return immediately.
    Only blocks on real participant data (participants.tsv). A schema-only
    participants.json saved earlier from the annotation widget has no rows
    to lose, so it doesn't require force_overwrite confirmation.
    """
    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    existing_files = []
    if participants_tsv.exists():
        existing_files.append(str(participants_tsv))
    if participants_json.exists():
        existing_files.append(str(participants_json))

    if participants_tsv.exists() and not force_overwrite and mode != "existing":
        error_response = (
            jsonify(
                {
                    "error": "Participant files already exist. Enable 'force overwrite' to replace them.",
                    "existing_files": existing_files,
                }
            ),
            409,
        )
        return participants_tsv, participants_json, existing_files, error_response

    return participants_tsv, participants_json, existing_files, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversion_participants_convert_helpers.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Wire into `api_participants_convert`**

In `conversion_participants_blueprint.py`, replace the block (originally lines 2148–2169, locate by content):

```python
    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    existing_files = []
    if participants_tsv.exists():
        existing_files.append(str(participants_tsv))
    if participants_json.exists():
        existing_files.append(str(participants_json))

    # Only block on real participant data (participants.tsv). A schema-only
    # participants.json saved earlier from the annotation widget has no rows
    # to lose, so it shouldn't require force_overwrite confirmation.
    if participants_tsv.exists() and not force_overwrite and mode != "existing":
        return (
            jsonify(
                {
                    "error": "Participant files already exist. Enable 'force overwrite' to replace them.",
                    "existing_files": existing_files,
                }
            ),
            409,
        )
```

with:

```python
    participants_tsv, participants_json, existing_files, error_response = (
        _check_existing_participants_files(project_root, mode, force_overwrite)
    )
    if error_response is not None:
        return error_response
```

Do the same replacement in `api_participants_convert_start` for its equivalent block (originally lines 2422–2440).

Add `_check_existing_participants_files` to the blueprint's `from .conversion_participants_convert import (...)` block.

- [ ] **Step 6: Run full regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v && pytest tests/test_conversion_participants_convert_helpers.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_convert.py app/src/web/blueprints/conversion_participants_blueprint.py tests/test_conversion_participants_convert_helpers.py
git commit -m "refactor: consolidate duplicated existing-files guard into _check_existing_participants_files"
```

---

### Task 6: TDD — consolidate the duplicated participants.tsv/json writer into `_write_participants_outputs`

**Files:**
- Modify: `app/src/web/blueprints/conversion_participants_convert.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py` (route `api_participants_convert`, function `_run_participants_convert_job`)
- Modify: `tests/test_conversion_participants_convert_helpers.py`

**Interfaces:**
- Consumes: `_rekey_neurobagel_schema_to_output_columns` (already imported in Task 4), `_merge_neurobagel_schema_for_columns` (already imported in Task 4), `ParticipantsConverter` from `src.participants_converter` (local import inside the function, matching existing pattern).
- Produces: `_write_participants_outputs(project_root: Path, input_path: Path, mapping: dict, converter_separator: str, sheet_arg, participants_tsv: Path, participants_json: Path, neurobagel_schema: dict, existing_files: list[str], log_msg) -> dict[str, Any]`. Raises `ValueError("Conversion failed")` if the converter reports failure. Returns a dict **without** a `"log"` key — callers merge that in themselves.

- [ ] **Step 1: Write the failing test**

This is the one function in this plan that drives real conversion logic, so test it with a real `ParticipantsConverter` run (no mocks), following the pattern in `tests/test_participants_converter_edge_cases.py`. Append to `tests/test_conversion_participants_convert_helpers.py`:

```python
import json
import tempfile
from pathlib import Path

import pandas as pd

from src.web.blueprints.conversion_participants_convert import (
    _write_participants_outputs,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_write_participants_outputs_creates_tsv_and_json():
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        source = project_root / "participants_source.csv"
        _write_csv(source, [{"ID": "001", "age": "21"}, {"ID": "002", "age": "22"}])

        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                }
            },
        }
        participants_tsv = project_root / "participants.tsv"
        participants_json = project_root / "participants.json"
        logs = []

        result = _write_participants_outputs(
            project_root=project_root,
            input_path=source,
            mapping=mapping,
            converter_separator="auto",
            sheet_arg=0,
            participants_tsv=participants_tsv,
            participants_json=participants_json,
            neurobagel_schema={},
            existing_files=[],
            log_msg=lambda level, message: logs.append((level, message)),
        )

        assert result["status"] == "success"
        assert result["files_created"] == [str(participants_tsv), str(participants_json)]
        assert result["overwrote_existing"] is False
        assert participants_tsv.exists()

        written = json.loads(participants_json.read_text())
        assert "participant_id" in written
        assert written["participant_id"]["Description"] == "Participant identifier (sub-<label>)"


def test_write_participants_outputs_raises_on_conversion_failure():
    import pytest

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        source = project_root / "participants_source.csv"
        # No ID-like column at all -- matches the proven failure fixture in
        # tests/test_participants_converter_edge_cases.py::
        # test_convert_fails_without_recoverable_participant_id. A column
        # named "ID" with blank values instead gets its blank rows dropped
        # (success=True, fewer rows), not a hard failure -- don't use that.
        _write_csv(source, [{"age": "21"}, {"age": "22"}])

        mapping = {
            "version": "1.0",
            "mappings": {
                "age": {
                    "source_column": "age",
                    "standard_variable": "age",
                    "type": "string",
                }
            },
        }

        with pytest.raises(ValueError, match="Conversion failed"):
            _write_participants_outputs(
                project_root=project_root,
                input_path=source,
                mapping=mapping,
                converter_separator="auto",
                sheet_arg=0,
                participants_tsv=project_root / "participants.tsv",
                participants_json=project_root / "participants.json",
                neurobagel_schema={},
                existing_files=[],
                log_msg=lambda level, message: None,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversion_participants_convert_helpers.py -v -k write_participants_outputs`
Expected: FAIL with `ImportError: cannot import name '_write_participants_outputs'`.

- [ ] **Step 3: Implement `_write_participants_outputs`**

Add to `conversion_participants_convert.py`:

```python
def _write_participants_outputs(
    project_root: Path,
    input_path: Path,
    mapping: dict,
    converter_separator: str,
    sheet_arg,
    participants_tsv: Path,
    participants_json: Path,
    neurobagel_schema: dict,
    existing_files: list[str],
    log_msg,
) -> dict[str, Any]:
    """Run ParticipantsConverter, write participants.tsv/json, return the
    success result payload (no "log" key -- callers merge that in)."""
    from src.participants_converter import ParticipantsConverter

    converter = ParticipantsConverter(project_root, log_callback=log_msg)
    success, df, messages = converter.convert_participant_data(
        source_file=str(input_path),
        mapping=mapping,
        output_file=str(participants_tsv),
        separator=converter_separator,
        sheet=sheet_arg,
    )

    for msg in messages:
        log_msg("INFO", msg)

    if not success or df is None:
        raise ValueError("Conversion failed")

    df.to_csv(participants_tsv, sep="\t", index=False)
    log_msg("INFO", f"✓ Created {participants_tsv.name}")

    participants_json_data: dict[str, Any] = {str(col): {} for col in df.columns}

    if neurobagel_schema:
        try:
            aligned_neurobagel_schema = _rekey_neurobagel_schema_to_output_columns(
                neurobagel_schema=neurobagel_schema,
                mapping=mapping if isinstance(mapping, dict) else None,
                allowed_columns=list(df.columns),
            )
            participants_json_data, merged_count = _merge_neurobagel_schema_for_columns(
                participants_json_data,
                aligned_neurobagel_schema,
                list(df.columns),
                log_callback=log_msg,
            )
            log_msg(
                "INFO",
                f"Merged NeuroBagel annotations for {merged_count} participants.tsv column(s)",
            )
        except Exception as e:
            log_msg("WARNING", f"Could not merge NeuroBagel schema: {str(e)}")

    fallback_descriptions = {
        "participant_id": "Participant identifier (sub-<label>)",
        "age": "Age of participant",
    }
    for col in df.columns:
        col_name = str(col)
        field = participants_json_data.setdefault(col_name, {})
        current_description = str(field.get("Description") or "").strip()
        if current_description:
            continue
        field["Description"] = fallback_descriptions.get(col_name, f"Participant {col_name}")

    with open(participants_json, "w", encoding="utf-8") as f:
        json.dump(participants_json_data, f, indent=2, ensure_ascii=False)

    log_msg("INFO", f"✓ Created {participants_json.name}")

    return {
        "status": "success",
        "files_created": [str(participants_tsv), str(participants_json)],
        "output_directory": str(project_root),
        "overwrote_existing": bool(existing_files),
        "overwritten_files": existing_files if existing_files else [],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversion_participants_convert_helpers.py -v`
Expected: PASS (6 tests total in this file so far).

- [ ] **Step 5: Wire into `api_participants_convert`'s file-mode branch**

`converter = ParticipantsConverter(project_root, log_callback=log_msg)` (originally line 2203) is instantiated *before* the mapping-resolution logic (`_resolve_web_participant_import_mapping`, the `id_resolution`/`detected_id_col`/`mapping` checks) — that resolution logic is route-specific request handling, not part of the duplicated writer, and must stay in the route untouched. `_write_participants_outputs` creates its own `ParticipantsConverter` internally (Step 3), so this line is now dead — delete it (not replace it):

```python
                converter = ParticipantsConverter(project_root, log_callback=log_msg)
```

Leave everything between it and `success, df, messages = converter.convert_participant_data(` (the mapping resolution block, originally lines 2204–2249) exactly as-is.

Then replace the block starting at `success, df, messages = converter.convert_participant_data(` through the final `return jsonify({...})` (originally lines 2251–2334) with:

```python
                try:
                    result = _write_participants_outputs(
                        project_root=project_root,
                        input_path=input_path,
                        mapping=mapping,
                        converter_separator=converter_separator,
                        sheet_arg=sheet_arg,
                        participants_tsv=participants_tsv,
                        participants_json=participants_json,
                        neurobagel_schema=neurobagel_schema,
                        existing_files=existing_files,
                        log_msg=log_msg,
                    )
                except ValueError:
                    return jsonify({"error": "Conversion failed", "log": logs}), 400

                return jsonify({**result, "log": logs})
```

(Remove the now-unused `from src.participants_converter import ParticipantsConverter` import at the top of `api_participants_convert` — check with `grep -n ParticipantsConverter` on the route body first in case anything else there still needs it.)

- [ ] **Step 6: Wire into `_run_participants_convert_job`'s file-mode branch**

In `conversion_participants_convert.py`, replace the equivalent block inside `_run_participants_convert_job` (from `from src.participants_converter import ParticipantsConverter` through the `_participants_job_store.success(job_id, {...})` call) with:

```python
                try:
                    result = _write_participants_outputs(
                        project_root=project_root,
                        input_path=input_path,
                        mapping=mapping,
                        converter_separator=config["converter_separator"],
                        sheet_arg=config["sheet_arg"],
                        participants_tsv=participants_tsv,
                        participants_json=participants_json,
                        neurobagel_schema=neurobagel_schema,
                        existing_files=existing_files,
                        log_msg=log_msg,
                    )
                except ValueError:
                    _participants_job_store.failure(job_id, "Conversion failed")
                    return

                _participants_job_store.success(job_id, result)
```

Add `_check_existing_participants_files` and `_write_participants_outputs` to the blueprint's import from `conversion_participants_convert` if not already there.

- [ ] **Step 7: Run full regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v && pytest tests/test_conversion_participants_convert_helpers.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_convert.py app/src/web/blueprints/conversion_participants_blueprint.py tests/test_conversion_participants_convert_helpers.py
git commit -m "refactor: consolidate duplicated participants.tsv/json writer into _write_participants_outputs"
```

---

### Task 7: TDD — extract `_resolve_additional_preview_columns` from `api_participants_preview`

**Files:**
- Modify: `app/src/web/blueprints/conversion_participants_mapping.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py` (route `api_participants_preview`)
- Create: `tests/test_conversion_participants_preview_helpers.py`

**Interfaces:**
- Produces: `_resolve_additional_preview_columns(df: "pd.DataFrame", project_root: "Path | None", excluded_columns: set[str], extra_columns_json: str) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_conversion_participants_preview_helpers.py`:

```python
import json
import tempfile
from pathlib import Path

import pandas as pd

from src.web.blueprints.conversion_participants_mapping import (
    _resolve_additional_preview_columns,
)


def _df():
    return pd.DataFrame({"participant_id": ["sub-001"], "age": [21], "site": ["A"]})


def test_no_project_root_and_no_extra_columns_returns_empty():
    assert _resolve_additional_preview_columns(_df(), None, set(), "") == []


def test_columns_from_saved_mapping_are_included():
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        mapping_path = project_root / "participants_mapping.json"
        mapping_path.write_text(
            json.dumps({"mappings": {"site": {"source_column": "site"}}})
        )

        result = _resolve_additional_preview_columns(_df(), project_root, set(), "")

        assert "site" in result


def test_excluded_column_from_saved_mapping_is_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        mapping_path = project_root / "participants_mapping.json"
        mapping_path.write_text(
            json.dumps({"mappings": {"site": {"source_column": "site"}}})
        )

        result = _resolve_additional_preview_columns(
            _df(), project_root, {"site"}, ""
        )

        assert "site" not in result


def test_columns_from_extra_columns_json_are_included():
    result = _resolve_additional_preview_columns(
        _df(), None, set(), json.dumps(["age"])
    )

    assert result == ["age"]


def test_column_not_present_in_df_is_ignored():
    result = _resolve_additional_preview_columns(
        _df(), None, set(), json.dumps(["not_a_real_column"])
    )

    assert result == []
```

Note: `participants_mapping_candidates(project_root)` (already imported in `conversion_participants_mapping.py` from Task 2) must resolve `participants_mapping_candidates` to include `project_root / "participants_mapping.json"` as one of its candidates for `test_columns_from_saved_mapping_are_included` to pass — check `src/participants_paths.py::participants_mapping_candidates` for the exact expected filename before running Step 2; adjust the fixture's filename in the test to match if it differs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversion_participants_preview_helpers.py -v`
Expected: FAIL with `ImportError: cannot import name '_resolve_additional_preview_columns'`.

- [ ] **Step 3: Implement `_resolve_additional_preview_columns`**

Add to `conversion_participants_mapping.py`:

```python
def _resolve_additional_preview_columns(
    df,
    project_root: "Path | None",
    excluded_columns: set[str],
    extra_columns_json: str,
) -> list[str]:
    """Extra source columns to add to a participants preview.

    Columns come from the project's saved participants mapping (via
    participants_mapping_candidates) and the frontend's "Additional
    Variables" selection (extra_columns_json), minus excluded_columns.
    Only columns present in df are returned.
    """
    additional_columns: list[str] = []

    if project_root:
        loaded_mapping = None
        for candidate in participants_mapping_candidates(project_root):
            if candidate.exists() and candidate.is_file():
                try:
                    with open(candidate, "r", encoding="utf-8") as mapping_file:
                        loaded_mapping = json.load(mapping_file)
                    break
                except Exception:
                    loaded_mapping = None

        if isinstance(loaded_mapping, dict):
            if isinstance(loaded_mapping.get("mappings"), dict):
                for map_spec in loaded_mapping["mappings"].values():
                    if not isinstance(map_spec, dict):
                        continue
                    source_col = str(map_spec.get("source_column") or "").strip()
                    if (
                        source_col
                        and source_col in df.columns
                        and source_col not in excluded_columns
                    ):
                        additional_columns.append(source_col)
            elif loaded_mapping:
                for source_col in loaded_mapping.keys():
                    source_name = str(source_col or "").strip()
                    if (
                        source_name
                        and source_name in df.columns
                        and source_name not in excluded_columns
                    ):
                        additional_columns.append(source_name)

    if extra_columns_json:
        try:
            for col in json.loads(extra_columns_json):
                col = str(col or "").strip()
                if (
                    col
                    and col in df.columns
                    and col not in excluded_columns
                    and col not in additional_columns
                ):
                    additional_columns.append(col)
        except Exception:
            pass

    return additional_columns
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversion_participants_preview_helpers.py -v`
Expected: PASS (5 tests). If `test_columns_from_saved_mapping_are_included` fails because of the candidate filename, fix the test fixture's filename to match `participants_mapping_candidates`'s actual expected name (found via `grep -n "def participants_mapping_candidates" -A 15 src/participants_paths.py`) and re-run — do not change the implementation to fit a wrong filename.

- [ ] **Step 5: Wire into `api_participants_preview`**

In `conversion_participants_blueprint.py`, replace the block from `additional_columns = []` through the `extra_columns_json` try/except (originally lines 1668–1735) with:

```python
            additional_columns = _resolve_additional_preview_columns(
                df=df,
                project_root=_get_session_project_root(),
                excluded_columns=excluded_columns,
                extra_columns_json=request.form.get("extra_columns", ""),
            )
```

Keep the following block unchanged:

```python
            for column_name in additional_columns:
                if column_name not in output_columns:
                    output_columns.append(column_name)
```

Add `_resolve_additional_preview_columns` to the blueprint's `from .conversion_participants_mapping import (...)` block.

- [ ] **Step 6: Run full regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v && pytest tests/test_conversion_participants_preview_helpers.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_mapping.py app/src/web/blueprints/conversion_participants_blueprint.py tests/test_conversion_participants_preview_helpers.py
git commit -m "refactor: extract _resolve_additional_preview_columns from api_participants_preview"
```

---

### Task 8: TDD — extract `_diagnose_preview_error` from `api_participants_preview`'s exception handler

**Files:**
- Modify: `app/src/web/blueprints/conversion_participants_io.py`
- Modify: `app/src/web/blueprints/conversion_participants_blueprint.py` (route `api_participants_preview`)
- Modify: `tests/test_conversion_participants_preview_helpers.py`

**Interfaces:**
- Produces: `_diagnose_preview_error(exc: Exception, df, input_path: "Path | None", suffix: "str | None", sheet_arg, separator_option: "str | None", preview_stage: "str | None") -> tuple[Response, int]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_conversion_participants_preview_helpers.py`:

```python
import pandas as pd

from src.web.blueprints.conversion_participants_io import _diagnose_preview_error


def test_mixed_time_format_column_produces_400_with_error_code():
    df = pd.DataFrame({"duration": ["10:30", "2h", "10:45", "3h"]})

    response, status_code = _diagnose_preview_error(
        exc=ValueError("boom"),
        df=df,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage="reading input file",
    )

    assert status_code == 400
    body = response.get_json()
    assert body["error_code"] == "mixed_time_formats"
    assert body["problem_columns"][0]["column"] == "duration"


def test_generic_exception_without_df_produces_500_with_message():
    response, status_code = _diagnose_preview_error(
        exc=ValueError("something broke"),
        df=None,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage="detecting participant ID column",
    )

    assert status_code == 500
    body = response.get_json()
    assert body["error"] == "something broke"
    assert body["error_type"] == "ValueError"
    assert body["error_stage"] == "detecting participant ID column"


def test_pattern_mismatch_message_is_rewritten_with_stage():
    response, status_code = _diagnose_preview_error(
        exc=ValueError("The string did not match the expected pattern."),
        df=None,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage="resolving template library",
    )

    assert status_code == 500
    body = response.get_json()
    assert "resolving template library" in body["error"]


def test_missing_preview_stage_defaults_to_unknown_stage():
    response, status_code = _diagnose_preview_error(
        exc=ValueError("boom"),
        df=None,
        input_path=None,
        suffix=None,
        sheet_arg=0,
        separator_option="auto",
        preview_stage=None,
    )

    body = response.get_json()
    assert body["error_stage"] == "unknown stage"
```

These tests call `response.get_json()` on a Flask `jsonify(...)` return value outside a request context, which requires an application context. Wrap each call (or the whole test module) using a minimal Flask app context — add this fixture at the top of the file and use it in each test:

```python
import pytest
from flask import Flask

_app = Flask(__name__)


@pytest.fixture(autouse=True)
def _app_context():
    with _app.app_context():
        yield
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversion_participants_preview_helpers.py -v -k diagnose_preview_error`
Expected: FAIL with `ImportError: cannot import name '_diagnose_preview_error'`.

- [ ] **Step 3: Implement `_diagnose_preview_error`**

Add to `conversion_participants_io.py` (add `from flask import jsonify, Response` to its imports):

```python
def _diagnose_preview_error(
    exc: Exception,
    df,
    input_path: "Path | None",
    suffix: "str | None",
    sheet_arg,
    separator_option: "str | None",
    preview_stage: "str | None",
) -> "tuple[Response, int]":
    """Build the error response for a failed /api/participants-preview request.

    Tries to detect mixed time-format columns (using df if already loaded,
    else by re-reading input_path) to give a more actionable error than the
    raw exception message.
    """
    diagnostic_columns: list[dict[str, object]] = []

    if df is not None:
        try:
            diagnostic_columns = _detect_mixed_time_style_columns(df)
        except Exception:
            diagnostic_columns = []

    if (
        not diagnostic_columns
        and input_path is not None
        and suffix in {".xlsx", ".csv", ".tsv", ".lsa"}
    ):
        try:
            diagnostic_df = _read_participants_input_table(
                input_path=input_path,
                suffix=suffix,
                sheet_arg=sheet_arg,
                separator_option=separator_option,
            )
            if diagnostic_df is not None:
                diagnostic_columns = _detect_mixed_time_style_columns(diagnostic_df)
        except Exception:
            diagnostic_columns = []

    if diagnostic_columns:
        mixed_time_message = _format_mixed_time_style_message(diagnostic_columns)
        return (
            jsonify(
                {
                    "error": mixed_time_message,
                    "error_code": "mixed_time_formats",
                    "problem_columns": diagnostic_columns,
                }
            ),
            400,
        )

    error_text = str(exc) or "Preview failed"
    error_type = exc.__class__.__name__
    stage_text = preview_stage or "unknown stage"

    if error_text.strip().lower() == "the string did not match the expected pattern.":
        error_text = (
            "Preview failed due to an invalid value pattern in the uploaded data "
            f"(stage: {stage_text}). Please check columns with timing/duration values "
            "for mixed formats and ambiguous tokens, then retry."
        )

    return (
        jsonify(
            {
                "error": error_text,
                "error_type": error_type,
                "error_stage": stage_text,
            }
        ),
        500,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversion_participants_preview_helpers.py -v`
Expected: PASS (9 tests total in this file).

- [ ] **Step 5: Wire into `api_participants_preview`'s exception handler**

In `conversion_participants_blueprint.py`, replace the entire `except Exception as e:` block (originally lines 1810–1881) with:

```python
        except Exception as e:
            return _diagnose_preview_error(
                exc=e,
                df=df if "df" in locals() else None,
                input_path=input_path if "input_path" in locals() else None,
                suffix=suffix if "suffix" in locals() else None,
                sheet_arg=sheet_arg if "sheet_arg" in locals() else None,
                separator_option=(
                    separator_option if "separator_option" in locals() else None
                ),
                preview_stage=preview_stage if "preview_stage" in locals() else None,
            )
```

Add `_diagnose_preview_error` to the blueprint's `from .conversion_participants_io import (...)` block.

- [ ] **Step 6: Run full regression suite**

Run: `pytest tests/test_web_blueprints_conversion.py -k Participants -v && pytest tests/test_conversion_participants_preview_helpers.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/src/web/blueprints/conversion_participants_io.py app/src/web/blueprints/conversion_participants_blueprint.py tests/test_conversion_participants_preview_helpers.py
git commit -m "refactor: extract _diagnose_preview_error from api_participants_preview exception handler"
```

---

### Task 9: Final verification and cleanup pass

**Files:**
- Modify (formatting only, if needed): all five blueprint files touched above.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v 2>&1 | tail -60`
Expected: no failures anywhere in the repo (not just the participants-related tests) — this catches any import-order or circular-import issue introduced across Tasks 1–8.

- [ ] **Step 2: Re-run every drift check**

```bash
python3 -c "import src.web.blueprints.conversion_participants_blueprint as m; print(m.__file__)"
python3 -c "import src.web.blueprints.conversion_participants_io as m; print(m.__file__)"
python3 -c "import src.web.blueprints.conversion_participants_mapping as m; print(m.__file__)"
python3 -c "import src.web.blueprints.conversion_participants_merge as m; print(m.__file__)"
python3 -c "import src.web.blueprints.conversion_participants_convert as m; print(m.__file__)"
```

Expected: all five print a path under `app/src/web/blueprints/`.

- [ ] **Step 3: Confirm the size reduction**

Run: `wc -l app/src/web/blueprints/conversion_participants_*.py`
Expected: `conversion_participants_blueprint.py` is now roughly 1,000–1,200 lines (down from 2,748); the four new files plus the blueprint sum to a similar total line count as before (a small net decrease from the two consolidations in Tasks 5–6, since duplicated code was removed).

- [ ] **Step 4: Format and lint**

Run: `black app/src/web/blueprints/conversion_participants_*.py tests/test_conversion_participants_convert_helpers.py tests/test_conversion_participants_preview_helpers.py && flake8 app/src/web/blueprints/conversion_participants_*.py`
Expected: `black` reports no changes needed or applies only whitespace formatting; `flake8` reports no unused-import warnings (this is the real check that every import list built in Tasks 1–8 was accurate — an unused import here means a name was imported into a file that doesn't actually call it, and a missing-name `NameError` at runtime would have already been caught by Step 1).

- [ ] **Step 5: Commit any formatting fixes**

```bash
git add -u
git commit -m "style: black formatting pass on the split participants blueprint files"
```

(Skip this step if `black`/`flake8` made no changes.)
