import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_API_MODULE = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
SHARED_PATH_PICKER_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "shared" / "path-picker.js"
)
PROJECTS_CORE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "core.js"
)
PROJECTS_FILE_BROWSER_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "file-browser.js"
)
PROJECTS_PATH_PICKERS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "path-pickers.js"
)
PROJECTS_INIT_ON_BIDS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "init-on-bids.js"
)
PROJECTS_CREATE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "create-project.js"
)
PROJECTS_CREATE_PREFLIGHT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "create-preflight.js"
)
PROJECTS_CURRENT_STATE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "current-project-state.js"
)
PROJECTS_RECENT_PROJECTS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "recent-projects.js"
)
PROJECTS_SELECTION_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "project-selection.js"
)
PROJECTS_MAINTENANCE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "maintenance-actions.js"
)
PROJECTS_METADATA_SUBMIT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-submit.js"
)
PROJECTS_METADATA_STATUS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-status.js"
)
PROJECTS_METADATA_DESCRIPTION_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-description.js"
)
PROJECTS_METADATA_ORCID_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-orcid.js"
)
PROJECTS_METADATA_LOAD_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-load.js"
)
PROJECTS_METADATA_SAVE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-save.js"
)
PROJECTS_METADATA_METHODS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata-methods.js"
)
PROJECTS_BOOTSTRAP_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "page-bootstrap.js"
)
PROJECTS_HINTS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "project-hints.js"
)
PROJECTS_SETTINGS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "settings.js"
)
PROJECTS_OPEN_PROJECT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "open-project.js"
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
PROJECTS_INDEX_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "index.js"
)
MAIN_MODULE = REPO_ROOT / "app" / "static" / "js" / "main.js"
LEGACY_PROJECTS_CORE = REPO_ROOT / "app" / "static" / "js" / "projects-core.js"
LEGACY_PROJECTS_EXPORT = REPO_ROOT / "app" / "static" / "js" / "projects-export.js"
LEGACY_PROJECTS_HELPERS = REPO_ROOT / "app" / "static" / "js" / "projects-helpers.js"
LEGACY_PROJECTS_METADATA = REPO_ROOT / "app" / "static" / "js" / "projects-metadata.js"
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
LIBRARY_EDITOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "library_editor.js"


class TestProjectsWorkflowWiring(unittest.TestCase):
    def test_shared_api_exports_desktop_fallback_helper(self):
        content = SHARED_API_MODULE.read_text(encoding="utf-8")
        base_content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("export async function fetchWithApiFallback(", content)
        self.assertIn("url.startsWith('/api/')", content)
        self.assertIn("return 'http://127.0.0.1:5001';", content)
        self.assertIn("credentials: 'include'", content)
        self.assertIn("window.PRISM_API_ORIGIN = {{ prism_api_origin|tojson }};", base_content)

    def test_shared_path_picker_honors_server_preference_and_in_app_fallback(self):
        content = SHARED_PATH_PICKER_MODULE.read_text(encoding="utf-8")

        self.assertIn("export function prefersServerPicker()", content)
        self.assertIn("export async function browseFolderWithFallback(_fetchWithApiFallback, options = {})", content)
        self.assertIn("export async function browseFileWithFallback(_fetchWithApiFallback, options = {})", content)
        self.assertIn("window.PrismFileSystemMode.prefersServerPicker()", content)
        self.assertIn("return requirePathPicker('browseFolder').browseFolder(options);", content)
        self.assertIn("return requirePathPicker('browseFile').browseFile(options);", content)
        self.assertIn("throw new Error('Shared path picker is unavailable.');", content)

    def test_new_project_draft_clear_uses_api_fallback(self):
        content = PROJECTS_SELECTION_MODULE.read_text(encoding="utf-8")

        self.assertIn("fetchWithApiFallback('/api/projects/current', {", content)
        self.assertIn("body: JSON.stringify({ path: '' })", content)

    def test_recent_projects_controller_owns_storage_sync_and_rendering(self):
        content = PROJECTS_RECENT_PROJECTS_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("export function createRecentProjectsController({", content)
        self.assertIn("fetchWithApiFallback('/api/projects/recent', {", content)
        self.assertIn("fetchWithApiFallback('/api/projects/path-status', {", content)
        self.assertIn("function renderRecentProjects() {", content)
        self.assertIn("const recentProjectsController = createRecentProjectsController({", core_content)
        self.assertIn("export { getRecentProjects, saveRecentProjects, addRecentProject, renderRecentProjects };", core_content)

    def test_current_project_state_and_recent_projects_bootstrap_before_workflows(self):
        current_state_content = PROJECTS_CURRENT_STATE_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { createProjectsCurrentStateController } from './current-project-state.js';",
            core_content,
        )
        self.assertIn(
            "const currentProjectStateController = createProjectsCurrentStateController({",
            core_content,
        )
        self.assertIn("const projectsRoot = document.getElementById('projectsRoot');", current_state_content)
        self.assertIn("const globalProjectState = getProjectStateSnapshot();", current_state_content)
        self.assertIn("let currentProjectDatalad = null;", current_state_content)
        self.assertIn("window.updateNavbarProject(currentProjectName, currentProjectPath, currentProjectIcon, currentProjectDatalad);", current_state_content)
        self.assertIn("window.addEventListener('prism-project-changed', function(event) {", current_state_content)
        self.assertLess(
            core_content.index("const currentProjectStateController = createProjectsCurrentStateController({"),
            core_content.index("const recentProjectsController = createRecentProjectsController({"),
        )
        self.assertLess(
            core_content.index("const recentProjectsController = createRecentProjectsController({"),
            core_content.index("initProjectInitOnBidsController({"),
        )

    def test_open_project_loaded_state_owns_datalad_actions(self):
        content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")

        self.assertIn("function renderProjectBoxDataladState(", content)
        self.assertIn('id="projectBoxDataladStateBadge"', content)
        self.assertIn('id="projectBoxDataladEnableBtn"', content)
        self.assertIn('id="projectBoxDataladSaveBtn"', content)
        self.assertIn('id="projectBoxDataladProgressWrap"', content)
        self.assertIn('id="projectBoxDataladProgressBar"', content)
        self.assertIn('id="projectBoxDataladProgressLabel"', content)
        self.assertIn("Repair DataLad Structure", content)
        self.assertIn("DataLad Structure Complete", content)
        self.assertIn("fetchWithApiFallback('/api/projects/datalad/enable'", content)
        self.assertIn("fetchWithApiFallback('/api/projects/datalad/save'", content)
        self.assertIn("confirmed: true", content)
        self.assertIn("backfill one missing nested dataset per click", content)
        self.assertIn("DataLad structure is complete for this project.", content)
        self.assertIn("backfilling one missing nested dataset for this click", content)
        self.assertIn("Watch the backend terminal for progress.", content)
        self.assertIn("subdatasetsProgressPercent", content)
        self.assertIn("nextMissingSubdataset", content)
        self.assertIn("window.prompt('Commit message for this checkpoint'", content)
        self.assertIn("window.setNavbarDataladFeedback?.(", content)
        self.assertIn("const DATALAD_PREFERENCES_NAMESPACE = 'datalad';", content)
        self.assertIn("/api/projects/preferences/${DATALAD_PREFERENCES_NAMESPACE}", content)
        self.assertIn("window.prismDataladOperationState", content)
        self.assertIn("maybePromptDataladOptIn", content)

    def test_settings_and_fix_actions_use_api_fallback(self):
        settings_content = PROJECTS_SETTINGS_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        maintenance_content = PROJECTS_MAINTENANCE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "const response = await fetchWithApiFallback('/api/settings/global-library');",
            settings_content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/library-path');",
            settings_content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/fix', {",
            maintenance_content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/projects/current', {",
            maintenance_content,
        )
        self.assertIn("import {", core_content)
        self.assertIn("} from './settings.js';", core_content)
        self.assertIn(
            "import { createProjectMaintenanceActions } from './maintenance-actions.js';",
            core_content,
        )
        self.assertIn("const projectMaintenanceActions = createProjectMaintenanceActions({", core_content)
        self.assertIn("initProjectSettingsForm();", core_content)

    def test_projects_page_uses_single_bootstrap_entrypoint(self):
        index_content = PROJECTS_INDEX_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        bootstrap_content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")
        export_content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")
        main_content = MAIN_MODULE.read_text(encoding="utf-8")
        template_content = PROJECTS_PAGE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("export function initializeProjectsPage() {", index_content)
        self.assertIn("initProjectsPage();", index_content)
        self.assertIn("initProjectValidation();", index_content)
        self.assertIn("initializeProjectsExport();", index_content)
        self.assertIn("let projectsPageInitialized = false;", core_content)
        self.assertIn("export function initProjectsPage() {", core_content)
        self.assertIn("import { initProjectsPageBootstrap } from './page-bootstrap.js';", core_content)
        self.assertIn("initProjectsPageBootstrap({", core_content)
        self.assertIn("export function initProjectsPageBootstrap({", bootstrap_content)
        self.assertNotIn("document.addEventListener('DOMContentLoaded', initProjectsPage);", core_content)
        self.assertIn("let exportModuleInitialized = false;", export_content)
        self.assertIn("export function initializeProjectsExport() {", export_content)
        self.assertNotIn("document.addEventListener('DOMContentLoaded', function() {", export_content)
        self.assertIn("ProjectsModule.initializeProjectsPage()", main_content)
        self.assertIn("<script type=\"module\" src=\"{{ url_for('static', filename='js/main.js', v=prism_static_asset_token) }}\"></script>", template_content)
        self.assertFalse(LEGACY_PROJECTS_CORE.exists())
        self.assertFalse(LEGACY_PROJECTS_EXPORT.exists())
        self.assertFalse(LEGACY_PROJECTS_HELPERS.exists())
        self.assertFalse(LEGACY_PROJECTS_METADATA.exists())

    def test_backend_monitoring_verbose_toggle_is_wired(self):
        settings_content = PROJECTS_SETTINGS_MODULE.read_text(encoding="utf-8")
        settings_template = (
            REPO_ROOT
            / "app"
            / "templates"
            / "includes"
            / "projects"
            / "settings_section.html"
        ).read_text(encoding="utf-8")

        self.assertIn("backendMonitoringVerboseToggle", settings_template)
        self.assertIn("exportDefacingConfirmationMode", settings_template)
        self.assertIn(
            "function normalizeExportDefacingConfirmationMode(value) {",
            settings_content,
        )
        self.assertIn(
            "const exportDefacingConfirmationModeSelect = document.getElementById('exportDefacingConfirmationMode');",
            settings_content,
        )
        self.assertIn(
            "export_defacing_confirmation_mode: exportDefacingConfirmationMode,",
            settings_content,
        )
        self.assertIn(
            "const verboseToggle = document.getElementById('backendMonitoringVerboseToggle');",
            settings_content,
        )
        self.assertIn("backend_monitoring_verbose", settings_content)

    def test_open_project_flow_reuses_metadata_button_binder(self):
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        metadata_content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        metadata_submit_content = PROJECTS_METADATA_SUBMIT_MODULE.read_text(encoding="utf-8")
        open_project_content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")

        self.assertIn("bindProjectBoxActionButtons,", core_content)
        self.assertIn(
            "import { createStudyMetadataSubmitController } from './metadata-submit.js';",
            metadata_content,
        )
        self.assertIn(
            "const studyMetadataSubmitController = createStudyMetadataSubmitController({",
            metadata_content,
        )
        self.assertIn(
            "export function createStudyMetadataSubmitController({",
            metadata_submit_content,
        )
        self.assertIn("function bindProjectBoxActionButtons() {", metadata_submit_content)
        self.assertIn("initPrimaryStudyMetadataSubmitButton()", metadata_submit_content)
        self.assertIn("bindProjectBoxActionButtons();", open_project_content)

    def test_unsaved_new_project_detector_ignores_default_form_values(self):
        content = PROJECTS_SELECTION_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "if (options.some((option) => option.selected !== option.defaultSelected)) {",
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
        content = PROJECTS_FILE_BROWSER_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("import { browseFileWithFallback } from '../../shared/path-picker.js';", content)
        self.assertIn("const res = await fetchWithApiFallback(url);", content)
        self.assertIn("const pickedPath = await browseFileWithFallback(fetchWithApiFallback, {", content)
        self.assertIn("await openProjectBrowserModal(startPath || null);", content)
        self.assertIn(
            'class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-project-json text-start"',
            content,
        )
        self.assertIn(
            'class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-dir text-start bg-white"',
            content,
        )
        self.assertIn(
            'aria-label="Select project.json at ${escHtml(data.project_json_path)}"',
            content,
        )
        self.assertIn("export function initProjectFileBrowser(", content)
        self.assertIn("initProjectFileBrowser({ fetchWithApiFallback });", core_content)

    def test_projects_core_uses_shared_path_picker(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        picker_content = PROJECTS_PATH_PICKERS_MODULE.read_text(encoding="utf-8")

        self.assertIn("import { initProjectPathPickers } from './path-pickers.js';", content)
        self.assertIn("initProjectPathPickers({", content)
        self.assertNotIn("await browseFolderWithFallback(fetchWithApiFallback, {", content)
        self.assertIn("import { browseFolderWithFallback } from '../../shared/path-picker.js';", picker_content)
        self.assertIn("export function initProjectPathPickers({ fetchWithApiFallback, validateProjectField, clearCreateResult })", picker_content)
        self.assertIn("buttonId: 'browseProjectPath'", picker_content)
        self.assertIn("buttonId: 'browseInitBidsPath'", picker_content)
        self.assertIn("buttonId: 'browseGlobalLibrary'", picker_content)
        self.assertIn("buttonId: 'browseGlobalRecipes'", picker_content)

    def test_projects_init_on_bids_flow_is_extracted(self):
        content = PROJECTS_INIT_ON_BIDS_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("export function initProjectInitOnBidsController({", content)
        self.assertIn("const response = await fetchWithApiFallback('/api/projects/init-on-bids', {", content)
        self.assertIn("PRISM Initialised Successfully!", content)
        self.assertIn("bidsPath.split(/[\\\\/]/).pop()", content)
        self.assertIn("import { initProjectInitOnBidsController } from './init-on-bids.js';", core_content)
        self.assertIn("initProjectInitOnBidsController({", core_content)

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
        self.assertIn("const inheritedPreferences = data.inherited_preferences || {};", content)
        self.assertIn("loadExportPreferences();", content)
        self.assertIn(
            "exclude_sessions: _getUncheckedValues('export-session-filter')", content
        )
        self.assertIn(
            "exclude_modalities: _getUncheckedValues('export-modality-filter')", content
        )
        self.assertIn("exclude_acq: _getUncheckedAcqByModality(),", content)
        self.assertIn("exclude_tasks: _getUncheckedTaskByModality(),", content)
        self.assertIn("applyModalitySubfilterState(target);", content)
        self.assertIn("syncModalitySubfilterState(modality);", content)
        self.assertIn("validation_mode: 'both',", content)
        self.assertIn("repository_mode: 'datalad_free',", content)
        self.assertIn("defacing_confirmation_mode: 'risk',", content)
        self.assertIn("function getSelectedExportRepositoryMode() {", content)
        self.assertIn(
            "saveExportPreferencesPatch({ repository_mode: getSelectedExportRepositoryMode() });",
            content,
        )
        self.assertIn("function getSelectedDefacingConfirmationMode() {", content)
        self.assertIn(
            "saveExportPreferencesPatch({ validation_mode: getSelectedExportValidationMode() });",
            content,
        )
        self.assertIn(
            "saveExportPreferencesPatch({ defacing_confirmation_mode: getSelectedDefacingConfirmationMode() });",
            content,
        )
        self.assertIn(
            "await saveExportPreferencesPatch({ defacing_confirmation_mode: null });",
            content,
        )
        self.assertIn("const resetDefacingModeBtn = getById('exportDefacingUseGlobalDefault');", content)
        self.assertIn("updateExportSnapshotUi();", content)

    def test_export_summary_ui_wiring_present(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("function updateExportSnapshotUi() {", content)
        self.assertIn(
            "function setExportChipState(chipId, text, tone = 'neutral') {", content
        )
        self.assertIn("function countExcludedSubfilterLabels(excludedAcq, excludedTasks) {", content)
        self.assertIn("function applyModalitySubfilterState(modalityCheckbox) {", content)
        self.assertIn("function syncModalitySubfilterState(modality) {", content)
        self.assertIn("function syncAllModalitySubfilterStates() {", content)
        self.assertIn("exportScopeSummary", content)
        self.assertIn("exportDestinationSummary", content)
        self.assertIn("exportPreferenceSummary", content)
        self.assertIn("ZIP repository mode:", content)
        self.assertIn("Defacing confirmation:", content)
        self.assertIn("Project + global defaults", content)
        self.assertIn("saved in project export preferences", content)
        self.assertIn("inherited from Global Settings", content)
        self.assertIn(
            "resetDefacingModeBtn.disabled = !currentProjectPath || lastExportPreferenceInheritance.defacing_confirmation_mode;",
            content,
        )
        self.assertIn("exportSessionsChip", content)
        self.assertIn("exportModalitiesChip", content)
        self.assertIn("exportAcqChip", content)
        self.assertIn("Task/acquisition labels", content)

    def test_export_actions_use_desktop_api_fallback(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("function buildExportRequestData(currentProjectPath, overrides = {}) {", content)
        self.assertIn("function buildFolderExportRequestData(currentProjectPath) {", content)
        self.assertIn(
            "exclude_version_control_metadata: getSelectedExportRepositoryMode() === 'datalad_free',",
            content,
        )
        self.assertIn("function getExportRepositoryModeStatusSuffix(repositoryMode) {", content)
        self.assertIn("function getExportRepositoryModeSuccessNote(repositoryMode) {", content)
        self.assertIn("async function fetchDefacingSummary(projectPath) {", content)
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
        self.assertIn("export_preset: 'upload_ready',", content)
        self.assertIn("repository_mode: 'datalad_free',", content)
        self.assertIn("Upload-Ready Export Successful!", content)
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/template-export', {",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/export/folder', {",
            content,
        )
        self.assertIn("const data = buildFolderExportRequestData(currentProjectPath);", content)
        self.assertIn("const warningText = typeof result.warning === 'string'", content)
        self.assertIn("const missingFilesCount = Number(result.missing_files_count || 0);", content)
        self.assertIn("const missingFilePreview = Array.isArray(result.missing_files_preview)", content)
        self.assertIn("const excludedMetadata = Array.isArray(result.excluded_repository_metadata)", content)
        self.assertIn("Stripped repository metadata:", content)
        self.assertIn("const templateExportButton = getById('templateExportButton');", content)
        self.assertIn("const plainFolderExportButton = getById('plainFolderExportButton');", content)
        self.assertIn("const uploadReadyExportButton = getById('uploadReadyExportButton');", content)
        self.assertIn("validation_mode: getSelectedExportValidationMode(),", content)
        self.assertIn("repository_mode: getSelectedExportRepositoryMode(),", content)
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

        self.assertIn('id="plainFolderExportButton"', content)
        self.assertIn('id="uploadReadyExportButton"', content)
        self.assertIn('id="templateExportButton"', content)
        self.assertIn('id="exportRepositoryMode"', content)
        self.assertIn('id="exportDefacingConfirmAlways"', content)
        self.assertIn('id="exportDefacingUseGlobalDefault"', content)
        self.assertIn("Folder Export", content)
        self.assertIn("Upload-Ready ZIP", content)
        self.assertIn("Template Export", content)

    def test_export_async_completion_renders_saved_zip_path_from_status(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("const MAX_POLLS = 2250;", content)
        self.assertIn(
            "`/api/projects/export/${encodeURIComponent(jobId)}/status`",
            content,
        )
        self.assertIn("const savedPath = status.zip_path || 'unknown location';", content)
        self.assertIn("const defacingWarning = status.defacing_warning || null;", content)
        self.assertIn("defacingWarning && defacingWarning.message", content)
        self.assertIn("ZIP saved to:", content)
        self.assertIn("escapeHtml(savedPath)", content)

    def test_export_submit_prompts_for_defacing_risk_when_scrub_enabled(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("if (data.scrub_mri_json) {", content)
        self.assertIn("const defacingConfirmationMode = getSelectedDefacingConfirmationMode();", content)
        self.assertIn("const defacingSummary = await fetchDefacingSummary(currentProjectPath);", content)
        self.assertIn("if (defacingConfirmationMode === 'always' || defacingSummary.riskCount > 0) {", content)
        self.assertIn("const continueExport = window.confirm(", content)
        self.assertIn("Defacing check did not detect unresolved risk in anatomical scans. Continue export anyway?", content)
        self.assertIn("Could not retrieve defacing status before export. Continue export anyway?", content)
        self.assertIn("Continue export anyway?", content)

    def test_create_and_init_flows_use_fallback_and_refresh_project_sections(self):
        init_content = PROJECTS_INIT_ON_BIDS_MODULE.read_text(encoding="utf-8")
        create_content = PROJECTS_CREATE_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/init-on-bids', {",
            init_content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/create', {",
            create_content,
        )
        self.assertIn("showStudyMetadataCard();", create_content)
        self.assertIn("showExportCard();", create_content)
        self.assertIn("showMethodsCard();", create_content)
        self.assertIn("import { initCreateProjectController } from './create-project.js';", core_content)
        self.assertIn("initCreateProjectController({", core_content)

    def test_create_flow_checks_target_path_before_submitting(self):
        content = PROJECTS_CREATE_PREFLIGHT_MODULE.read_text(encoding="utf-8")
        create_content = PROJECTS_CREATE_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("async function checkCreateTargetStatus() {", content)
        self.assertIn("function buildDataladPreflightHtml(status, targetPath) {", content)
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/projects/path-status', {",
            content,
        )
        self.assertIn("status?.datalad_preflight", content)
        self.assertIn("document.getElementById('projectUseDatalad')?.checked !== false", content)
        self.assertIn("projectUseDataladInput.addEventListener('change', function() {", content)
        self.assertIn("const targetStatus = await checkCreateTargetStatus();", create_content)
        self.assertIn("if (targetStatus.conflict) {", create_content)
        self.assertIn("const fullPath = joinProjectTargetPath(projectPath, projectName);", create_content)
        self.assertIn("import { initCreatePreflightController } from './create-preflight.js';", core_content)
        self.assertIn("const createPreflightController = initCreatePreflightController({", core_content)

    def test_create_conflict_warning_can_open_existing_project(self):
        content = PROJECTS_CREATE_PREFLIGHT_MODULE.read_text(encoding="utf-8")

        self.assertIn("function submitOpenProjectPath(path) {", content)
        self.assertIn('data-action="open-existing-project"', content)
        self.assertIn(
            "const openExistingBtn = event.target.closest('[data-action=\"open-existing-project\"]');",
            content,
        )
        self.assertIn("submitOpenProjectPath(path);", content)

    def test_open_project_flow_separates_load_and_validation(self):
        content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        bootstrap_content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")

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
        self.assertIn("function renderProjectQuickSummary(summary) {", content)
        self.assertIn("const projectSummary = result.project_summary", content)
        self.assertIn("renderLoadedProjectState(loadedName, loadedPath, projectSummary);", content)
        self.assertIn("import { initOpenProjectController } from './open-project.js';", core_content)
        self.assertIn("const openProjectController = initOpenProjectController({", core_content)
        self.assertNotIn("runProjectValidation(", bootstrap_content)

    def test_loaded_project_state_links_to_full_validator(self):
        content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")

        self.assertIn("Need a full dataset check?", content)
        self.assertIn('class="validation-result pending', content)
        self.assertIn('href="/validate"', content)
        self.assertIn("Snapshot from folders currently found on disk.", content)
        self.assertIn("Open Validator", content)
        self.assertIn("id=\"projectBoxSaveBtn\"", content)
        self.assertIn("Save Changes to Project", content)

    def test_projects_page_no_longer_owns_inline_validation_actions(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        bootstrap_content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")

        self.assertNotIn("function getProjectValidationAction(code) {", content)
        self.assertNotIn("runProjectValidation(", bootstrap_content)
        self.assertIn('href="/validate"', PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8"))

    def test_open_project_copy_describes_load_then_optional_validation(self):
        open_form_content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")
        projects_page_content = PROJECTS_PAGE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "Load here, then open the full Validator when you need a real dataset check",
            open_form_content,
        )
        self.assertIn(
            "Loading sets the current project. Full dataset validation runs from the Validator page.",
            open_form_content,
        )
        self.assertIn(
            "Load a project you already use in PRISM Studio here, then run full checks in the Validator.",
            projects_page_content,
        )
        self.assertIn("Load only", projects_page_content)

    def test_preserved_project_shows_open_section_without_validation(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        bootstrap_content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")

        self.assertIn("function ensureOpenSectionVisibleForLoadedProject() {", content)
        self.assertIn("if (!path || !shouldHideProjectTypeSelectionWhenLoaded()) {", content)
        self.assertIn("selectProjectType('open');", content)
        self.assertIn("ensureOpenSectionVisibleForLoadedProject,", content)
        self.assertIn("ensureOpenSectionVisibleForLoadedProject();", bootstrap_content)

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
        methods_content = PROJECTS_METADATA_METHODS_MODULE.read_text(encoding="utf-8")
        metadata_status_content = PROJECTS_METADATA_STATUS_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { fetchWithApiFallback } from '../../shared/api.js';", content
        )
        self.assertIn("const r = await fetchWithApiFallback('/api/config');", content)
        self.assertIn("let metadataLoadToken = 0;", content)
        self.assertIn(
            "import { createMetadataMethodsController } from './metadata-methods.js';",
            content,
        )
        self.assertIn(
            "const metadataMethodsController = createMetadataMethodsController({",
            content,
        )
        self.assertIn("let methodsRequestToken = 0;", methods_content)
        self.assertIn(
            "withProjectPathQuery('/api/projects/citation/status', requestProjectPath)",
            metadata_status_content,
        )
        self.assertIn(
            "withProjectPathQuery('/api/projects/metadata/status', requestProjectPath)",
            metadata_status_content,
        )
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath })", content
        )
        self.assertIn(
            "if (requestToken !== methodsRequestToken || requestProjectPath !== getCurrentProjectPath()) {",
            methods_content,
        )
        self.assertIn("metadataMethodsController.handleProjectChanged();", content)
        self.assertIn("metadataMethodsController.initMethodsControls();", content)

    def test_metadata_description_controller_owns_schema_and_live_validation(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        description_content = PROJECTS_METADATA_DESCRIPTION_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { createMetadataDescriptionController } from './metadata-description.js';",
            content,
        )
        self.assertIn(
            "const metadataDescriptionController = createMetadataDescriptionController({",
            content,
        )
        self.assertIn(
            "return metadataDescriptionController.validateDatasetDescriptionDraftLive();",
            content,
        )
        self.assertIn(
            "metadataDescriptionController.scheduleLiveDescriptionValidation();",
            content,
        )
        self.assertIn(
            "return metadataDescriptionController.saveProjectSchemaConfig();",
            content,
        )
        self.assertIn(
            "return metadataDescriptionController.loadDatasetDescriptionFields();",
            content,
        )
        self.assertIn(
            "return metadataDescriptionController.saveDatasetDescription(requestProjectPath);",
            content,
        )
        self.assertIn("let descriptionValidationTimer = null;", description_content)
        self.assertIn("async function saveDatasetDescription(projectPath = null) {", description_content)
        self.assertIn("withProjectPathQuery('/api/projects/schema-config', requestProjectPath)", description_content)
        self.assertIn("withProjectPathQuery('/api/projects/description', requestProjectPath)", description_content)
        self.assertIn("fetchWithApiFallback('/api/projects/description/validate'", description_content)
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath, description, citation_fields: citationFields })",
            description_content,
        )
        self.assertIn("await saveProjectSchemaConfig();", description_content)
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath, schema_version: schemaVersion })",
            description_content,
        )
        self.assertIn(
            "withProjectPathQuery('/api/projects/description', requestProjectPath)",
            description_content,
        )

    def test_metadata_orcid_lookup_uses_backend_search_and_multi_hit_selection(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        orcid_content = PROJECTS_METADATA_ORCID_MODULE.read_text(encoding="utf-8")

        self.assertIn("import { createMetadataOrcidController } from './metadata-orcid.js';", content)
        self.assertIn("const metadataOrcidController = createMetadataOrcidController({", content)
        self.assertIn("metadataOrcidController.lookupOrcidForAuthorRow(row)", content)
        self.assertIn("/api/projects/orcid/search?", orcid_content)
        self.assertIn("Multiple ORCID matches found", orcid_content)
        self.assertIn("window.bootstrap.Modal", orcid_content)
        self.assertIn("Use selected ORCID", orcid_content)
        self.assertIn("candidate.affiliation", orcid_content)
        self.assertIn(">Affiliation</th>", orcid_content)
        self.assertIn(">Public data</th>", orcid_content)
        self.assertIn("candidate.public_data_status", orcid_content)
        self.assertIn("Current ORCID in field", orcid_content)
        self.assertIn("No public affiliation data", orcid_content)
        self.assertIn("params.set('limit', '10')", orcid_content)
        self.assertIn("params.set('current_orcid', currentOrcid)", orcid_content)
        self.assertIn("lookupOrcidForAuthorRow", orcid_content)

    def test_metadata_sync_warning_exposes_repair_actions(self):
        metadata_content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        metadata_status_content = PROJECTS_METADATA_STATUS_MODULE.read_text(encoding="utf-8")
        metadata_submit_content = PROJECTS_METADATA_SUBMIT_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { createMetadataStatusController } from './metadata-status.js';",
            metadata_content,
        )
        self.assertIn(
            "const metadataStatusController = createMetadataStatusController({",
            metadata_content,
        )
        self.assertIn(
            "export function createMetadataStatusController({",
            metadata_status_content,
        )
        self.assertIn("function renderMetadataRepairHint() {", metadata_status_content)
        self.assertIn(
            "const studyMetadataSubmitController = createStudyMetadataSubmitController({",
            metadata_content,
        )
        self.assertIn('data-action="repair-metadata-sync"', metadata_status_content)
        self.assertIn('data-action="regenerate-citation-sync"', metadata_status_content)
        self.assertIn("requestMetadataRepairSave();", metadata_content)
        self.assertIn("regenerateCitationCff();", metadata_content)
        self.assertIn("function requestMetadataRepairSave() {", metadata_submit_content)

    def test_project_box_save_buttons_set_distinct_submit_intents(self):
        content = PROJECTS_METADATA_SUBMIT_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "function requestStudyMetadataSubmit(submitIntent = 'standard') {",
            content,
        )
        self.assertIn("function bindProjectBoxSubmitBridge(button, submitIntent) {", content)
        self.assertIn("button.addEventListener('pointerdown', (event) => {", content)
        self.assertIn("form.dataset.submitIntent = submitIntent;", content)
        self.assertIn(
            "bindProjectBoxSubmitBridge(projectBoxPreliminarySaveBtn, 'preliminary');",
            content,
        )
        self.assertIn(
            "bindProjectBoxSubmitBridge(projectBoxSaveBtn, 'standard');",
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
        content = PROJECTS_SELECTION_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        open_content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")
        init_content = PROJECTS_INIT_ON_BIDS_MODULE.read_text(encoding="utf-8")

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
        self.assertIn("import { initProjectSelectionController } from './project-selection.js';", core_content)
        self.assertIn("const projectSelectionController = initProjectSelectionController({", core_content)
        self.assertIn(
            "await loadProjectWithoutValidation(path, null, { skipContextGuard: true });",
            core_content,
        )
        self.assertIn(
            "if (!skipContextGuard && !confirmProjectContextChange('load another project', normalizedPath)) {",
            open_content,
        )
        self.assertIn(
            "if (!confirmProjectContextChange('initialise a PRISM project on another dataset', bidsPath)) {",
            init_content,
        )

    def test_project_selection_controller_owns_card_switching(self):
        content = PROJECTS_SELECTION_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        bootstrap_content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")

        self.assertIn("function selectProjectType(type) {", content)
        self.assertIn("bindProjectTypeCard('card-create', 'create');", content)
        self.assertIn("bindProjectTypeCard('card-open', 'open');", content)
        self.assertIn("bindProjectTypeCard('card-init-bids', 'init-bids');", content)
        self.assertIn("initProjectSelectionUi();", bootstrap_content)
        self.assertIn("initProjectSelectionUi: () => projectSelectionController.initProjectSelectionUi(),", core_content)

    def test_project_switch_and_clear_paths_surface_non_blocking_autosave_feedback(self):
        open_content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")
        selection_content = PROJECTS_SELECTION_MODULE.read_text(encoding="utf-8")
        maintenance_content = PROJECTS_MAINTENANCE_MODULE.read_text(encoding="utf-8")

        self.assertIn("showAutosaveFailureFeedback(result.autosave_previous);", open_content)
        self.assertIn("const autosave = data.autosave_previous;", selection_content)
        self.assertIn("window.setNavbarDataladFeedback?.(detail, 'danger', 'Auto-save failed');", selection_content)
        self.assertIn("const autosave = data.autosave_previous;", maintenance_content)
        self.assertIn("window.setNavbarDataladFeedback?.(detail, 'danger', 'Auto-save failed');", maintenance_content)

    def test_projects_bootstrap_controller_owns_page_init_wiring(self):
        content = PROJECTS_BOOTSTRAP_MODULE.read_text(encoding="utf-8")

        self.assertIn("existingPathInput.placeholder = 'C:\\\\Users\\\\YourName\\\\MyProject\\\\project.json';", content)
        self.assertIn("projectPathInput.placeholder = 'C:\\\\Users\\\\YourName\\\\Documents';", content)
        self.assertIn("el.addEventListener('shown.bs.collapse'", content)
        self.assertIn("const validationResultDiv = document.getElementById('validationResult');", content)
        self.assertIn("const recentList = document.getElementById('recentProjectsList');", content)
        self.assertIn("const clearCurrentProjectBtn = document.getElementById('clearCurrentProjectBtn');", content)

    def test_project_hints_controller_is_split_from_core(self):
        content = PROJECTS_HINTS_MODULE.read_text(encoding="utf-8")
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")
        open_content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")

        self.assertIn("export function getBeginnerHelpModeEnabled() {", content)
        self.assertIn("export function initBeginnerHelpMode() {", content)
        self.assertIn("export function initProjectFieldHints() {", content)
        self.assertIn("} from './project-hints.js';", core_content)
        self.assertIn("getBeginnerHelpModeEnabled,", open_content)

    def test_init_on_bids_controller_is_wired_after_selection_guard_exists(self):
        core_content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertLess(
            core_content.index("const confirmProjectContextChange = projectSelectionController.confirmProjectContextChange;"),
            core_content.index("initProjectInitOnBidsController({"),
        )

    def test_loaded_project_save_actions_wait_for_metadata_readiness(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        load_content = PROJECTS_METADATA_LOAD_MODULE.read_text(encoding="utf-8")
        open_project_content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { createStudyMetadataLoadController } from './metadata-load.js';",
            content,
        )
        self.assertIn(
            "const studyMetadataLoadController = createStudyMetadataLoadController({",
            content,
        )
        self.assertIn("let studyMetadataLoadInFlight = false;", load_content)
        self.assertIn("let studyMetadataReadyProjectPath = '';", load_content)
        self.assertIn(
            "const metadataReadyForCurrentProject = Boolean(currentProjectPath)",
            content,
        )
        self.assertIn(
            "if (!isCreateMode && currentProjectPath && !metadataReadyForCurrentProject) {",
            content,
        )
        self.assertIn(
            "setMetadataSaveStatus(loadingMessage, 'muted');",
            content,
        )
        self.assertIn(
            "setMetadataSaveStatus(loadingMessage, 'warning');",
            content,
        )
        self.assertIn("async function loadStudyMetadata() {", load_content)
        self.assertIn("studyMetadataReadyProjectPath = requestProjectPath;", load_content)
        self.assertIn(
            "renderLoadedProjectState(loadedName, loadedPath, projectSummary);",
            open_project_content,
        )
        self.assertIn("bindProjectBoxActionButtons();", open_project_content)
        self.assertIn("updateCreateProjectButton();", open_project_content)

    def test_metadata_save_transaction_reuses_request_project_path(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")
        save_content = PROJECTS_METADATA_SAVE_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { createStudyMetadataSaveController } from './metadata-save.js';",
            content,
        )
        self.assertIn(
            "const studyMetadataSaveController = createStudyMetadataSaveController({",
            content,
        )

        self.assertIn(
            "export async function saveDatasetDescription(projectPath = null) {",
            content,
        )
        self.assertIn(
            "const requestProjectPath = String(projectPath || _getCurrentProjectPath()).trim();",
            content,
        )
        self.assertIn("await saveDatasetDescription(requestProjectPath);", save_content)
        self.assertIn(
            "const readmeResult = await generateReadmeSilent(requestProjectPath);",
            save_content,
        )
        self.assertIn(
            "async function generateReadmeSilent(projectPath = null) {",
            content,
        )
        self.assertIn(
            "if (requestProjectPath === getCurrentProjectPath()) {\n                    await refreshMetadataSyncStatus();\n                    captureBaseline();\n                }\n\n                saveSucceeded = true;",
            save_content,
        )

    def test_file_browser_template_announces_dynamic_updates(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="fsBrowserList" aria-live="polite"', content)
        self.assertIn(
            'id="fsBrowserSelectedHint" style="display:none;" role="status" aria-live="polite"',
            content,
        )

    def test_open_form_drops_quick_validate_control(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn('id="quickValidateProjectBtn"', content)
        self.assertNotIn('Quick Validate', content)

    def test_project_box_exposes_preliminary_save_button_with_shared_submit_path(self):
        open_project_content = PROJECTS_OPEN_PROJECT_MODULE.read_text(encoding="utf-8")
        submit_content = PROJECTS_METADATA_SUBMIT_MODULE.read_text(encoding="utf-8")

        self.assertIn('id="projectBoxPreliminarySaveBtn"', open_project_content)
        self.assertIn("document.getElementById('projectBoxPreliminarySaveBtn')", submit_content)
        self.assertIn("bindProjectBoxSubmitBridge(projectBoxPreliminarySaveBtn, 'preliminary');", submit_content)
        self.assertIn(
            "bindProjectBoxSubmitBridge(projectBoxSaveBtn, 'standard');",
            submit_content,
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
        self.assertIn('id="exportRepositoryMode"', content)
        self.assertIn('value="datalad_free"', content)
        self.assertIn('value="datalad_preserving"', content)

    def test_library_editor_uses_shared_header_and_help_macros(self):
        content = LIBRARY_EDITOR_TEMPLATE.read_text(encoding="utf-8")
        script_content = LIBRARY_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)
        self.assertIn('id="saveSurveyBtn"', content)
        self.assertIn('id="libraryAdvancedUnavailableNotice"', content)
        self.assertIn(
            '<script type="module" src="{{ url_for(\'static\', filename=\'js/library_editor.js\', v=prism_static_asset_token) }}"></script>',
            content,
        )
        self.assertIn(
            "import { fetchWithRelativePathFallback } from './shared/api.js';",
            script_content,
        )
        self.assertIn(
            "const advancedUnavailableNotice = document.getElementById('libraryAdvancedUnavailableNotice');",
            script_content,
        )
        self.assertIn("jsonTab.disabled = true;", script_content)
        self.assertIn(
            "advancedUnavailableNotice.classList.remove('d-none');",
            script_content,
        )
        self.assertIn(
            "await fetchWithRelativePathFallback(`/library/api/save/${encodeURIComponent(filename)}`, {",
            script_content,
        )


if __name__ == "__main__":
    unittest.main()
