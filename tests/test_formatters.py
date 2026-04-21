"""Tests for src/formatters.py — SARIF, JUnit, Markdown, CSV, JSON output."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from issues import Issue, Severity
from src.formatters import (
    to_sarif,
    to_junit_xml,
    to_markdown,
    to_csv,
    format_output,
    _get_issue_category,
    FORMATTERS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(code="PRISM001", msg="Something broke", path=None, hint=None):
    return Issue(code=code, severity=Severity.ERROR, message=msg,
                 file_path=path, fix_hint=hint)

def _warning(code="PRISM201", msg="Watch out", path=None):
    return Issue(code=code, severity=Severity.WARNING, message=msg, file_path=path)


# ---------------------------------------------------------------------------
# _get_issue_category
# ---------------------------------------------------------------------------

class TestGetIssueCategory:
    def test_prism0(self):
        assert _get_issue_category("PRISM001") == "dataset-structure"

    def test_prism1(self):
        assert _get_issue_category("PRISM101") == "file-naming"

    def test_prism2(self):
        assert _get_issue_category("PRISM201") == "sidecar-metadata"

    def test_prism3(self):
        assert _get_issue_category("PRISM301") == "schema-validation"

    def test_prism4(self):
        assert _get_issue_category("PRISM401") == "content-validation"

    def test_prism5(self):
        assert _get_issue_category("PRISM501") == "bids-compatibility"

    def test_unknown(self):
        assert _get_issue_category("UNKNOWN999") == "other"


# ---------------------------------------------------------------------------
# to_sarif
# ---------------------------------------------------------------------------

class TestToSarif:
    def test_empty_issues(self, tmp_path):
        result = to_sarif([], str(tmp_path))
        assert result["version"] == "2.1.0"
        assert result["runs"][0]["results"] == []

    def test_error_issue_included(self, tmp_path):
        issues = [_error(code="PRISM001", msg="Missing file", path="/some/file.json")]
        result = to_sarif(issues, str(tmp_path))
        run = result["runs"][0]
        assert len(run["results"]) == 1
        assert run["results"][0]["ruleId"] == "PRISM001"
        assert run["results"][0]["level"] == "error"

    def test_warning_level(self, tmp_path):
        issues = [_warning()]
        result = to_sarif(issues, str(tmp_path))
        assert result["runs"][0]["results"][0]["level"] == "warning"

    def test_rules_deduplicated(self, tmp_path):
        issues = [_error("PRISM001", "a"), _error("PRISM001", "b")]
        result = to_sarif(issues, str(tmp_path))
        rules = result["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 1

    def test_fix_hint_in_rule(self, tmp_path):
        issues = [_error(hint="Do this instead")]
        result = to_sarif(issues, str(tmp_path))
        rule = result["runs"][0]["tool"]["driver"]["rules"][0]
        assert "help" in rule

    def test_location_added_when_file_path(self, tmp_path):
        issues = [_error(path=str(tmp_path / "file.json"))]
        result = to_sarif(issues, str(tmp_path))
        locations = result["runs"][0]["results"][0].get("locations")
        assert locations is not None

    def test_no_location_without_file_path(self, tmp_path):
        issues = [_error()]
        result = to_sarif(issues, str(tmp_path))
        assert "locations" not in result["runs"][0]["results"][0]


# ---------------------------------------------------------------------------
# to_junit_xml
# ---------------------------------------------------------------------------

class TestToJunitXml:
    def test_returns_string(self, tmp_path):
        xml = to_junit_xml([], str(tmp_path))
        assert isinstance(xml, str)
        assert "testsuites" in xml

    def test_error_produces_error_element(self, tmp_path):
        xml = to_junit_xml([_error()], str(tmp_path))
        assert "<error" in xml

    def test_warning_produces_system_out(self, tmp_path):
        xml = to_junit_xml([_warning()], str(tmp_path))
        assert "system-out" in xml or "WARNING" in xml

    def test_valid_xml(self, tmp_path):
        from defusedxml import ElementTree as ET
        xml = to_junit_xml([_error(), _warning()], str(tmp_path))
        # Should parse without raising
        ET.fromstring(xml)

    def test_stats_included_in_xml(self, tmp_path):
        """Lines 223-229: stats with subjects and total_files."""
        class FakeStats:
            subjects = ["sub-01", "sub-02"]
            total_files = 42
        xml = to_junit_xml([], str(tmp_path), stats=FakeStats())
        assert "subject_count" in xml
        assert "total_files" in xml

    def test_error_with_file_path_in_xml(self, tmp_path):
        """Line 257: error with file_path → text set on error element."""
        xml = to_junit_xml([_error(path="sub-01/T1w.json")], str(tmp_path))
        assert "sub-01/T1w.json" in xml or "File:" in xml


# ---------------------------------------------------------------------------
# to_markdown
# ---------------------------------------------------------------------------

class TestToMarkdown:
    def test_no_issues_valid(self, tmp_path):
        md = to_markdown([], str(tmp_path))
        assert "No Issues Found" in md or "valid" in md.lower()

    def test_errors_appear(self, tmp_path):
        md = to_markdown([_error(msg="Missing dataset_description.json")], str(tmp_path))
        assert "Missing dataset_description.json" in md

    def test_warnings_appear(self, tmp_path):
        md = to_markdown([_warning(msg="Deprecated field")], str(tmp_path))
        assert "Deprecated field" in md

    def test_badge_included_by_default(self, tmp_path):
        md = to_markdown([], str(tmp_path))
        assert "img.shields.io" in md

    def test_badge_excluded(self, tmp_path):
        md = to_markdown([], str(tmp_path), include_badge=False)
        assert "img.shields.io" not in md

    def test_warning_truncation(self, tmp_path):
        warnings = [_warning(msg=f"warn {i}") for i in range(25)]
        md = to_markdown(warnings, str(tmp_path))
        assert "more warnings" in md


# ---------------------------------------------------------------------------
# to_csv
# ---------------------------------------------------------------------------

class TestToCsv:
    def test_header_row(self, tmp_path):
        csv = to_csv([])
        assert "code" in csv
        assert "severity" in csv

    def test_data_row(self, tmp_path):
        csv = to_csv([_error(code="PRISM001", msg="broken")])
        assert "PRISM001" in csv
        assert "broken" in csv

    def test_empty_path_and_hint_blank(self, tmp_path):
        csv = to_csv([_error()])
        lines = csv.strip().splitlines()
        assert len(lines) == 2  # header + 1 data row


# ---------------------------------------------------------------------------
# format_output / FORMATTERS registry
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_json_format(self, tmp_path):
        out = format_output([_error()], str(tmp_path), "json")
        parsed = json.loads(out)
        assert "issues" in parsed
        assert "summary" in parsed

    def test_sarif_format(self, tmp_path):
        out = format_output([_error()], str(tmp_path), "sarif")
        parsed = json.loads(out)
        assert parsed["version"] == "2.1.0"

    def test_junit_format(self, tmp_path):
        out = format_output([_error()], str(tmp_path), "junit")
        assert "testsuites" in out

    def test_markdown_format(self, tmp_path):
        out = format_output([], str(tmp_path), "markdown")
        assert "PRISM" in out

    def test_csv_format(self, tmp_path):
        out = format_output([_error()], str(tmp_path), "csv")
        assert "code" in out

    def test_unknown_format_raises(self, tmp_path):
        import pytest
        with pytest.raises(ValueError, match="Unknown format"):
            format_output([], str(tmp_path), "xml")
