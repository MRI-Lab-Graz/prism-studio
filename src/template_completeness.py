"""How complete a template is: the numbers behind the template editor's rings and ``library template-score``.

``required`` counts the fields a template must have to be used (the same rules as the gate that refuses an
incomplete template); ``recommended`` counts the fields that make it reusable (FAIR) and never block.
"""

from __future__ import annotations

from src.prism_template_validation import is_blank, required_field_paths
from src.template_save import gate_findings, gate_schema

# Fields a reusable instrument description should have beyond the required ones. One list, edited here.
RECOMMENDED = (
    "Study/ShortName",
    "Study/Version",
    "Study/Authors",
    "Study/DOI",
    "Study/Construct",
    "Study/Description",
    "Study/Instructions",
)


def _percent(filled: int, total: int) -> int:
    return round(100 * filled / total) if total else 100


def template_completeness(
    template: dict, *, source: str, app_root=None, schema_version: str = "stable", project: bool = True
) -> dict:
    """``required`` / ``recommended`` (``total``, ``filled``, ``missing`` paths), ``problems`` (other errors that stop
    the template from being used, for example a language it uses but does not declare), ``complete`` (usable) and
    ``percent``. ``project=True`` is a project copy; ``project=False`` a library template (global fields only)."""
    schema = gate_schema(app_root=app_root, schema_version=schema_version, project=project)
    required = required_field_paths(schema)
    errors = gate_findings(template, source=source, schema=schema)
    missing = [e["path"] for e in errors if e["path"] in required]
    problems = [e["message"] for e in errors if e["path"] not in required]

    template = template if isinstance(template, dict) else {}

    def blank(path: str) -> bool:
        section, field = path.split("/")
        values = template.get(section)
        return not isinstance(values, dict) or is_blank(values.get(field))

    missing_recommended = [path for path in RECOMMENDED if blank(path)]
    return {
        "required": {"total": len(required), "filled": len(required) - len(missing), "missing": missing},
        "recommended": {
            "total": len(RECOMMENDED),
            "filled": len(RECOMMENDED) - len(missing_recommended),
            "missing": missing_recommended,
        },
        "problems": problems,
        "complete": not errors,
        "percent": {
            "required": _percent(len(required) - len(missing), len(required)),
            "recommended": _percent(len(RECOMMENDED) - len(missing_recommended), len(RECOMMENDED)),
        },
    }
