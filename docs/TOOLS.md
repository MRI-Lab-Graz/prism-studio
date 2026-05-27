# Tools

Use the Tools area after the project exists and the first round of imports is in
place.

This page helps you decide which tool matches the task in front of you.

## What the Tools area is for

The Tools area is where you refine, repair, and extend the project after the raw
import steps are done.

Common tasks include:

- finishing survey or biometrics templates
- editing JSON sidecars safely
- building scoring recipes
- renaming or reorganizing files more safely than by hand
- working with project-local library assets

## When to use Tools

Use the Tools area after:

1. the project exists
2. the initial import is done
3. the first validation pass has shown what still needs attention

That sequence makes the tool choice much clearer because you are reacting to a
specific need rather than exploring a menu blindly.

## Which tool should I open?

| If you need to... | Open this tool | Typical next step |
|---|---|---|
| Complete or fix a survey or biometrics template | Template Editor | Re-run validation |
| Edit a JSON sidecar or metadata file directly but safely | JSON Editor | Re-run validation |
| Create scoring logic from questionnaire items | Recipe Builder | Run the scoring workflow |
| Rename or reorganize files with structure awareness | File Management | Re-run validation |
| Reuse or inspect project-local assets | Library-related tools | Continue the workflow that uses those assets |

## The two highest-value beginner tools

For most new users, the most important tools are:

- **Template Editor**
- **Recipe Builder**

Why these matter first:

- Template Editor closes the gap between imported data and complete metadata.
- Recipe Builder closes the gap between raw responses and analysis-ready scores.

## Example: using Tools after a survey import

Typical path:

1. Import survey data.
2. Run validation.
3. Notice that the survey sidecar or template still lacks detail.
4. Open **Template Editor** and complete the missing information.
5. Re-run validation.
6. Open **Recipe Builder** and define one small score.
7. Run scoring and inspect the outputs.

This is the intended progression for many beginner projects.

## Tool selection rules of thumb

### Use Template Editor when the issue is about instrument structure

Examples:

- missing item descriptions
- missing response options
- missing administration details
- incomplete task or technical metadata

### Use Recipe Builder when the issue is about derived scores

Examples:

- total scores
- subscales
- reverse coding
- derived columns used for later analysis

### Use JSON Editor when you already know exactly which metadata file needs a
targeted edit

This is useful for precise metadata work, but Template Editor is often the safer
starting point for surveys and biometrics.

### Use File Management when the problem is structural rather than semantic

Examples:

- entity renaming
- safer reorganizing of files
- cleanup that should still respect the dataset structure

## Common mistakes

- opening multiple tools before deciding the actual task
- trying to use Recipe Builder before the imported data and templates are stable
- editing metadata in JSON Editor when Template Editor is the safer workflow
- forgetting to validate again after a structural or metadata change

## Detailed guides

- [TEMPLATE_EDITOR.md](TEMPLATE_EDITOR.md)
- [RECIPE_BUILDER.md](RECIPE_BUILDER.md)
- [ANALYSIS_OUTPUT.md](ANALYSIS_OUTPUT.md)
- [VALIDATOR.md](VALIDATOR.md)