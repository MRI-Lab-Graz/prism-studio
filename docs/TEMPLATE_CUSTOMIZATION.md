# Template Customization Workflow

This guide explains how to customize global survey templates for your specific study without modifying the shared library.

## 🎯 Key Principle: All Edits Go to Project Code Folder

> **IMPORTANT:** When you edit ANY template (global or project-local), all saves go to:
> ```
> {project}/code/library/{modality}/     ← Templates (data structure definitions)
> {project}/code/recipes/{modality}/     ← Recipes (scoring/transformation logic)
> ```
> Following YODA principles, all code-related files live under `code/`.
> 
> - ✅ Global templates/recipes remain **read-only** and unchanged
> - ✅ Your edits create a **project-local copy** automatically
> - ✅ Same filename = **automatic override** (project version is used instead of global)
> - ✅ Different filename = **new variant** (both templates available)

## Overview

PRISM uses a **two-tier template system**:

1. **Global Library** (Read-Only): Shared, validated templates in `official/library/survey/`
2. **Project Library** (Writable): Project-specific customizations in `{project}/code/library/survey/`

This design allows you to:
- ✅ Use validated, standardized templates from the global library
- ✅ Customize them for your specific study (e.g., paper-pencil vs. online)
- ✅ Keep your customizations separate from the global templates
- ✅ Update global templates without losing your customizations

## Common Customization Scenarios

### Scenario 1: Changing Survey Format (Online → Paper-Pencil)

**Problem**: You have a standardized questionnaire (e.g., PHQ-9) from the global library, but you administered it as a paper-pencil test instead of an online survey.

**Solution**:

1. **Open Template Editor**: Tools → Template Editor
2. **Select the global template**: Choose `survey-phq9.json` from the dropdown
3. **Load the template**: Click "Load Template"
   - You'll see a message: *"This template is from a read-only source (global). You can edit and download, but saving will require a different filename or project library."*
4. **Make your changes**:
   - Navigate to the `Technical` section
   - Change `SoftwarePlatform` from `"LimeSurvey"` to `"PaperPencil"`
   - Add any other study-specific modifications
5. **Save as project template**:
   - Keep the same filename (`survey-phq9.json`) **OR** use a new name (e.g., `survey-phq9-custom.json`)
   - Click "Save"
   - The template is now saved to your project's library: `{project}/code/library/survey/`

**Result**: Your project now has a customized version of PHQ-9 that takes **priority** over the global template when used in your dataset.

### Scenario 2: Adding Study-Specific Metadata

**Problem**: You want to add study-specific information (e.g., administration instructions, local IRB notes) to a global template.

**Solution**:

1. Load the global template in the Template Editor
2. Add fields to the `Study` section:
   ```json
   "Study": {
     "TaskName": "phq9",
     "OriginalName": "Patient Health Questionnaire-9",
     "AdministrationNotes": "Administered before fMRI scan",
     "LocalIRB": "Protocol #2024-123"
   }
   ```
3. Save with the same or a new filename to your project library

### Scenario 3: Language Customization

**Problem**: The global template has both German and English, but you only need English.

**Solution**:

1. Load the bilingual global template
2. Use `prism_tools.py` to build a single-language version:
   ```bash
   python prism_tools.py survey i18n-build official/library/survey/survey-phq9.json --lang en
   ```
3. This creates a clean English-only version
4. Alternatively, manually edit in the Template Editor to remove unwanted language keys

## Understanding Template Priority

When PRISM looks for a template named `survey-phq9.json`, it searches in this order:

1. **Project Library**: `{project}/code/library/survey/survey-phq9.json`
2. **Global Library**: `official/library/survey/survey-phq9.json`

If you create a project-local version with the **same filename**, it will be used instead of the global one.

### Viewing Template Sources

In the Template Editor, templates are marked with their source:
- 🌍 **global**: Read-only global library
- 📁 **project**: Writable project library
- 🔗 **project-external**: External library (configured in `.prismrc.json`)

## Best Practices

### ✅ DO:
- **Keep the same filename** when customizing a global template (it overrides automatically)
- **Document your changes** in the `Study.Notes` or `Metadata.CustomizationReason` field
- **Use descriptive filenames** if creating a substantially different variant (e.g., `survey-phq9-short.json`)
- **Test validation** after editing to ensure schema compliance

### ❌ DON'T:
- **Modify global templates directly** (they are read-only and shared across all projects)
- **Delete required fields** from the schema (use Template Editor validation to check)
- **Change item codes** (e.g., `PHQ01` → `PHQ001`) unless you understand the implications for scoring

## Working Without a Project

If you don't have a project selected:
- You can still **load and edit** templates from the global library
- You can **download** templates as JSON files
- You **cannot save** directly (saving requires a project library)

**Workaround**: Download the template, then manually place it in your dataset's library folder.

## Advanced: External Project Libraries

For shared projects (e.g., multi-site studies), you can configure an external library in `.prismrc.json`:

```json
{
  "templateLibraryPath": "/shared/nextcloud/study-abc/templates"
}
```

This allows multiple researchers to share customized templates without duplicating them in each project.

## Troubleshooting

### "Saving is disabled - no project selected"

**Cause**: The Template Editor can only save to a project library, not the global library.

**Solution**:
1. Go to Projects → Create or select a project
2. Return to the Template Editor
3. Try saving again

### "Template already exists"

**Cause**: You're trying to save a template with a filename that already exists in the project library.

**Solution**:
- **Option 1**: Overwrite by confirming the save operation
- **Option 2**: Change the filename to create a variant (e.g., `survey-phq9-v2.json`)

### "Validation failed after editing"

**Cause**: Your edits violated the PRISM schema requirements.

**Solution**:
1. Review the validation errors in the red alert box
2. Common issues:
   - Missing required fields (e.g., `Technical.StimulusType`)
   - Invalid values (e.g., wrong data type)
   - Nested structure violations
3. Use the "Schema" tab in the Template Editor to see requirements

## Integration with Converter

When using the LimeSurvey Converter (Tools → Converter):
- Generated templates are automatically saved to the **project library**
- They can be further customized in the Template Editor
- Use the "Save to Project" button to add them directly

## CLI Integration

You can also work with templates programmatically:

```bash
# List project templates
ls {project}/code/library/survey/

# Copy and customize a global template
cp official/library/survey/survey-phq9.json {project}/code/library/survey/
# Then edit manually or in Template Editor

# Build single-language version
python prism_tools.py survey i18n-build \
  {project}/code/library/survey/survey-phq9.json \
  --lang en \
  --output {project}/code/library/survey/survey-phq9-en.json
```

## Related Documentation

- [Survey Library & Workflow](SURVEY_LIBRARY.md): Global library structure and management
- [Global Library Configuration](GLOBAL_LIBRARY_CONFIG.md): Setting up global vs. project libraries
- [Template Editor Guide](WEB_INTERFACE.md#template-editor): Detailed editor features
- [Survey Specifications](specs/survey.md): Technical schema documentation

## Summary

The template customization workflow is designed to be **safe** and **flexible**:

1. **Global templates remain untouched** (read-only)
2. **Project customizations are isolated** (in project library)
3. **Priority system ensures** project versions override global ones
4. **No manual file management needed** (Template Editor handles everything)

This allows you to leverage standardized templates while adapting them to your specific study requirements.
