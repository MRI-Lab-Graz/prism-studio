import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_API_MODULE = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
PROJECTS_CORE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "core.js"
)
PROJECTS_EXPORT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "export.js"
)
PROJECTS_METADATA_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata.js"
)
PROJECTS_VALIDATION_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "validation.js"
)
OPEN_FORM_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "open_form.html"
)
STUDY_METADATA_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "study_metadata.html"
)
EXPORT_SECTION_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "export_section.html"
)
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"


class TestProjectsWorkflowWiring(unittest.TestCase):
    def test_shared_api_exports_desktop_fallback_helper(self):
        content = SHARED_API_MODULE.read_text(encoding="utf-8")

        self.assertIn("export async function fetchWithApiFallback(", content)
        self.assertIn("url.startsWith('/api/')", content)
        self.assertIn("return 'http://127.0.0.1:5001';", content)

    def test_new_project_draft_clear_uses_api_fallback(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("fetchWithApiFallback('/api/projects/current', {", content)

    def test_unsaved_new_project_detector_ignores_default_form_values(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "if (options.some(option => option.selected !== option.defaultSelected)) {",
            content,
        )
        self.assertIn(
            "if (field.checked !== field.defaultChecked) return true;", content
        )
        self.assertIn(
            "if ((field.value || '').trim() !== (field.defaultValue || '').trim()) {",
            content,
        )

    def test_file_browser_uses_fallback_and_button_rows(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("const res = await fetchWithApiFallback(url);", content)
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/browse-folder');",
            content,
        )
        self.assertIn(
            'class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-project-json text-start"',
            content,
        )
        self.assertIn(
            'class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-dir text-start bg-white"',
            content,
        )
        self.assertIn(
            'aria-label="Select project.json at ${_escHtml(data.project_json_path)}"',
            content,
        )

    def test_export_structure_shows_loading_and_failure_placeholders(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("let projectStructureLoadToken = 0;", content)
        self.assertIn(
            "renderProjectStructureStatus('Loading current project structure...');",
            content,
        )
        self.assertIn(
            "renderProjectStructureStatus('Could not load current project structure.', 'warning');",
            content,
        )
        self.assertIn(
            "const resp = await fetchWithApiFallback('/api/projects/export/structure', {",
            content,
        )

    def test_export_preferences_are_loaded_and_saved_via_project_namespace(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("let exportPreferencesLoadToken = 0;", content)
        self.assertIn("let isApplyingExportPreferences = false;", content)
        self.assertIn(
            "let lastLoadedExportPreferences = getDefaultExportPreferences();", content
        )
        self.assertIn("let lastExportStructureStatus = {", content)
        self.assertIn(
            "return fetchWithApiFallback('/api/projects/preferences/export', {", content
        )
        self.assertIn(
            "body: JSON.stringify({ project_path: projectPath, preferences: preferencesPatch }),",
            content,
        )
        self.assertIn(
            "/api/projects/preferences/export?project_path=${encodeURIComponent(requestProjectPath)}",
            content,
        )
        self.assertIn(
            "if (requestToken !== exportPreferencesLoadToken || requestProjectPath !== resolveCurrentProjectPath()) {",
            content,
        )
        self.assertIn("loadExportPreferences();", content)
        self.assertIn(
            "exclude_sessions: _getUncheckedValues('export-session-filter')", content
        )
        self.assertIn(
            "exclude_modalities: _getUncheckedValues('export-modality-filter')", content
        )
        self.assertIn("exclude_acq: _getUncheckedAcqByModality(),", content)
        self.assertIn("validation_mode: 'both',", content)
        self.assertIn(
            "saveExportPreferencesPatch({ validation_mode: getSelectedExportValidationMode() });",
            content,
        )
        self.assertIn("updateExportSnapshotUi();", content)

    def test_export_summary_ui_wiring_present(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("function updateExportSnapshotUi() {", content)
        self.assertIn(
            "function setExportChipState(chipId, text, tone = 'neutral') {", content
        )
        self.assertIn("function countExcludedAcqLabels(excludedAcq) {", content)
        self.assertIn("exportScopeSummary", content)
        self.assertIn("exportDestinationSummary", content)
        self.assertIn("exportPreferenceSummary", content)
        self.assertIn("exportSessionsChip", content)
        self.assertIn("exportModalitiesChip", content)
        self.assertIn("exportAcqChip", content)

    def test_export_actions_use_desktop_api_fallback(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "const resp = await fetchWithApiFallback('/api/projects/export/browse-folder', { method: 'POST' });",
            content,
        )
        self.assertIn(
            "const resp = await fetchWithApiFallback('/api/projects/export/defacing-report', {",
            content,
        )
        self.assertIn(
            "const startResp = await fetchWithApiFallback('/api/projects/export/start', {",
            content,
        )
        self.assertIn("validation_mode: selectedValidationMode,", content)
        self.assertIn("async function requestCancelForActiveJob() {", content)
        self.assertIn("await requestCancelForActiveJob();", content)
        self.assertIn("const statusResp = await fetchWithApiFallback(", content)
        self.assertIn(
            "fetchWithApiFallback(`/api/projects/export/${encodeURIComponent(jobId)}/cancel`, { method: 'DELETE' })",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/anc-export', {",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback(`/api/projects/openminds-tasks${params}`);",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/openminds-export', {",
            content,
        )

    def test_create_and_init_flows_use_fallback_and_refresh_project_sections(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/init-on-bids', {",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/create', {",
            content,
        )
        self.assertIn("showStudyMetadataCard();", content)
        self.assertIn("showExportCard();", content)
        self.assertIn("showMethodsCard();", content)

    def test_open_project_flow_separates_load_and_validation(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "async function loadProjectWithoutValidation(path, triggerButton = null)",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/current', {",
            content,
        )
        self.assertIn(
            "await loadProjectWithoutValidation(getOpenProjectActionPath(), btn);",
            content,
        )
        self.assertIn(
            "async function runProjectValidation(path, triggerButton = null)",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/validate', {",
            content,
        )
        self.assertIn("await loadProjectWithoutValidation(path);", content)
        self.assertIn("function renderProjectQuickSummary(summary) {", content)
        self.assertIn("const projectSummary = result.project_summary", content)
        self.assertIn("renderLoadedProjectState(loadedName, loadedPath, projectSummary);", content)

    def test_preserved_project_shows_open_section_without_validation(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("function ensureOpenSectionVisibleForLoadedProject() {", content)
        self.assertIn("if (!path || !shouldHideProjectTypeSelectionWhenLoaded()) {", content)
        self.assertIn("selectProjectType('open');", content)
        self.assertIn("ensureOpenSectionVisibleForLoadedProject();", content)

    def test_navbar_recent_project_redirect_does_not_request_auto_validation(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            'window.location.href = "{{ url_for(\'projects.projects_page\') }}?preserve_current=1";',
            content,
        )
        self.assertNotIn("show_open_validation=1", content)

    def test_metadata_reset_clears_validation_state(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "el.classList.remove('is-invalid', 'required-field-empty', 'required-field-filled');",
            content,
        )
        self.assertIn("el.removeAttribute('aria-invalid');", content)
        self.assertIn("el.setCustomValidity('');", content)

    def test_metadata_actions_use_fallback_project_targeting_and_stale_guards(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { fetchWithApiFallback } from '../../shared/api.js';", content
        )
        self.assertIn("const r = await fetchWithApiFallback('/api/config');", content)
        self.assertIn("let metadataLoadToken = 0;", content)
        self.assertIn("let methodsRequestToken = 0;", content)
        self.assertIn(
            "_withProjectPathQuery('/api/projects/citation/status', requestProjectPath)",
            content,
        )
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath })", content
        )
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath, schema_version: schemaVersion })",
            content,
        )
        self.assertIn(
            "_withProjectPathQuery('/api/projects/description', requestProjectPath)",
            content,
        )
        self.assertIn(
            "_withProjectPathQuery('/api/projects/study-metadata', requestProjectPath)",
            content,
        )
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath, language: lang, detail_level: detailLevel, continuous: continuous })",
            content,
        )
        self.assertIn(
            "if (requestToken !== methodsRequestToken || requestProjectPath !== _getCurrentProjectPath()) {",
            content,
        )
        self.assertIn("if (currentProjectPath !== lastMethodsProjectPath) {", content)

    def test_file_browser_template_announces_dynamic_updates(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="fsBrowserList" aria-live="polite"', content)
        self.assertIn(
            'id="fsBrowserSelectedHint" style="display:none;" role="status" aria-live="polite"',
            content,
        )

    def test_open_form_exposes_quick_validate_control(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="quickValidateProjectBtn"', content)
        self.assertIn('Quick Validate', content)

    def test_project_box_exposes_preliminary_save_button_with_shared_submit_path(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn('id="projectBoxPreliminarySaveBtn"', content)
        self.assertIn("document.getElementById('projectBoxPreliminarySaveBtn')", content)
        self.assertIn("requestStudyMetadataSaveFromProjectBox();", content)

    def test_eligibility_requires_two_combined_criteria_instead_of_both_lists(self):
        metadata_content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        validation_content = PROJECTS_VALIDATION_MODULE.read_text(encoding="utf-8")
        template_content = STUDY_METADATA_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("Eligibility: new Set(['InclusionCriteria'])", metadata_content)
        self.assertIn("const eligibilityCriteriaTotal =", metadata_content)
        self.assertIn(
            "addField('Eligibility', 'InclusionCriteria', eligibilityCriteriaTotal >= 2);",
            metadata_content,
        )
        self.assertIn("export function validateEligibilityCriteriaBadges()", validation_content)
        self.assertIn("totalCriteria >= 2", validation_content)
        self.assertIn('id="smEligCriteriaRequiredBadge"', template_content)
        self.assertIn('id="smEligExclusionOptionalBadge"', template_content)

    def test_export_template_includes_pre_export_validation_mode_selector(self):
        content = EXPORT_SECTION_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="exportValidationMode"', content)
        self.assertIn('value="both"', content)
        self.assertIn('value="prism"', content)
        self.assertIn('value="bids"', content)
        self.assertIn('value="ignore"', content)


if __name__ == "__main__":
    unittest.main()
