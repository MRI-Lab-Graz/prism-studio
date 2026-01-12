"""
Output formatters for prism.

Supports multiple output formats:
- text: Human-readable terminal output (default)
- json: Machine-readable JSON
- sarif: SARIF format for GitHub/GitLab code scanning
- junit: JUnit XML for CI/CD test reporting
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Callable
from defusedxml import ElementTree as ET
from defusedxml import minidom

from issues import (
    Issue,
    Severity,
    summarize_issues,
    get_error_documentation_url,
)


# =============================================================================
# SARIF OUTPUT (Static Analysis Results Interchange Format)
# =============================================================================


def to_sarif(
    issues: List[Issue],
    dataset_path: str,
    schema_version: str = "stable",
) -> Dict[str, Any]:
    """
    Convert validation results to SARIF 2.1.0 format.

    SARIF is supported by GitHub Code Scanning, GitLab SAST, and other CI tools.

    Args:
        issues: List of Issue objects
        dataset_path: Path to the dataset
        schema_version: Schema version used

    Returns:
        SARIF document as dict
    """
    # Map our severity to SARIF levels
    severity_map = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "note",
    }

    # Build unique rule definitions from issues
    rules = {}
    for issue in issues:
        if issue.code not in rules:
            rules[issue.code] = {
                "id": issue.code,
                "name": issue.code,
                "shortDescription": {
                    "text": issue.message.split("\n")[0][
                        :200
                    ]  # First line, max 200 chars
                },
                "helpUri": get_error_documentation_url(issue.code),
                "properties": {
                    "category": _get_issue_category(issue.code),
                },
            }
            if issue.fix_hint:
                rules[issue.code]["help"] = {"text": issue.fix_hint}

    # Build results
    results = []
    for issue in issues:
        result = {
            "ruleId": issue.code,
            "level": severity_map.get(issue.severity, "warning"),
            "message": {"text": issue.message},
        }

        # Add location if file_path is available
        if issue.file_path:
            rel_path = (
                os.path.relpath(issue.file_path, dataset_path)
                if os.path.isabs(issue.file_path)
                else issue.file_path
            )
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": rel_path.replace("\\", "/"),
                            "uriBaseId": "DATASETROOT",
                        }
                    }
                }
            ]

        # Add fix suggestion if available
        if issue.fix_hint:
            result["fixes"] = [{"description": {"text": issue.fix_hint}}]

        results.append(result)

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "prism",
                        "version": "1.7.0",
                        "informationUri": "https://prism.readthedocs.io",
                        "rules": list(rules.values()),
                    }
                },
                "originalUriBaseIds": {
                    "DATASETROOT": {
                        "uri": f"file://{os.path.abspath(dataset_path)}/",
                        "description": {
                            "text": "The root directory of the validated dataset"
                        },
                    }
                },
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "endTimeUtc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "toolConfigurationNotifications": [],
                        "properties": {"schemaVersion": schema_version},
                    }
                ],
            }
        ],
    }

    return sarif


def _get_issue_category(code: str) -> str:
    """Get category from issue code"""
    if code.startswith("PRISM0"):
        return "dataset-structure"
    elif code.startswith("PRISM1"):
        return "file-naming"
    elif code.startswith("PRISM2"):
        return "sidecar-metadata"
    elif code.startswith("PRISM3"):
        return "schema-validation"
    elif code.startswith("PRISM4"):
        return "content-validation"
    elif code.startswith("PRISM5"):
        return "bids-compatibility"
    else:
        return "other"


# =============================================================================
# JUnit XML OUTPUT
# =============================================================================


def to_junit_xml(
    issues: List[Issue],
    dataset_path: str,
    stats: Any = None,
) -> str:
    """
    Convert validation results to JUnit XML format.

    JUnit XML is widely supported by CI/CD systems (Jenkins, GitHub Actions, etc.)

    Args:
        issues: List of Issue objects
        dataset_path: Path to the dataset
        stats: Optional DatasetStats object

    Returns:
        JUnit XML as string
    """
    # Create root element
    testsuites = ET.Element("testsuites")
    testsuites.set("name", "prism")
    testsuites.set("tests", str(len(issues) + 1))  # +1 for the overall test

    error_count = sum(1 for i in issues if i.severity == Severity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)

    testsuites.set("errors", str(error_count))
    testsuites.set("failures", "0")  # We use errors, not failures
    testsuites.set("time", "0")

    # Create testsuite for the dataset
    testsuite = ET.SubElement(testsuites, "testsuite")
    testsuite.set("name", os.path.basename(dataset_path))
    testsuite.set("tests", str(len(issues) + 1))
    testsuite.set("errors", str(error_count))
    testsuite.set("failures", "0")
    testsuite.set("time", "0")
    testsuite.set("timestamp", datetime.utcnow().isoformat())

    # Add properties
    properties = ET.SubElement(testsuite, "properties")
    prop = ET.SubElement(properties, "property")
    prop.set("name", "dataset_path")
    prop.set("value", os.path.abspath(dataset_path))

    if stats:
        prop = ET.SubElement(properties, "property")
        prop.set("name", "subject_count")
        prop.set("value", str(len(getattr(stats, "subjects", []))))

        prop = ET.SubElement(properties, "property")
        prop.set("name", "total_files")
        prop.set("value", str(getattr(stats, "total_files", 0)))

    # Add overall validation test case
    overall_test = ET.SubElement(testsuite, "testcase")
    overall_test.set("name", "Dataset Validation")
    overall_test.set("classname", "prism")
    overall_test.set("time", "0")

    if error_count > 0:
        error_elem = ET.SubElement(overall_test, "error")
        error_elem.set(
            "message",
            f"Validation found {error_count} error(s) and {warning_count} warning(s)",
        )
        error_elem.set("type", "ValidationError")

    # Add individual test cases for each issue
    for issue in issues:
        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", f"[{issue.code}] {issue.message[:100]}")
        testcase.set("classname", f"prism.{_get_issue_category(issue.code)}")
        testcase.set("time", "0")

        if issue.severity == Severity.ERROR:
            error_elem = ET.SubElement(testcase, "error")
            error_elem.set("message", issue.message)
            error_elem.set("type", issue.code)
            if issue.file_path:
                error_elem.text = f"File: {issue.file_path}"
        elif issue.severity == Severity.WARNING:
            # JUnit doesn't have warnings, we can use system-out
            system_out = ET.SubElement(testcase, "system-out")
            system_out.text = f"WARNING: {issue.message}"

    # Pretty print
    xml_str = ET.tostring(testsuites, encoding="unicode")
    return minidom.parseString(xml_str).toprettyxml(indent="  ")


# =============================================================================
# MARKDOWN OUTPUT
# =============================================================================


def to_markdown(
    issues: List[Issue],
    dataset_path: str,
    stats: Any = None,
    include_badge: bool = True,
) -> str:
    """
    Convert validation results to Markdown format.

    Useful for README badges and reports.

    Args:
        issues: List of Issue objects
        dataset_path: Path to the dataset
        stats: Optional DatasetStats object
        include_badge: Include validation badge

    Returns:
        Markdown string
    """
    summary = summarize_issues(issues)
    is_valid = summary["errors"] == 0

    lines = []

    # Badge
    if include_badge:
        if is_valid:
            badge = "![Validation: Passed](https://img.shields.io/badge/PRISM-valid-brightgreen)"
        else:
            badge = (
                "![Validation: Failed](https://img.shields.io/badge/PRISM-invalid-red)"
            )
        lines.append(badge)
        lines.append("")

    # Header
    lines.append("# PRISM Validation Report")
    lines.append("")
    lines.append(f"**Dataset:** `{os.path.basename(dataset_path)}`")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Status | {'✅ Valid' if is_valid else '❌ Invalid'} |")
    lines.append(f"| Errors | {summary['errors']} |")
    lines.append(f"| Warnings | {summary['warnings']} |")

    if stats:
        lines.append(f"| Subjects | {len(getattr(stats, 'subjects', []))} |")
        lines.append(f"| Total Files | {getattr(stats, 'total_files', 0)} |")

    lines.append("")

    # Issues by category
    if issues:
        lines.append("## Issues")
        lines.append("")

        # Group by severity
        errors = [i for i in issues if i.severity == Severity.ERROR]
        warnings = [i for i in issues if i.severity == Severity.WARNING]

        if errors:
            lines.append("### Errors")
            lines.append("")
            for issue in errors:
                lines.append(f"- **[{issue.code}]** {issue.message}")
                if issue.file_path:
                    lines.append(f"  - File: `{issue.file_path}`")
                if issue.fix_hint:
                    lines.append(f"  - Fix: {issue.fix_hint}")
            lines.append("")

        if warnings:
            lines.append("### Warnings")
            lines.append("")
            for issue in warnings[:20]:  # Limit to first 20
                lines.append(f"- **[{issue.code}]** {issue.message}")
            if len(warnings) > 20:
                lines.append(f"- ... and {len(warnings) - 20} more warnings")
            lines.append("")
    else:
        lines.append("## ✅ No Issues Found")
        lines.append("")
        lines.append("The dataset passed all validation checks.")

    return "\n".join(lines)


# =============================================================================
# CSV OUTPUT
# =============================================================================


def to_csv(issues: List[Issue]) -> str:
    """
    Convert issues to CSV format.

    Args:
        issues: List of Issue objects

    Returns:
        CSV string
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["code", "severity", "message", "file_path", "fix_hint"])

    # Data
    for issue in issues:
        writer.writerow(
            [
                issue.code,
                issue.severity.value,
                issue.message,
                issue.file_path or "",
                issue.fix_hint or "",
            ]
        )

    return output.getvalue()


# =============================================================================
# FORMAT REGISTRY
# =============================================================================

FORMATTERS: Dict[str, Callable[..., str]] = {
    "json": lambda issues, path, stats: json.dumps(
        {
            "issues": [i.to_dict() for i in issues],
            "summary": summarize_issues(issues),
        },
        indent=2,
    ),
    "sarif": lambda issues, path, stats: json.dumps(to_sarif(issues, path), indent=2),
    "junit": to_junit_xml,
    "markdown": to_markdown,
    "csv": lambda issues, path, stats: to_csv(issues),
}


def format_output(
    issues: List[Issue],
    dataset_path: str,
    format_name: str,
    stats: Any = None,
) -> str:
    """
    Format issues in the specified format.

    Args:
        issues: List of Issue objects
        dataset_path: Path to dataset
        format_name: Output format (json, sarif, junit, markdown, csv)
        stats: Optional DatasetStats

    Returns:
        Formatted string
    """
    formatter = FORMATTERS.get(format_name)
    if not formatter:
        raise ValueError(
            f"Unknown format: {format_name}. Available: {list(FORMATTERS.keys())}"
        )

    return formatter(issues, dataset_path, stats)
