"""
PRISM to Pavlovia/PsychoPy Converter

Converts PRISM survey JSON to PsychoPy experiment format (.psyexp) for use with Pavlovia.

Usage:
    python src/converters/pavlovia.py task-bdi_beh.json
    python src/converters/pavlovia.py task-bdi_beh.json --output ./experiments/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from defusedxml import ElementTree as ET
from defusedxml import minidom
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


def extract_questions(prism_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract question data from PRISM JSON, filtering out metadata sections."""
    questions = []
    metadata_keys = {"Technical", "Study", "Metadata", "I18n", "Scoring"}

    for key, value in prism_json.items():
        if key not in metadata_keys and isinstance(value, dict):
            question = {
                "code": key,
                "description": value.get("Description", ""),
                "type": value.get("QuestionType", ""),
                "levels": value.get("Levels", {}),
                "items": value.get("Items", {}),
                "mandatory": value.get("Mandatory", False),
                "condition": value.get("Condition", None),
                "help": value.get("HelpText", None),
                "position": value.get("Position", {}),
            }
            questions.append(question)

    # Sort by group order and question order
    questions.sort(
        key=lambda q: (
            q["position"].get("GroupOrder", 0),
            q["position"].get("QuestionOrder", 0),
        )
    )

    return questions


def determine_component_type(question: Dict[str, Any]) -> str:
    """Determine the best PsychoPy component type for a question.

    Returns:
        "form": Form component (best for multiple choice with many options)
        "slider": Slider component (good for Likert scales)
        "textbox": Textbox component (for free text)
        "loop": Loop with conditions (for array questions)
    """
    q_type = question.get("type", "").lower()
    has_levels = bool(question.get("levels"))
    has_items = bool(question.get("items"))

    # Array questions need loops
    if has_items:
        return "loop"

    # Free text questions
    if "text" in q_type and not has_levels:
        return "textbox"

    # Scale questions (1-5, 1-7, etc.) work well as sliders
    if has_levels:
        level_keys = list(question["levels"].keys())
        try:
            numeric_keys = [int(k) for k in level_keys]
            if len(numeric_keys) >= 3 and max(numeric_keys) - min(numeric_keys) <= 10:
                return "slider"
        except (ValueError, TypeError):
            pass

    # Default: form component for multiple choice
    return "form"


def create_conditions_csv(
    questions: List[Dict[str, Any]], output_dir: Path
) -> Optional[Path]:
    """Create conditions spreadsheet for loop-based questions."""
    conditions_data = []

    for q in questions:
        if q.get("items"):
            # Expand array questions into rows
            for item_code, item_data in q["items"].items():
                row = {
                    "question_code": f"{q['code']}_{item_code}",
                    "question_text": item_data.get("Description", ""),
                    "parent_code": q["code"],
                    "item_order": item_data.get("Order", 0),
                }

                # Add levels if present
                if q.get("levels"):
                    for level_key, level_text in q["levels"].items():
                        row[f"level_{level_key}"] = level_text

                conditions_data.append(row)
        else:
            # Regular questions (one row each)
            row = {
                "question_code": q["code"],
                "question_text": q["description"],
                "question_type": q.get("type", ""),
            }

            # Add levels
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


def build_psyexp_xml(
    task_name: str,
    questions: List[Dict[str, Any]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Build the PsychoPy .psyexp XML structure.

    This creates a minimal but functional experiment with:
    - Welcome screen
    - Question routines (one per question or question group)
    - Thank you screen
    - Flow connecting all routines
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
    # Add text component parameters
    _add_component_param(welcome_text, "text", f"Welcome to {task_name}")
    _add_component_param(welcome_text, "pos", "[0, 0]")
    _add_component_param(welcome_text, "height", "0.05")

    welcome_key = ET.SubElement(welcome_routine, "KeyboardComponent")
    welcome_key.set("name", "welcome_key")
    _add_component_param(welcome_key, "keys", "['space']")
    _add_component_param(welcome_key, "text", "Press SPACE to continue")

    # 2. Question routines
    # Group questions by their group name
    grouped_questions: Dict[str, List[Dict[str, Any]]] = {}
    for q in questions:
        group = q["position"].get("Group", "questions")
        if group not in grouped_questions:
            grouped_questions[group] = []
        grouped_questions[group].append(q)

    # Create a routine for each group
    for group_name, group_questions in grouped_questions.items():
        routine = ET.SubElement(routines, "Routine")
        routine_name = f"group_{group_name.lower().replace(' ', '_')}"
        routine.set("name", routine_name)

        # For now, create a simple form component
        # Planned: Add specialized components for sliders, textboxes, and loops.
        form_items = []
        for q in group_questions:
            form_items.append(create_psychopy_form_item(q))

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

    # Add welcome
    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "welcome")

    # Add question routines
    for group_name in grouped_questions.keys():
        routine_name = f"group_{group_name.lower().replace(' ', '_')}"
        flow_item = ET.SubElement(flow, "Routine")
        flow_item.set("name", routine_name)

    # Add thanks
    flow_item = ET.SubElement(flow, "Routine")
    flow_item.set("name", "thanks")

    # Convert to pretty XML string
    xml_str = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent="  ")

    return pretty_xml


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
) -> Path:
    """Main export function.

    Args:
        json_path: Path to PRISM survey JSON
        output_dir: Output directory (default: ./task-name/)
        experiment_name: Override experiment name

    Returns:
        Path to created .psyexp file
    """
    # Load PRISM data
    prism_json = load_prism_json(json_path)

    # Extract metadata
    technical = prism_json.get("Technical", {})
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
    questions = extract_questions(prism_json)
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
        )

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
