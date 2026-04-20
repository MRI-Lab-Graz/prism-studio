import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_EDITOR_TEMPLATE = REPO_ROOT / "app" / "templates" / "template_editor.html"
TEMPLATE_EDITOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "template-editor.js"
TEMPLATE_EDITOR_BLUEPRINT = (
    REPO_ROOT
    / "app"
    / "src"
    / "web"
    / "blueprints"
    / "tools_template_editor_blueprint.py"
)


class TestTemplateEditorWorkflowWiring(unittest.TestCase):
    def test_template_editor_save_tooltip_matches_guarded_overwrite_flow(self):
        content = TEMPLATE_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            'title="Saves to project/code/library/{modality}/ and confirms before replacing an existing project template."',
            content,
        )

    def test_template_editor_uses_api_fallback_for_editor_requests(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "async function fetchWithApiFallback(url, options = {}, fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.')",
            content,
        )
        self.assertIn(
            "const res = await fetchWithApiFallback(url, { method: 'GET' });", content
        )
        self.assertIn("const res = await fetchWithApiFallback(url, {", content)
        self.assertIn(
            "await fetchWithApiFallback('/api/template-editor/download', {", content
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/template-editor/import-lsq-lsg', {",
            content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/limesurvey-to-prism', {", content
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/template-editor/export-questionnaire', {",
            content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/template-editor/delete', {", content
        )

    def test_template_editor_import_sets_explicit_editable_state(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "if (hasUnsavedChanges() && !confirm('You have unsaved changes. Importing a template source will discard them. Continue?')) {",
            content,
        )
        self.assertIn(
            "currentTemplateFilename = normalizeTemplateFilename(data.suggested_filename, modalityEl.value, currentTemplate);",
            content,
        )
        self.assertIn("loadedFromReadonly = false;", content)
        self.assertIn("hasUserInteracted = true;", content)
        self.assertIn("hasExplicitTemplate = true;", content)
        self.assertIn("clearTemplateSelections();", content)

    def test_template_editor_import_and_delete_restore_visible_state(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function captureEditorState() {", content)
        self.assertIn("function restoreEditorState(state) {", content)
        self.assertIn("restoreEditorState(previousEditorState);", content)
        self.assertIn("Validation could not be completed:", content)
        self.assertIn("btnDownload.disabled = false;", content)
        self.assertIn("originalTemplate = null;", content)
        self.assertIn("selectedItemId = null;", content)
        self.assertIn("renderAll();", content)

    def test_template_editor_project_switch_invalidates_project_bound_actions(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        blueprint_content = TEMPLATE_EDITOR_BLUEPRINT.read_text(encoding="utf-8")

        self.assertIn("function getCurrentProjectPath() {", script_content)
        self.assertIn(
            "function handleProjectContextChange(previousProjectPath, nextProjectPath) {",
            script_content,
        )
        self.assertIn("let loadedTemplateProjectPath = '';", script_content)
        self.assertIn("let projectContextRequestToken = 0;", script_content)
        self.assertIn("project_path: currentProjectPath,", script_content)
        self.assertIn(
            "window.addEventListener('prism-project-changed', async () => {",
            script_content,
        )
        self.assertIn("The editor kept the content as a detached draft", script_content)
        self.assertIn(
            "Saved to the previous project library before the active project changed.",
            script_content,
        )
        self.assertIn('request.args.get("project_path")', blueprint_content)
        self.assertIn(
            'explicit_project_path=payload.get("project_path")', blueprint_content
        )

    def test_template_editor_schema_switch_refreshes_schema_aware_template_statuses(
        self,
    ):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("schemaEl.addEventListener('change', async () => {", content)
        self.assertIn("await refreshTemplateList();", content)
        self.assertIn("await loadNewTemplate();", content)

    def test_template_editor_switch_cancel_and_failure_revert_select_state(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function getTrackedSelectValue(selectEl) {", content)
        self.assertIn("function commitTrackedSelectValue(selectEl) {", content)
        self.assertIn(
            "function revertTrackedSelectValue(selectEl, fallbackValue = '') {", content
        )
        self.assertIn(
            "const previousModality = getTrackedSelectValue(modalityEl);", content
        )
        self.assertIn(
            "revertTrackedSelectValue(modalityEl, previousModality);", content
        )
        self.assertIn("commitTrackedSelectValue(modalityEl);", content)
        self.assertIn(
            "const previousSchemaVersion = getTrackedSelectValue(schemaEl);", content
        )
        self.assertIn(
            "revertTrackedSelectValue(schemaEl, previousSchemaVersion);", content
        )
        self.assertIn("commitTrackedSelectValue(schemaEl);", content)
        self.assertIn("await refreshSchema();", content)
        self.assertIn("loadedTemplateProjectPath = '';", content)

    def test_template_editor_failed_template_load_restores_previous_editor_state(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "projectTemplateSelectEl.addEventListener('change', async () => {", content
        )
        self.assertIn(
            "globalTemplateSelectEl.addEventListener('change', async () => {", content
        )
        self.assertIn("const previousEditorState = captureEditorState();", content)
        self.assertIn("restoreEditorState(previousEditorState);", content)

    def test_template_editor_blank_template_creation_is_guarded_and_rollback_safe(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("btnNew.addEventListener('click', async () => {", content)
        self.assertIn(
            "if (hasUnsavedChanges() && !confirm('You have unsaved changes. Create a new blank template and discard them?')) {",
            content,
        )
        self.assertIn("const previousEditorState = captureEditorState();", content)
        self.assertIn("restoreEditorState(previousEditorState);", content)

    def test_template_editor_save_requests_explicit_overwrite_permission(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function getSaveDecision(filename) {", content)
        self.assertIn(
            'A project template named "${filename}" already exists. Overwrite it?',
            content,
        )
        self.assertIn(
            'This template comes from a read-only library. Save an editable project copy as "${filename}"?',
            content,
        )
        self.assertIn("allow_overwrite: saveDecision.allowOverwrite,", content)

    def test_template_editor_save_api_rejects_unconfirmed_conflicts(self):
        content = TEMPLATE_EDITOR_BLUEPRINT.read_text(encoding="utf-8")

        self.assertIn(
            'allow_overwrite = bool(payload.get("allow_overwrite", False))', content
        )
        self.assertIn("if path.exists() and not allow_overwrite:", content)
        self.assertIn('"code": "file_exists"', content)


if __name__ == "__main__":
    unittest.main()
