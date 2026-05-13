import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_EDITOR_TEMPLATE = REPO_ROOT / "app" / "templates" / "template_editor.html"
TEMPLATE_EDITOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "template-editor.js"
TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT = (
    REPO_ROOT / "app" / "static" / "js" / "template-editor" / "source-workflow.js"
)
TEMPLATE_EDITOR_BLUEPRINT = (
    REPO_ROOT
    / "app"
    / "src"
    / "web"
    / "blueprints"
    / "tools_template_editor_blueprint.py"
)


class TestTemplateEditorWorkflowWiring(unittest.TestCase):
    def test_template_editor_uses_shared_header_and_help_panel_macros(self):
        content = TEMPLATE_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)

    def test_template_editor_exposes_modality_selector_with_survey_default(self):
        content = TEMPLATE_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="modality"', content)
        self.assertIn('<option value="survey" selected>survey</option>', content)
        self.assertIn('<option value="biometrics">biometrics</option>', content)
        self.assertIn(
            'Choose modality first (default: survey), then select a template from the dropdown to load it, or click Create to start a new one.',
            content,
        )

    def test_template_editor_save_tooltip_matches_guarded_overwrite_flow(self):
        content = TEMPLATE_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            'title="Saves to project/code/library/{modality}/ and confirms before replacing an existing project template."',
            content,
        )

    def test_template_editor_uses_api_fallback_for_editor_requests(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "const sharedApiModuleUrl = new URL('./shared/api.js', document.currentScript?.src || window.location.href).href;",
            script_content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", script_content)
        self.assertIn(
            "sharedFetchWithApiFallbackPromise = import(sharedApiModuleUrl).then(({ fetchWithApiFallback }) => {",
            script_content,
        )
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            script_content,
        )
        self.assertIn(
            "const templateEditorSourceWorkflowModuleUrl = new URL('./template-editor/source-workflow.js', document.currentScript?.src || window.location.href).href;",
            script_content,
        )
        self.assertIn(
            "templateEditorSourceWorkflowPromise = import(templateEditorSourceWorkflowModuleUrl).then((module) => {",
            script_content,
        )
        self.assertIn(
            "|| typeof module.bindTemplateEditorSourceWorkflowEvents !== 'function'",
            script_content,
        )
        self.assertIn(
            "const res = await fetchWithApiFallback(url, { method: 'GET' });",
            script_content,
        )
        self.assertIn("const res = await fetchWithApiFallback(url, {", script_content)
        self.assertIn(
            "await context.fetchWithApiFallback('/api/template-editor/download', {",
            workflow_content,
        )
        self.assertIn(
            "await context.fetchWithApiFallback('/api/template-editor/import-lsq-lsg', {",
            workflow_content,
        )
        self.assertIn(
            "await context.fetchWithApiFallback('/api/survey-generate-templates', {",
            workflow_content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/template-editor/export-questionnaire', {",
            script_content,
        )
        self.assertIn(
            "await context.fetchWithApiFallback('/api/template-editor/delete', {",
            workflow_content,
        )

    def test_template_editor_import_sets_explicit_editable_state(self):
        content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Importing a template source will discard them. Continue?')) {",
            content,
        )
        self.assertIn(
            "context.currentTemplateFilename = context.normalizeTemplateFilename(data.suggested_filename, context.modalityEl.value, context.currentTemplate);",
            content,
        )
        self.assertIn("context.loadedFromReadonly = false;", content)
        self.assertIn("context.hasUserInteracted = true;", content)
        self.assertIn("context.hasExplicitTemplate = true;", content)
        self.assertIn("context.clearTemplateSelections();", content)

    def test_template_editor_filename_normalization_uses_biometrics_test_name(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function getTemplateNameCandidate(obj, modality) {", content)
        self.assertIn("extractTemplateNameValue(study.BiometricName)", content)
        self.assertIn("extractTemplateNameValue(study.OriginalName)", content)
        self.assertIn(
            "const expectedPrefix = modality === 'biometrics' ? 'biometrics-' : 'survey-';",
            content,
        )
        self.assertIn(
            "const finalStem = safeStem === 'template' ? fallbackStem : safeStem;",
            content,
        )

    def test_template_editor_save_replaces_generic_placeholder_filenames(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn("function isGenericTemplateFilename(filename, modality) {", script_content)
        self.assertIn("function resolveTemplateFilenameForSave(templateObj, modality) {", script_content)
        self.assertIn("return ['template', 'new', 'imported'].includes(stem);", script_content)
        self.assertIn("if (isGenericTemplateFilename(currentTemplateFilename, modality)) {", script_content)
        self.assertIn("const filename = context.resolveTemplateFilenameForSave(obj, modality);", workflow_content)
        self.assertIn(
            "const filename = context.resolveTemplateFilenameForSave(obj, context.modalityEl.value);",
            workflow_content,
        )

    def test_template_editor_import_and_delete_restore_visible_state(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn("function captureEditorState() {", script_content)
        self.assertIn("function restoreEditorState(state) {", script_content)
        self.assertIn("context.restoreEditorState(previousEditorState);", workflow_content)
        self.assertIn("Validation could not be completed:", workflow_content)
        self.assertIn("context.btnDownload.disabled = false;", workflow_content)
        self.assertIn("context.originalTemplate = null;", workflow_content)
        self.assertIn("context.selectedItemId = null;", workflow_content)
        self.assertIn("context.renderAll();", workflow_content)

    def test_template_editor_project_switch_invalidates_project_bound_actions(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )
        blueprint_content = TEMPLATE_EDITOR_BLUEPRINT.read_text(encoding="utf-8")

        self.assertIn("function getCurrentProjectPath() {", script_content)
        self.assertIn(
            "async function bindTemplateEditorSourceWorkflowEvents() {",
            script_content,
        )
        self.assertIn(
            "function handleProjectContextChange(previousProjectPath, nextProjectPath) {",
            script_content,
        )
        self.assertIn("let loadedTemplateProjectPath = '';", script_content)
        self.assertIn("let projectContextRequestToken = 0;", script_content)
        self.assertIn("project_path: currentProjectPath,", workflow_content)
        self.assertIn(
            "window.addEventListener('prism-project-changed', async () => {",
            workflow_content,
        )
        self.assertIn("The editor kept the content as a detached draft", script_content)
        self.assertIn(
            "Saved to the previous project library before the active project changed.",
            workflow_content,
        )
        self.assertIn('request.args.get("project_path")', blueprint_content)
        self.assertIn(
            'explicit_project_path=payload.get("project_path")', blueprint_content
        )

    def test_template_editor_schema_switch_refreshes_schema_aware_template_statuses(
        self,
    ):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "return workflow.bindTemplateEditorSourceWorkflowEvents(buildTemplateEditorSourceWorkflowContext());",
            script_content,
        )
        self.assertIn(
            "context.schemaEl.addEventListener('change', async () => {",
            workflow_content,
        )
        self.assertIn("await refreshTemplateList(context);", workflow_content)
        self.assertIn("await loadNewTemplate(context);", workflow_content)

    def test_template_editor_switch_cancel_and_failure_revert_select_state(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn("function getTrackedSelectValue(selectEl) {", script_content)
        self.assertIn("function commitTrackedSelectValue(selectEl) {", script_content)
        self.assertIn(
            "function revertTrackedSelectValue(selectEl, fallbackValue = '') {",
            script_content,
        )
        self.assertIn(
            "const previousModality = context.getTrackedSelectValue(context.modalityEl);",
            workflow_content,
        )
        self.assertIn(
            "context.revertTrackedSelectValue(context.modalityEl, previousModality);",
            workflow_content,
        )
        self.assertIn(
            "context.commitTrackedSelectValue(context.modalityEl);",
            workflow_content,
        )
        self.assertIn(
            "const previousSchemaVersion = context.getTrackedSelectValue(context.schemaEl);",
            workflow_content,
        )
        self.assertIn(
            "context.revertTrackedSelectValue(context.schemaEl, previousSchemaVersion);",
            workflow_content,
        )
        self.assertIn(
            "context.commitTrackedSelectValue(context.schemaEl);",
            workflow_content,
        )
        self.assertIn("await context.refreshSchema();", workflow_content)
        self.assertIn("loadedTemplateProjectPath = '';", script_content)

    def test_template_editor_failed_template_load_restores_previous_editor_state(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "function captureEditorState() {",
            script_content,
        )
        self.assertIn(
            "context.projectTemplateSelectEl.addEventListener('change', async () => {",
            workflow_content,
        )
        self.assertIn(
            "context.globalTemplateSelectEl.addEventListener('change', async () => {",
            workflow_content,
        )
        self.assertIn(
            "const previousEditorState = context.captureEditorState();",
            workflow_content,
        )
        self.assertIn("context.restoreEditorState(previousEditorState);", workflow_content)
        self.assertIn(
            "export async function loadSelectedTemplate(context) {",
            workflow_content,
        )

    def test_template_editor_blank_template_creation_is_guarded_and_rollback_safe(self):
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "context.btnNew.addEventListener('click', async () => {",
            workflow_content,
        )
        self.assertIn(
            "if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Create a new blank template and discard them?')) {",
            workflow_content,
        )
        self.assertIn(
            "const previousEditorState = context.captureEditorState();",
            workflow_content,
        )
        self.assertIn("context.restoreEditorState(previousEditorState);", workflow_content)

    def test_template_editor_save_requests_explicit_overwrite_permission(self):
        script_content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")
        workflow_content = TEMPLATE_EDITOR_SOURCE_WORKFLOW_SCRIPT.read_text(
            encoding="utf-8"
        )

        self.assertIn("function getSaveDecision(filename) {", script_content)
        self.assertIn(
            'A project template named "${filename}" already exists. Overwrite it?',
            script_content,
        )
        self.assertIn(
            'This template comes from a read-only library. Save an editable project copy as "${filename}"?',
            script_content,
        )
        self.assertIn("allow_overwrite: saveDecision.allowOverwrite,", workflow_content)

    def test_template_editor_save_api_rejects_unconfirmed_conflicts(self):
        content = TEMPLATE_EDITOR_BLUEPRINT.read_text(encoding="utf-8")

        self.assertIn(
            'allow_overwrite = bool(payload.get("allow_overwrite", False))', content
        )
        self.assertIn("if path.exists() and not allow_overwrite:", content)
        self.assertIn('"code": "file_exists"', content)

    def test_template_editor_add_item_mode_controls_exist(self):
        content = TEMPLATE_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="newItemMode"', content)
        self.assertIn('value="blank"', content)
        self.assertIn('value="copy-style"', content)
        self.assertIn('id="copyStyleSourceItem"', content)

    def test_template_editor_add_item_supports_copy_style_mode(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function buildNewItemFromSelection(itemSchema)", content)
        self.assertIn("Choose a source item to copy its style.", content)
        self.assertIn("Style copied from", content)
        self.assertIn("description was cleared.", content)

    def test_template_editor_copy_style_mode_prefers_selected_item_and_quick_action(
        self,
    ):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function updateCopyStyleSourceOptions(options = {})", content)
        self.assertIn("const { preferSelected = false } = options;", content)
        self.assertIn(
            "if (preferSelected && selectedItemId && keys.includes(selectedItemId)) {",
            content,
        )
        self.assertIn("updateNewItemModeUI({ preferSelected: true });", content)
        self.assertIn("copyStyleBtn.innerHTML = '<i class=\"fas fa-copy me-1\"></i>Copy Style';", content)
        self.assertIn("newItemModeEl.value = 'copy-style';", content)
        self.assertIn("copyStyleSourceItemEl.value = k;", content)
        self.assertIn("Style source set to <code>${escapeHtml(k)}</code>", content)

    def test_template_editor_item_delete_controls_exist_with_prefix_hint(self):
        content = TEMPLATE_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="btnDeleteItems"', content)
        self.assertIn(
            "Delete supports exact ID or prefix with <code>...</code>", content
        )
        self.assertIn("<code>59...</code>", content)

    def test_template_editor_item_delete_supports_selected_and_prefix_targets(self):
        content = TEMPLATE_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("const btnDeleteItems = document.getElementById('btnDeleteItems');", content)
        self.assertIn("function resolveDeletionTargets()", content)
        self.assertIn("if (rawInput.endsWith('...')) {", content)
        self.assertIn("function deleteTemplateItems()", content)
        self.assertIn(
            "Select items (checkboxes), or enter an item ID/prefix (for example 59...) before deleting.",
            content,
        )
        self.assertIn("btnDeleteItems.addEventListener('click', () => {", content)
        self.assertIn("deleteTemplateItems();", content)


if __name__ == "__main__":
    unittest.main()
