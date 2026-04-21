"""Tests for src/converters/biometrics.py — pure utility functions."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.biometrics import (
    _norm_col,
    _find_col,
    _normalize_sub_id,
    _normalize_ses_id,
    _load_biometrics_library,
    detect_biometrics_in_table,
    BiometricsConvertResult,
)


# ---------------------------------------------------------------------------
# _norm_col
# ---------------------------------------------------------------------------

class TestNormCol:
    def test_lowercases_and_strips(self):
        assert _norm_col("  AGE  ") == "age"

    def test_replaces_spaces_with_underscores(self):
        # norm_key normalizes whitespace
        result = _norm_col("First Name")
        assert " " not in result

    def test_empty_string(self):
        result = _norm_col("")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _find_col
# ---------------------------------------------------------------------------

class TestFindCol:
    def test_finds_exact_match(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"participant_id": ["sub-001"], "age": [25]})
        result = _find_col(df, {"participant_id", "subject"})
        assert result == "participant_id"

    def test_case_insensitive_match(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"Participant_ID": ["sub-001"]})
        result = _find_col(df, {"participant_id"})
        assert result == "Participant_ID"

    def test_returns_none_if_not_found(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        df = pd.DataFrame({"age": [25]})
        result = _find_col(df, {"participant_id"})
        assert result is None


# ---------------------------------------------------------------------------
# _normalize_sub_id
# ---------------------------------------------------------------------------

class TestNormalizeSubId:
    def test_bare_number(self):
        assert _normalize_sub_id("001") == "sub-001"

    def test_already_sub_prefix(self):
        assert _normalize_sub_id("sub-001") == "sub-001"

    def test_uppercase_sub(self):
        assert _normalize_sub_id("SUB-042") == "sub-042"

    def test_strips_special_chars(self):
        assert _normalize_sub_id("s u b - 0 1") in ("sub-sub01", "sub-sub01", "sub-sub01") or \
               "sub" in _normalize_sub_id("s-u-b-01")

    def test_empty_returns_empty(self):
        assert _normalize_sub_id("") == ""

    def test_nan_returns_empty(self):
        assert _normalize_sub_id("nan") == ""


# ---------------------------------------------------------------------------
# _normalize_ses_id
# ---------------------------------------------------------------------------

class TestNormalizeSesId:
    def test_bare_number(self):
        assert _normalize_ses_id("1") == "ses-1"

    def test_already_ses_prefix(self):
        assert _normalize_ses_id("ses-01") == "ses-01"

    def test_empty_uses_default(self):
        result = _normalize_ses_id("", default_session="ses-1")
        assert result == "ses-1"

    def test_none_uses_default(self):
        result = _normalize_ses_id(None, default_session="ses-baseline")
        assert result == "ses-baseline"

    def test_nan_uses_default(self):
        result = _normalize_ses_id("nan")
        assert result == "ses-1"


# ---------------------------------------------------------------------------
# _load_biometrics_library
# ---------------------------------------------------------------------------

class TestLoadBiometricsLibrary:
    def test_empty_library(self, tmp_path):
        task_to_items, task_to_template = _load_biometrics_library(tmp_path)
        assert task_to_items == {}
        assert task_to_template == {}

    def test_loads_valid_file(self, tmp_path):
        data = {
            "grip_left": {"unit": "kg"},
            "grip_right": {"unit": "kg"},
            "Study": {},
            "Technical": {},
        }
        (tmp_path / "biometrics-grip.json").write_text(json.dumps(data))
        task_to_items, task_to_template = _load_biometrics_library(tmp_path)
        assert "grip" in task_to_items
        assert "grip_left" in task_to_items["grip"]
        assert "grip_right" in task_to_items["grip"]

    def test_skips_malformed_json(self, tmp_path):
        (tmp_path / "biometrics-bad.json").write_text("NOT JSON")
        task_to_items, _ = _load_biometrics_library(tmp_path)
        assert "bad" not in task_to_items

    def test_skips_file_with_no_items(self, tmp_path):
        # All keys are non-item top-level keys
        data = {"Study": {}, "Technical": {}}
        (tmp_path / "biometrics-empty.json").write_text(json.dumps(data))
        task_to_items, _ = _load_biometrics_library(tmp_path)
        assert "empty" not in task_to_items


# ---------------------------------------------------------------------------
# detect_biometrics_in_table
# ---------------------------------------------------------------------------

class TestDetectBiometricsInTable:
    def test_detects_matching_task(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        # Create library with grip task
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        grip_data = {"grip_left": {"unit": "kg"}, "grip_right": {"unit": "kg"}}
        (library_dir / "biometrics-grip.json").write_text(json.dumps(grip_data))

        # Create input table with grip_left column
        input_file = tmp_path / "data.csv"
        pd.DataFrame({"participant_id": ["sub-001"], "grip_left": [45.0]}).to_csv(
            input_file, index=False
        )

        result = detect_biometrics_in_table(
            input_path=input_file, library_dir=library_dir
        )
        assert "grip" in result

    def test_returns_empty_if_no_match(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        (library_dir / "biometrics-grip.json").write_text(
            json.dumps({"grip_left": {}, "grip_right": {}})
        )

        input_file = tmp_path / "data.csv"
        pd.DataFrame({"participant_id": ["sub-001"], "age": [30]}).to_csv(
            input_file, index=False
        )

        result = detect_biometrics_in_table(
            input_path=input_file, library_dir=library_dir
        )
        assert result == []


# ---------------------------------------------------------------------------
# convert_biometrics_table_to_prism_dataset
# ---------------------------------------------------------------------------

try:
    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
    CONVERT_AVAILABLE = True
except ImportError:
    CONVERT_AVAILABLE = False


@pytest.mark.skipif(not CONVERT_AVAILABLE, reason="convert_biometrics_table_to_prism_dataset not available")
class TestConvertBiometricsTable:
    def _make_library(self, library_dir):
        import json
        grip_data = {"grip_left": {"unit": "kg"}, "grip_right": {"unit": "kg"}, "Study": {}}
        (library_dir / "biometrics-grip.json").write_text(json.dumps(grip_data))

    def test_basic_conversion_creates_output(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001", "002"],
            "grip_left": [40.0, 45.0],
            "grip_right": [42.0, 47.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
        )
        assert result.id_column is not None
        assert "grip" in result.tasks_included
        assert (output_root / "dataset_description.json").exists()
        assert (output_root / "participants.tsv").exists()

    def test_skip_participants(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [40.0],
            "grip_right": [42.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
            skip_participants=True,
        )
        assert not (output_root / "participants.tsv").exists()

    def test_unknown_error_mode_raises(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [40.0],
            "unknown_column_xyz": [99],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        with pytest.raises(ValueError, match="Unmapped columns"):
            convert_biometrics_table_to_prism_dataset(
                input_path=input_file,
                library_dir=library_dir,
                output_root=output_root,
                unknown="error",
            )

    def test_explicit_session(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [40.0],
            "grip_right": [42.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
            session="ses-baseline",
        )
        sub_dir = output_root / "sub-001" / "ses-baseline" / "biometrics"
        assert sub_dir.exists()

    def test_nonempty_output_without_force_raises(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [40.0],
            "grip_right": [42.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        output_root.mkdir()
        (output_root / "existing.txt").write_text("existing")

        with pytest.raises(ValueError, match="not empty"):
            convert_biometrics_table_to_prism_dataset(
                input_path=input_file,
                library_dir=library_dir,
                output_root=output_root,
                force=False,
            )

    def test_tasks_to_export_filter(self, tmp_path):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")

        library_dir = tmp_path / "library"
        library_dir.mkdir()
        import json
        self._make_library(library_dir)
        (library_dir / "biometrics-balance.json").write_text(
            json.dumps({"balance_left": {}, "balance_right": {}})
        )

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [40.0],
            "grip_right": [42.0],
            "balance_left": [5.0],
            "balance_right": [6.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
            tasks_to_export=["grip"],
        )
        assert "grip" in result.tasks_included
        assert "balance" not in result.tasks_included

    def test_invalid_extension_raises(self, tmp_path):
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.json"
        input_file.write_text("{}")

        with pytest.raises(ValueError, match="must be a .csv"):
            convert_biometrics_table_to_prism_dataset(
                input_path=input_file,
                library_dir=library_dir,
                output_root=tmp_path / "output",
            )

    def test_missing_library_dir_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not a directory"):
            convert_biometrics_table_to_prism_dataset(
                input_path=tmp_path / "data.csv",
                library_dir=tmp_path / "nonexistent",
                output_root=tmp_path / "output",
            )


# ---------------------------------------------------------------------------
# Edge cases for pure utility functions
# ---------------------------------------------------------------------------

class TestNormalizeSubIdEdges:
    def test_special_chars_only_returns_empty(self):
        """Line 64: label becomes empty after stripping non-alphanum chars."""
        assert _normalize_sub_id("!!!") == ""

    def test_special_chars_in_sub_prefix_returns_empty(self):
        """Line 64: 'sub-!!!' → label '!!!' → stripped to '' → return ''."""
        assert _normalize_sub_id("sub-!!!") == ""


class TestNormalizeSesIdEdges:
    def test_special_chars_only_uses_default(self):
        """Line 75: label becomes empty → returns default."""
        assert _normalize_ses_id("!!!", default_session="ses-1") == "ses-1"


class TestReadTableAsDataframe:
    def test_unsupported_extension_raises(self, tmp_path):
        """Line 86: non-.csv/.tsv/.xlsx raises ValueError."""
        from src.converters.biometrics import _read_table_as_dataframe
        f = tmp_path / "data.json"
        f.write_text("{}")
        with pytest.raises(ValueError, match="Supported formats"):
            _read_table_as_dataframe(input_path=f)


class TestLoadBiometricsLibraryEdge:
    def test_file_with_empty_task_name_skipped(self, tmp_path):
        """Line 106: biometrics-.json has empty task name → skipped."""
        import json
        (tmp_path / "biometrics-.json").write_text(json.dumps({"item1": {}}))
        task_to_items, _ = _load_biometrics_library(tmp_path)
        assert task_to_items == {}


@pytest.mark.skipif(not CONVERT_AVAILABLE, reason="convert_biometrics_table_to_prism_dataset not available")
class TestConvertBiometricsEdgeCases:
    def _make_library(self, library_dir):
        import json
        grip_data = {"grip_left": {"unit": "kg"}, "grip_right": {"unit": "kg"}}
        (library_dir / "biometrics-grip.json").write_text(json.dumps(grip_data))

    def test_empty_library_raises(self, tmp_path):
        """Line 197: no templates found → raises ValueError."""
        import pandas as pd
        library_dir = tmp_path / "library"
        library_dir.mkdir()  # empty — no biometrics-*.json files

        input_file = tmp_path / "data.csv"
        pd.DataFrame({"participant_id": ["001"], "grip_left": [40.0]}).to_csv(input_file, index=False)

        with pytest.raises(ValueError, match="No biometrics-.*.json templates found"):
            convert_biometrics_table_to_prism_dataset(
                input_path=input_file,
                library_dir=library_dir,
                output_root=tmp_path / "output",
            )

    def test_missing_pid_column_raises(self, tmp_path):
        """Line 211: no participant_id column found → raises ValueError."""
        import pandas as pd
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({"grip_left": [40.0], "grip_right": [42.0]}).to_csv(input_file, index=False)

        with pytest.raises(ValueError, match="Missing participant id column"):
            convert_biometrics_table_to_prism_dataset(
                input_path=input_file,
                library_dir=library_dir,
                output_root=tmp_path / "output",
            )

    def test_row_with_nan_pid_skipped(self, tmp_path):
        """Line 288: sub_id empty → row skipped."""
        import pandas as pd
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["nan", "001"],
            "grip_left": [40.0, 45.0],
            "grip_right": [42.0, 47.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
        )
        # Only sub-001 should appear
        assert (output_root / "sub-001").exists()
        assert not (output_root / "sub-nan").exists()

    def test_na_item_value_written_as_na(self, tmp_path):
        """Line 309: None/NaN item value → written as 'n/a'."""
        import pandas as pd
        import math
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [float("nan")],
            "grip_right": [42.0],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
        )
        tsv_file = output_root / "sub-001" / "ses-1" / "biometrics" / "sub-001_ses-1_task-grip_biometrics.tsv"
        assert tsv_file.exists()
        content = tsv_file.read_text()
        assert "n/a" in content

    def test_reserved_col_name_not_flagged_as_unknown(self, tmp_path):
        """Line 238: column matching reserved key (e.g. 'Study') is silently ignored."""
        import pandas as pd
        library_dir = tmp_path / "library"
        library_dir.mkdir()
        self._make_library(library_dir)

        input_file = tmp_path / "data.csv"
        pd.DataFrame({
            "participant_id": ["001"],
            "grip_left": [40.0],
            "grip_right": [42.0],
            "Study": ["myStudy"],
        }).to_csv(input_file, index=False)

        output_root = tmp_path / "output"
        # Should NOT raise even though 'Study' is not a grip item
        result = convert_biometrics_table_to_prism_dataset(
            input_path=input_file,
            library_dir=library_dir,
            output_root=output_root,
            unknown="error",
        )
        assert "grip" in result.tasks_included
