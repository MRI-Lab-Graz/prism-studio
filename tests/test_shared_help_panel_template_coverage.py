import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

TOP_LEVEL_TEMPLATES_WITH_SHARED_HELP = [
    "index.html",
    "projects.html",
    "converter.html",
    "template_editor.html",
    "file_management.html",
    "json_editor.html",
    "specifications.html",
    "survey_generator.html",
    "recipes.html",
    "recipe_builder.html",
    "prism_app_runner.html",
    "results.html",
    "home.html",
]


def test_top_level_templates_import_shared_help_panel_macro() -> None:
    import_pattern = re.compile(r"\{%\s*from\s+\"includes/ui/macros\.html\"\s+import\s+[^%]*help_panel")

    missing_templates: list[str] = []
    for template_name in TOP_LEVEL_TEMPLATES_WITH_SHARED_HELP:
        template_path = REPO_ROOT / "app" / "templates" / template_name
        content = template_path.read_text(encoding="utf-8")
        if not import_pattern.search(content):
            missing_templates.append(template_name)

    assert not missing_templates, (
        "Templates missing shared help_panel import: "
        + ", ".join(sorted(missing_templates))
    )
