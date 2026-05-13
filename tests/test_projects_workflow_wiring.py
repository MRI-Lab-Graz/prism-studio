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
PROJECTS_PAGE_TEMPLATE = REPO_ROOT / "app" / "templates" / "projects.html"
STUDY_METADATA_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "study_metadata.html"
)
EXPORT_SECTION_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "export_section.html"
)
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"
LIBRARY_EDITOR_TEMPLATE = REPO_ROOT / "app" / "templates" / "library_editor.html"


class TestProjectsWorkflowWiring(unittest.TestCase):
    def test_shared_api_exports_desktop_fallback_helper(self):
        content = SHARED_API_MODULE.read_text(encoding="utf-8")

        self.assertIn("export async function fetchWithApiFallback(", content)
        self.assertIn("url.startsWith('/api/')", content)
        self.assertIn("return 'http://127.0.0.1:5001';", content)

    def test_new_project_draft_clear_uses_api_fallback(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("fetchWithApiFallback('/api/projects/current', {", content)

    def test_backend_monitoring_verbose_toggle_is_wired(self):
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        settings_template = (
            REPO_ROOT
            / "app"
            / "templates"
            / "includes"
            / "projects"
            / "settings_section.html"
        ).read_text(encoding="utf-8")

        self.assertIn("backendMonitoringVerboseToggle", settings_template)
        self.assertIn(
            "const verboseToggle = document.getElementById('backendMonitoringVerboseToggle');",
            core_content,
        )
        self.assertIn("backend_monitoring_verbose", core_content)

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
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/template-export', {",
            content,
        )
        self.assertIn("const templateExportButton = getById('templateExportButton');", content)
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

    def test_export_template_button_is_present_in_projects_export_section(self):
        content = EXPORT_SECTION_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="templateExportButton"', content)
        self.assertIn("Template Export", content)

    def test_export_async_completion_renders_saved_zip_path_from_status(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("const MAX_POLLS = 2250;", content)
        self.assertIn(
            "`/api/projects/export/${encodeURIComponent(jobId)}/status`",
            content,
        )
        self.assertIn("const savedPath = status.zip_path || 'unknown location';", content)
        self.assertIn("ZIP saved to:", content)
        self.assertIn("escapeHtml(savedPath)", content)

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

    def test_create_flow_checks_target_path_before_submitting(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("async function checkCreateTargetStatus() {", content)
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/path-status', {",
            content,
        )
        self.assertIn("const targetStatus = await checkCreateTargetStatus();", content)
        self.assertIn("if (targetStatus.conflict) {", content)
        self.assertIn("const fullPath = joinProjectTargetPath(projectPath, projectName);", content)

    def test_create_conflict_warning_can_open_existing_project(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("function submitOpenProjectPath(path) {", content)
        self.assertIn('data-action="open-existing-project"', content)
        self.assertIn(
            "const openExistingBtn = event.target.closest('[data-action=\"open-existing-project\"]');",
            content,
        )
        self.assertIn("submitOpenProjectPath(path);", content)

    def test_open_project_flow_separates_load_and_validation(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "async function loadProjectWithoutValidation(path, triggerButton = null, options = {})",
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
        self.assertIn(
            "await loadProjectWithoutValidation(path, null, { skipContextGuard: true });",
            content,
        )
        self.assertIn("function renderProjectQuickSummary(summary) {", content)
        self.assertIn("const projectSummary = result.project_summary", content)
        self.assertIn("renderLoadedProjectState(loadedName, loadedPath, projectSummary);", content)

    def test_loaded_project_state_exposes_validate_now_action(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("<strong>Not validated yet.</strong>", content)
        self.assertIn('class="validation-result pending', content)
        self.assertIn('data-action="validate-project"', content)
        self.assertIn(
            "const validateProjectBtn = event.target.closest('[data-action=\"validate-project\"]');",
            content,
        )
        self.assertIn(
            "runProjectValidation(validateProjectBtn.dataset.path || getOpenProjectActionPath());",
            content,
        )
        self.assertIn("id=\"projectBoxSaveBtn\"", content)
        self.assertIn("Save Changes to Project", content)

    def test_project_validation_surfaces_sociodemographics_action_for_participants_mismatch(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("function getProjectValidationAction(code) {", content)
        self.assertIn("normalizedCode === 'PRISM707'", content)
        self.assertIn("/converter?tab=participants", content)
        self.assertIn("Open Sociodemographics", content)

    def test_open_project_copy_describes_load_then_optional_validation(self):
        open_form_content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")
        projects_page_content = PROJECTS_PAGE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "Load first, then run Quick Validate only when you need it",
            open_form_content,
        )
        self.assertIn(
            "Loading sets the current project. Validation is optional and can be run afterwards.",
            open_form_content,
        )
        self.assertIn(
            "Load a project you already use in PRISM Studio and validate it only when needed.",
            projects_page_content,
        )
        self.assertIn("Load only", projects_page_content)

    def test_preserved_project_shows_open_section_without_validation(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("function ensureOpenSectionVisibleForLoadedProject() {", content)
        self.assertIn("if (!path || !shouldHideProjectTypeSelectionWhenLoaded()) {", content)
        self.assertIn("selectProjectType('open');", content)
        self.assertIn("ensureOpenSectionVisibleForLoadedProject();", content)

    def test_navbar_recent_project_redirect_preserves_current_project_only(self):
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
            "_withProjectPathQuery('/api/projects/metadata/status', requestProjectPath)",
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

    def test_metadata_orcid_lookup_uses_backend_search_and_multi_hit_selection(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn("/api/projects/orcid/search?", content)
        self.assertIn("Multiple ORCID matches found", content)
        self.assertIn("window.bootstrap.Modal", content)
        self.assertIn("Use selected ORCID", content)
        self.assertIn("candidate.affiliation", content)
        self.assertIn(">Affiliation</th>", content)
        self.assertIn(">Public data</th>", content)
        self.assertIn("candidate.public_data_status", content)
        self.assertIn("Current ORCID in field", content)
        self.assertIn("No public affiliation data", content)
        self.assertIn("params.set('limit', '10')", content)
        self.assertIn("params.set('current_orcid', currentOrcid)", content)
        self.assertIn("_lookupOrcidForAuthorRow", content)

    def test_metadata_sync_warning_exposes_repair_actions(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn("function requestMetadataRepairSave() {", content)
        self.assertIn("function _renderMetadataRepairHint() {", content)
        self.assertIn(
            "const preferredSubmitter = document.getElementById('createProjectSubmitBtn');",
            content,
        )
        self.assertIn('data-action="repair-metadata-sync"', content)
        self.assertIn('data-action="regenerate-citation-sync"', content)
        self.assertIn("requestMetadataRepairSave();", content)
        self.assertIn("regenerateCitationCff();", content)

    def test_project_box_save_buttons_set_distinct_submit_intents(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "function requestStudyMetadataSaveFromProjectBox(submitIntent = 'standard') {",
            content,
        )
        self.assertIn("studyMetadataForm.dataset.submitIntent = submitIntent;", content)
        self.assertIn(
            "button.id === 'projectBoxPreliminarySaveBtn' ? 'preliminary' : 'standard'",
            content,
        )
        self.assertIn(
            "const submitIntent = String(this.dataset.submitIntent || 'standard').trim().toLowerCase();",
            PROJECTS_METADATA_MODULE.read_text(encoding="utf-8"),
        )

    def test_preliminary_state_only_tracks_required_metadata_issues(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn("requiredInvalidFields", content)
        self.assertIn("optionalInvalidFields", content)
        self.assertIn(
            "Required fields are complete, but remaining validation errors must be fixed before saving changes.",
            content,
        )
        self.assertIn("Please fix metadata validation errors before saving.", content)

    def test_project_switch_actions_guard_busy_and_unsaved_metadata(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("hasUnsavedStudyMetadataChanges,", content)
        self.assertIn("isStudyMetadataBusy,", content)
        self.assertIn(
            "function confirmProjectContextChange(actionLabel = 'continue', targetPath = '') {",
            content,
        )
        self.assertIn("if (isStudyMetadataBusy()) {", content)
        self.assertIn(
            "if (normalizedCurrentPath && hasUnsavedStudyMetadataChanges()) {",
            content,
        )
        self.assertIn(
            "await loadProjectWithoutValidation(path, null, { skipContextGuard: true });",
            content,
        )
        self.assertIn(
            "if (!skipContextGuard && !confirmProjectContextChange('load another project', normalizedPath)) {",
            content,
        )
        self.assertIn(
            "if (!confirmProjectContextChange('initialise a PRISM project on another dataset', bidsPath)) {",
            content,
        )

    def test_loaded_project_save_actions_wait_for_metadata_readiness(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("let studyMetadataLoadInFlight = false;", content)
        self.assertIn("let studyMetadataReadyProjectPath = '';", content)
        self.assertIn(
            "const metadataReadyForCurrentProject = Boolean(currentProjectPath)",
            content,
        )
        self.assertIn(
            "if (!isCreateMode && currentProjectPath && !metadataReadyForCurrentProject) {",
            content,
        )
        self.assertIn(
            "setMetadataSaveStatus(loadingMessage, studyMetadataLoadInFlight ? 'muted' : 'warning');",
            content,
        )
        self.assertIn(
            "renderLoadedProjectState(loadedName, loadedPath, projectSummary);\n        bindProjectBoxActionButtons();\n        updateCreateProjectButton();",
            core_content,
        )

    def test_metadata_save_transaction_reuses_request_project_path(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "export async function saveDatasetDescription(projectPath = null) {",
            content,
        )
        self.assertIn(
            "const requestProjectPath = String(projectPath || _getCurrentProjectPath()).trim();",
            content,
        )
        self.assertIn("await saveDatasetDescription(requestProjectPath);", content)
        self.assertIn(
            "const readmeResult = await generateReadmeSilent(requestProjectPath);",
            content,
        )
        self.assertIn(
            "async function generateReadmeSilent(projectPath = null) {",
            content,
        )
        self.assertIn(
            "if (requestProjectPath === _getCurrentProjectPath()) {\n                await refreshMetadataSyncStatus();\n                _captureStudyMetadataBaseline();\n            }\n\n            saveSucceeded = true;",
            content,
        )

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
        self.assertIn("requestStudyMetadataSaveFromProjectBox(", content)
        self.assertIn(
            "button.id === 'projectBoxPreliminarySaveBtn' ? 'preliminary' : 'standard'",
            content,
        )

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

    def test_library_editor_uses_shared_header_and_help_macros(self):
        content = LIBRARY_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)
        self.assertIn('id="saveSurveyBtn"', content)


if __name__ == "__main__":
    unittest.main()
