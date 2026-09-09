"""
PRISM to Pavlovia/PsychoPy Converter

Converts PRISM survey JSON to PsychoPy experiment format (.psyexp) for use with Pavlovia.

Usage:
    python src/converters/pavlovia.py task-bdi_beh.json
    python src/converters/pavlovia.py task-bdi_beh.json --output ./experiments/
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from xml.etree import ElementTree as ET
try:
    from defusedxml import minidom
except ImportError:
    from xml.dom import minidom
import pandas as pd

# PsychoPy experiment template structure
PSYCHOPY_VERSION = "2024.1.1"
EXPERIMENT_SETTINGS = {
    "Data filename": "''",
    "Show info dlg": True,
    "Experiment info": {"participant": "", "session": "001"},
    "Enable Escape": True,
    "Logging level": "exp",
    "Window size (pixels)": [1920, 1080],
    "Full-screen window": True,
    "Color": "$[0,0,0]",
    "Color space": "rgb",
    "Units": "height",
}


def load_prism_json(json_path: Path) -> Dict[str, Any]:
    """Load and parse a PRISM survey JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def _extract_condition(value: Dict[str, Any]) -> Optional[str]:
    """Get the display-condition expression for a question, if any.

    Mirrors the precedence in app/src/limesurvey_exporter.py's
    _build_relevance_equation: explicit Relevance wins, then
    LimeSurvey.Relevance, then ConditionalDisplay.showWhen.
    """
    if "Relevance" in value:
        return value["Relevance"]
    limesurvey = value.get("LimeSurvey")
    if isinstance(limesurvey, dict) and "Relevance" in limesurvey:
        return limesurvey["Relevance"]
    conditional = value.get("ConditionalDisplay")
    if isinstance(conditional, dict):
        return conditional.get("showWhen") or None
    return None


def _resolve_text(value: Any, language: str) -> str:
    """Resolve a Description/Levels-label value to a plain string.

    The schema allows either a plain string or a per-language object
    ({"en": ..., "de": ...}). Prefer the requested language, fall back to
    any available language, fall back to empty string.
    """
    if isinstance(value, dict):
        if language in value:
            return str(value[language])
        for v in value.values():
            if v:
                return str(v)
        return ""
    if value is None:
        return ""
    return str(value)


def _get_active_variant_id(prism_json: Dict[str, Any]) -> Optional[str]:
    """The template's declared default/active variant, if any."""
    study = prism_json.get("Study")
    if isinstance(study, dict):
        version = study.get("Version")
        if version:
            return str(version)
    return None


def _resolve_item_for_variant(
    item: Dict[str, Any], variant_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Apply variant filtering/override to one item.

    Mirrors app/static/js/template-editor.js's own excludedByVariant check:
    an item with no (or empty) ApplicableVersions applies to every variant;
    otherwise it's excluded unless variant_id is explicitly listed.

    Returns the (possibly overridden) item dict, or None if excluded.
    """
    applicable = item.get("ApplicableVersions")
    if variant_id and isinstance(applicable, list) and applicable and variant_id not in applicable:
        return None

    variant_scales = item.get("VariantScales")
    if variant_id and isinstance(variant_scales, list):
        for scale in variant_scales:
            if isinstance(scale, dict) and scale.get("VariantID") == variant_id:
                merged = dict(item)
                for key in ("DataType", "MinValue", "MaxValue", "Levels", "ScaleType", "Unit"):
                    if key in scale:
                        merged[key] = scale[key]
                return merged

    return item


def extract_questions(
    prism_json: Dict[str, Any], language: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Extract question data from PRISM JSON, filtering out metadata sections."""
    if language is None:
        i18n = prism_json.get("I18n")
        language = (
            i18n.get("DefaultLanguage")
            if isinstance(i18n, dict) and i18n.get("DefaultLanguage")
            else "en"
        )

    active_variant = _get_active_variant_id(prism_json)
    questions = []
    metadata_keys = {"Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"}

    for key, value in prism_json.items():
        if key in metadata_keys or not isinstance(value, dict):
            continue

        resolved = _resolve_item_for_variant(value, active_variant)
        if resolved is None:
            continue

        raw_levels = resolved.get("Levels") if isinstance(resolved.get("Levels"), dict) else {}
        flat_levels = {
            level_key: _resolve_text(level_value, language)
            for level_key, level_value in raw_levels.items()
        }

        question = {
            "code": key,
            "description": _resolve_text(resolved.get("Description", ""), language),
            "levels": flat_levels,
            "raw_levels": raw_levels,
            "data_type": resolved.get("DataType", "string"),
            "scale_type": resolved.get("ScaleType"),
            "min_value": resolved.get("MinValue"),
            "max_value": resolved.get("MaxValue"),
            "mandatory": resolved.get("Mandatory", True),
            "condition": _extract_condition(resolved),
            "help": resolved.get("HelpText", None),
        }
        questions.append(question)

    return questions


def extract_questions_from_customized_group(
    group: Dict[str, Any], language: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Extract question data from one Survey Customizer group.

    Mirrors extract_questions()'s output shape, but reads from the
    customizer's `group["questions"]` list instead of a raw PRISM JSON
    file: filters to `enabled` questions, orders by `displayOrder`, and
    takes `mandatory` from the customizer's own field (a UI override) with
    each question's stored `originalData` as the fallback -- matching how
    the customizer's own LimeSurvey export already treats originalData as
    the source of truth for description/levels.

    A question's `runNumber` (set by the customizer's multi-run
    duplication) is appended to `code` as `_runNN` when greater than 1, so
    two runs of the same questionnaire never produce colliding output
    codes.
    """
    resolved_language = language or "en"
    ordered = sorted(
        (q for q in group.get("questions", []) if q.get("enabled", True)),
        key=lambda q: q.get("displayOrder", 0),
    )

    questions = []
    for q in ordered:
        original = q.get("originalData") or {}
        raw_levels = original.get("Levels") if isinstance(original.get("Levels"), dict) else {}
        flat_levels = {
            level_key: _resolve_text(level_value, resolved_language)
            for level_key, level_value in raw_levels.items()
        }

        run_number = q.get("runNumber", 1)
        code = q.get("questionCode", "")
        if run_number and run_number > 1:
            code = f"{code}_run{run_number:02d}"

        questions.append(
            {
                "code": code,
                "description": _resolve_text(
                    original.get("Description", q.get("description", "")), resolved_language
                ),
                "levels": flat_levels,
                "raw_levels": raw_levels,
                "data_type": original.get("DataType", q.get("dataType", "string")),
                "scale_type": original.get("ScaleType"),
                "min_value": original.get("MinValue", q.get("minValue")),
                "max_value": original.get("MaxValue", q.get("maxValue")),
                "mandatory": q.get("mandatory", original.get("Mandatory", True)),
                "condition": _extract_condition(original),
                "help": original.get("HelpText", q.get("help") or None),
            }
        )

    return questions


def determine_component_type(question: Dict[str, Any]) -> str:
    """Classify a question into a PsychoPy component type.

    Mirrors detectQuestionType's precedence in app/static/js/template-editor.js,
    adapted to the fields extract_questions produces (Task 2): a question with
    no Levels and no vas/visual-analogue ScaleType is free text; a
    vas/visual-analogue ScaleType is a slider regardless of Levels; otherwise
    the Levels count decides between a radio-style and dropdown-style choice
    list, matching the >10-options threshold the Studio's own Preview uses.
    """
    scale_type = (question.get("scale_type") or "").lower()
    if scale_type in ("vas", "visual-analogue"):
        return "slider"

    levels = question.get("levels") or {}
    if levels:
        return "dropdown" if len(levels) > 10 else "radio"

    return "free_text"


def _safe_component_name(code: str) -> str:
    """PsychoPy component names must be valid Python identifiers.

    Only replaces characters that are structurally invalid (not letters,
    digits, or underscore) -- an already-valid code passes through unchanged,
    per this plan's session-label/identifier constraint.
    """
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", code)
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    return safe


def _unique_routine_name(name: str, used: set) -> str:
    """PsychoPy-safe, unique routine name.

    Reuses _safe_component_name's identifier sanitizing and de-duplicates
    collisions with a numeric suffix -- two customizer groups can share a
    display name (e.g. two multi-run duplicates of the same
    questionnaire).
    """
    base = _safe_component_name(name) or "routine"
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}_{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def create_slider_component(question: Dict[str, Any]) -> Dict[str, str]:
    """Build a slider component dict for a VAS/visual-analogue question."""
    min_value = question.get("min_value")
    max_value = question.get("max_value")
    min_value = 0 if min_value is None else min_value
    max_value = 100 if max_value is None else max_value
    return {
        "name": _safe_component_name(question["code"]),
        "label": question.get("description", ""),
        "ticks": f"({min_value}, {max_value})",
        "granularity": "1",
    }


def create_textbox_component(question: Dict[str, Any]) -> Dict[str, str]:
    """Build a textbox component dict for a free-text question."""
    return {
        "name": _safe_component_name(question["code"]),
        "prompt": question.get("description", ""),
    }


def create_conditions_csv(
    questions: List[Dict[str, Any]],
    output_dir: Path,
    routine_labels: Optional[List[str]] = None,
) -> Optional[Path]:
    """Create conditions spreadsheet listing each question's code, text, type, and levels.

    routine_labels, when given, is a list parallel to `questions` naming
    which PsychoPy routine each question belongs to -- adds a `routine`
    column. Omitted for the existing single-routine callers, so their CSV
    shape is unchanged.
    """
    conditions_data = []

    for index, q in enumerate(questions):
        row = {}
        if routine_labels is not None:
            row["routine"] = routine_labels[index]
        row["question_code"] = q["code"]
        row["question_text"] = q["description"]
        row["question_type"] = determine_component_type(q)

        if q.get("levels"):
            for level_key, level_text in q["levels"].items():
                row[f"level_{level_key}"] = level_text

        conditions_data.append(row)

    if not conditions_data:
        return None

    df = pd.DataFrame(conditions_data)
    csv_path = output_dir / "conditions.csv"
    df.to_csv(csv_path, index=False)

    return csv_path


def create_psychopy_form_item(question: Dict[str, Any]) -> Dict[str, Any]:
    """Create a form item dict for PsychoPy Form component."""
    item = {
        "questionText": question["description"],
        "responseType": "choice" if question.get("levels") else "free",
    }

    if question.get("levels"):
        # Create choice options
        choices = []
        for key, text in question["levels"].items():
            choices.append(f"{key}: {text}")
        item["choices"] = choices

    if question.get("mandatory"):
        item["required"] = True

    return item


def build_psyexp_xml_grouped(
    task_name: str,
    routine_groups: List[Tuple[str, List[Dict[str, Any]]]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Build the PsychoPy .psyexp XML structure from one or more question routines.

    This creates a minimal but functional experiment with:
    - Welcome screen
    - One question routine per (routine_name, questions) pair in
      routine_groups, each holding a real component per question
      (SliderComponent/TextboxComponent/shared FormComponent, per
      determine_component_type), plus an optional CodeComponent for a
      non-null condition -- this only surfaces the PRISM condition text as a
      TODO comment for a researcher to translate manually; it does not gate
      visibility automatically
    - Thank you screen
    - Flow connecting all routines, in routine_groups order
    """

    root = ET.Element("PsychoPy2experiment")
    root.set("version", PSYCHOPY_VERSION)
    root.set("encoding", "utf-8")

    # Settings
    settings = ET.SubElement(root, "Settings")
    for key, value in EXPERIMENT_SETTINGS.items():
        param = ET.SubElement(settings, "Param")
        param.set("name", key)
        param.set("val", str(value))

    # Routines section
    routines = ET.SubElement(root, "Routines")

    # 1. Welcome routine
    welcome_routine = ET.SubElement(routines, "Routine")
    welcome_routine.set("name", "welcome")

    welcome_text = ET.SubElement(welcome_routine, "TextComponent")
    welcome_text.set("name", "welcome_text")
    _add_component_param(welcome_text, "text", f"Welcome to {task_name}")
    _add_component_param(welcome_text, "pos", "[0, 0]")
    _add_component_param(welcome_text, "height", "0.05")

    welcome_key = ET.SubElement(welcome_routine, "KeyboardComponent")
    welcome_key.set("name", "welcome_key")
    _add_component_param(welcome_key, "keys", "['space']")
    _add_component_param(welcome_key, "text", "Press SPACE to continue")

    # 2. One question routine per routine_groups entry
    for routine_name, questions in routine_groups:
        routine = ET.SubElement(routines, "Routine")
        routine.set("name", routine_name)

        form_items = []
        for q in questions:
            component_type = determine_component_type(q)
            safe_name = _safe_component_name(q["code"])

            if component_type == "slider":
                component = ET.SubElement(routine, "SliderComponent")
                component.set("name", safe_name)
                slider_params = create_slider_component(q)
                for key, value in slider_params.items():
                    if key != "name":
                        _add_component_param(component, key, value)
            elif component_type == "free_text":
                component = ET.SubElement(routine, "TextboxComponent")
                component.set("name", safe_name)
                textbox_params = create_textbox_component(q)
                for key, value in textbox_params.items():
                    if key != "name":
                        _add_component_param(component, key, value)
            else:
                # radio / dropdown -- batch into the shared form item list
                form_items.append(create_psychopy_form_item(q))

            if q.get("condition"):
                code_component = ET.SubElement(routine, "CodeComponent")
                code_component.set("name", f"{safe_name}_condition")
                _add_component_param(
                    code_component, "Begin Routine",
                    "# TODO: this question is conditionally displayed in PRISM:\n"
                    f"# {q['condition']}\n"
                    "# Translate this into PsychoPy/JS logic to gate visibility.\n"
                    f"{safe_name}_visible = True",
                )

        if form_items:
            form_component = ET.SubElement(routine, "FormComponent")
            form_component.set("name", f"form_{routine_name}")
            _add_component_param(form_component, "items", str(form_items))
            _add_component_param(form_component, "randomize", "False")

    # 3. Thank you routine
    thanks_routine = ET.SubElement(routines, "Routine")
    thanks_routine.set("name", "thanks")

    thanks_text = ET.SubElement(thanks_routine, "TextComponent")
    thanks_text.set("name", "thanks_text")
    _add_component_param(thanks_text, "text", "Thank you for participating!")
    _add_component_param(thanks_text, "pos", "[0, 0]")
    _add_component_param(thanks_text, "duration", "2.0")

    # Flow
    flow = ET.SubElement(root, "Flow")

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "welcome")

    for routine_name, _questions in routine_groups:
        flow_item = ET.SubElement(flow, "Routine")
        flow_item.set("name", routine_name)

    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "thanks")

    # Convert to pretty XML string
    xml_str = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_str)  # nosec B318 - xml_str is self-generated above, not untrusted input
    pretty_xml = dom.toprettyxml(indent="  ")

    return pretty_xml


def build_psyexp_xml(
    task_name: str,
    questions: List[Dict[str, Any]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Build a single-routine .psyexp -- the CLI/single-file export path.

    Thin wrapper over build_psyexp_xml_grouped with one routine named
    "questions", preserving this function's original single-routine output.
    """
    return build_psyexp_xml_grouped(task_name, [("questions", questions)], prism_metadata)


def _add_component_param(component: ET.Element, name: str, value: str) -> None:
    """Add a parameter to a PsychoPy component."""
    param = ET.SubElement(component, "Param")
    param.set("name", name)
    param.set("val", value)
    param.set("valType", "str")


def create_readme(output_dir: Path, task_name: str) -> None:
    """Create a README with instructions for using the exported experiment."""
    readme_content = f"""# {task_name} - Pavlovia Experiment

This experiment was automatically generated from PRISM survey data.

## Files

- `{task_name}.psyexp`: PsychoPy Builder experiment file
- `conditions.csv`: Trial/question parameters (if applicable)
- `README.md`: This file

## Usage

### Local Testing (PsychoPy)

1. Install PsychoPy: https://www.psychopy.org/download.html
2. Open `{task_name}.psyexp` in PsychoPy Builder
3. Click the green "Run" button to test locally

### Upload to Pavlovia

1. Create account at https://pavlovia.org
2. In PsychoPy Builder:
   - Click "Pavlovia" button (globe icon)
   - Log in to Pavlovia
   - Create new project or sync to existing
3. Set experiment to "RUNNING" on Pavlovia.org

### Collecting Data

- Share your Pavlovia URL with participants
- Data saves automatically to Pavlovia or OSF
- Download data from your Pavlovia dashboard

## Customization

This is a basic conversion. You may want to customize:

- **Visual appearance**: Edit text sizes, colors, positions in Builder
- **Instructions**: Modify welcome/thanks messages
- **Timing**: Add response time recording
- **Logic**: Add conditional display in Code components
- **Randomization**: Enable in loop settings

## Converting Data Back to PRISM

After collecting data on Pavlovia:

```bash
python src/converters/pavlovia.py --import pavlovia_data.csv task-{task_name}_beh.json
```

This will create PRISM-compatible TSV files.

## Support

- PRISM Documentation: docs/PAVLOVIA_EXPORT.md
- PsychoPy Forum: https://discourse.psychopy.org
- Pavlovia Help: https://pavlovia.org/docs
"""

    readme_path = output_dir / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")


def export_to_pavlovia(
    json_path: Path,
    output_dir: Optional[Path] = None,
    experiment_name: Optional[str] = None,
    language: Optional[str] = None,
) -> Path:
    """Main export function.

    Args:
        json_path: Path to PRISM survey JSON
        output_dir: Output directory (default: ./task-name/)
        experiment_name: Override experiment name
        language: Language code to export (default: template's own
            I18n.DefaultLanguage, falling back to "en"). Pavlovia export is
            single-language scoped -- this selects which language's text is
            used, it does not export multiple languages.

    Returns:
        Path to created .psyexp file
    """
    # Load PRISM data
    prism_json = load_prism_json(json_path)

    # Extract metadata
    study = prism_json.get("Study", {})

    # Determine task name
    if experiment_name:
        task_name = experiment_name
    else:
        task_name = study.get("TaskName", json_path.stem.replace("_beh", ""))

    # Set output directory
    if output_dir is None:
        output_dir = json_path.parent / f"task-{task_name}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🔄 Converting {json_path.name} to Pavlovia format...")
    print(f"📁 Output directory: {output_dir}")

    # Extract questions
    questions = extract_questions(prism_json, language=language)
    print(f"📋 Found {len(questions)} questions")

    # Create conditions CSV if needed
    conditions_path = create_conditions_csv(questions, output_dir)
    if conditions_path:
        print(f"📊 Created conditions spreadsheet: {conditions_path.name}")

    # Build .psyexp XML
    psyexp_content = build_psyexp_xml(task_name, questions, prism_json)
    psyexp_path = output_dir / f"{task_name}.psyexp"
    psyexp_path.write_text(psyexp_content, encoding="utf-8")
    print(f"✅ Created PsychoPy experiment: {psyexp_path.name}")

    # Create README
    create_readme(output_dir, task_name)
    print("📖 Created README with usage instructions")

    print(f"\n✨ Export complete! Open {psyexp_path.name} in PsychoPy Builder.")
    return psyexp_path


def generate_pavlovia_from_customization(
    groups: List[Dict[str, Any]],
    output_dir: Path,
    experiment_name: str,
    language: Optional[str] = None,
) -> Path:
    """Build a multi-routine Pavlovia/PsychoPy experiment from Survey
    Customizer groups -- one routine per non-empty group, in group order.

    Mirrors export_to_pavlovia's file-writing tail (conditions.csv,
    .psyexp, README.md) but sources questions from the customizer's
    `groups` model (already filtered/reordered/multi-run by the browser)
    via extract_questions_from_customized_group, instead of reading a raw
    PRISM JSON file.

    Raises:
        ValueError: every group came back empty after filtering (e.g. all
            questions disabled) -- there is nothing to export.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-seed with the two fixed routine names build_psyexp_xml_grouped
    # always adds, so a customizer group that happens to be named "welcome"
    # or "thanks" gets deduplicated instead of silently colliding with (and
    # making unreachable in the Flow) one of those fixed routines.
    used_names: set = {"welcome", "thanks"}
    routine_groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    for group in groups:
        questions = extract_questions_from_customized_group(group, language=language)
        if not questions:
            continue
        routine_name = _unique_routine_name(group.get("name") or "questions", used_names)
        routine_groups.append((routine_name, questions))

    if not routine_groups:
        raise ValueError("No enabled questions found in the selected groups")

    all_questions = [q for _name, questions in routine_groups for q in questions]
    routine_labels = [name for name, questions in routine_groups for _q in questions]
    create_conditions_csv(all_questions, output_dir, routine_labels=routine_labels)

    psyexp_content = build_psyexp_xml_grouped(experiment_name, routine_groups, {})
    psyexp_path = output_dir / f"{experiment_name}.psyexp"
    psyexp_path.write_text(psyexp_content, encoding="utf-8")

    create_readme(output_dir, experiment_name)

    return psyexp_path


def import_from_pavlovia(
    pavlovia_csv: Path,
    prism_json: Path,
    output_tsv: Optional[Path] = None,
) -> Optional[Path]:
    """Import Pavlovia data back to PRISM format.

    Args:
        pavlovia_csv: CSV file downloaded from Pavlovia
        prism_json: Original PRISM survey JSON (for column mapping)
        output_tsv: Output TSV path (default: auto-generated)

    Returns:
        Path to created TSV file
    """
    # Planned: Implement reverse conversion
    # - Map Pavlovia column names back to PRISM question codes
    # - Convert response formats
    # - Handle timing data (if present)
    print("⚠️  Import from Pavlovia not yet implemented")
    print("    Coming soon!")
    return None


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert PRISM survey JSON to Pavlovia/PsychoPy format"
    )
    parser.add_argument(
        "json_path",
        type=Path,
        help="Path to PRISM survey JSON file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output directory (default: ./task-name/)",
    )
    parser.add_argument(
        "--experiment-name",
        "-n",
        type=str,
        help="Override experiment name",
    )
    parser.add_argument(
        "--language",
        "-l",
        type=str,
        default=None,
        help="Language code to export (default: template's own default language)",
    )
    parser.add_argument(
        "--import",
        dest="import_mode",
        action="store_true",
        help="Import mode: convert Pavlovia data back to PRISM",
    )
    parser.add_argument(
        "--pavlovia-csv",
        type=Path,
        help="Pavlovia CSV file to import (for --import mode)",
    )

    args = parser.parse_args()

    if not args.json_path.exists():
        print(f"❌ Error: File not found: {args.json_path}")
        sys.exit(1)

    if args.import_mode:
        # Import mode
        if not args.pavlovia_csv:
            print("❌ Error: --pavlovia-csv required for import mode")
            sys.exit(1)
        result = import_from_pavlovia(
            args.pavlovia_csv,
            args.json_path,
        )
    else:
        # Export mode
        result = export_to_pavlovia(
            args.json_path,
            args.output,
            args.experiment_name,
            args.language,
        )

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
