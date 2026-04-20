from __future__ import annotations

import json

from src.converters.survey import (
    _load_project_template_version_overrides,
    _merge_template_version_overrides,
    _persist_project_template_version_overrides,
)


def test_merge_template_version_overrides_prefers_primary() -> None:
    fallback = [
        {"task": "wb", "session": "ses-1", "run": "run-2", "version": "short"},
        {"task": "mood", "version": "v1"},
    ]
    primary = [
        {"task": "wb", "session": "ses-1", "run": "run-2", "version": "long"},
    ]

    merged = _merge_template_version_overrides(
        primary_overrides=primary,
        fallback_overrides=fallback,
    )

    assert {entry["task"] for entry in merged} == {"wb", "mood"}
    wb_entry = next(entry for entry in merged if entry["task"] == "wb")
    assert wb_entry["version"] == "long"


def test_load_project_template_version_overrides_normalizes_entries(tmp_path) -> None:
    project_json = tmp_path / "project.json"
    project_json.write_text(
        json.dumps(
            {
                "TemplateVersionSelections": [
                    {"task": "WB", "version": "Long", "session": "1", "run": 2}
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = _load_project_template_version_overrides(dataset_root=tmp_path)

    assert loaded == [{"task": "wb", "version": "Long", "session": "1", "run": "run-2"}]


def test_persist_project_template_version_overrides_updates_multiversion_only(
    tmp_path,
) -> None:
    project_json = tmp_path / "project.json"
    project_json.write_text(
        json.dumps(
            {
                "Name": "Demo",
                "TemplateVersionSelections": [
                    {"task": "legacy", "version": "base", "session": "ses-1"}
                ],
            }
        ),
        encoding="utf-8",
    )

    _persist_project_template_version_overrides(
        dataset_root=tmp_path,
        task_context_templates={
            (
                "wb",
                "ses-1",
                "run-2",
            ): {
                "Study": {
                    "Versions": ["short", "long"],
                    "Version": "long",
                }
            },
            ("single", None, None): {
                "Study": {"Versions": ["default"], "Version": "default"}
            },
        },
    )

    data = json.loads(project_json.read_text(encoding="utf-8"))
    selections = data.get("TemplateVersionSelections") or []

    assert any(entry.get("task") == "legacy" for entry in selections)
    assert any(
        entry.get("task") == "wb"
        and entry.get("session") == "ses-1"
        and entry.get("run") == "run-2"
        and entry.get("version") == "long"
        for entry in selections
    )
    assert not any(entry.get("task") == "single" for entry in selections)
