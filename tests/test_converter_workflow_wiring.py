import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERTER_BOOTSTRAP = REPO_ROOT / "app" / "static" / "js" / "converter-bootstrap.js"
CONVERTER_INDEX = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "index.js"
)
SHARED_API = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
SESSION_REGISTER = (
    REPO_ROOT / "app" / "static" / "js" / "shared" / "session-register.js"
)
EYETRACKING_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_eyetracking.html"
BIOMETRICS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "biometrics.js"
)
SURVEY_CONVERT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-convert.js"
)
SURVEY_PARTICIPANTS_METADATA_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-participants-metadata.js"
)
SURVEY_WORKFLOW_PREPARE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-workflow-prepare.js"
)
SURVEY_WORKFLOW_PREVIEW_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-workflow-preview.js"
)
SURVEY_WORKFLOW_CONVERT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-workflow-convert.js"
)
SURVEY_WORKFLOW_CONVERT_RESULTS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-workflow-convert-results.js"
)
SURVEY_WORKFLOW_PROGRESS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-workflow-progress.js"
)
SURVEY_SOURCEDATA_QUICK_SELECT_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-sourcedata-quick-select.js"
)
SURVEY_WORKFLOW_TEMPLATE_CHECK_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-workflow-template-check.js"
)
SURVEY_TEMPLATE_RESULTS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-template-results.js"
)
SURVEY_CONVERSION_SUMMARY_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-conversion-summary.js"
)
SURVEY_CONVERSION_LOG_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-conversion-log.js"
)
SURVEY_CONVERT_FEEDBACK_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-convert-feedback.js"
)
SURVEY_FILE_SEPARATOR_UTILS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-file-separator-utils.js"
)
SURVEY_UNMATCHED_TEMPLATES_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-unmatched-templates.js"
)
SURVEY_IMPORT_FORM_STATE_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-import-form-state.js"
)
SURVEY_NEAR_ITEM_MATCH_REVIEW_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-near-item-match-review.js"
)
SURVEY_WORKFLOW_RESPONSE_UTILS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-workflow-response-utils.js"
)
SURVEY_VERSION_CONTEXT_UTILS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-version-context-utils.js"
)
SURVEY_VALIDATION_RESULTS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-validation-results.js"
)
SURVEY_VALUE_OFFSET_UTILS_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-value-offset-utils.js"
)
SURVEY_VALUE_OFFSET_EDITOR_MODULE = (
    REPO_ROOT
    / "app"
    / "static"
    / "js"
    / "modules"
    / "converter"
    / "survey-value-offset-editor.js"
)
PHYSIO_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "physio.js"
)
EYETRACKING_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "eyetracking.js"
)
ENVIRONMENT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "environment.js"
)
PARTICIPANTS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "participants.js"
)
SURVEY_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_survey.html"


class TestConverterWorkflowWiring(unittest.TestCase):
    def test_converter_module_aggregator_uses_single_bootstrap_entrypoint(self):
        content = CONVERTER_INDEX.read_text(encoding="utf-8")

        self.assertIn("window.__prismConverterBootstrapLoadedViaAggregator", content)
        self.assertIn("import('../../converter-bootstrap.js');", content)
        self.assertNotIn("initLimeSurveyQuickImport", content)
        self.assertNotIn("from './survey.js'", content)

    def test_converter_tabs_sourcedata_quick_select_smoke(self):
        module_expectations = {
            BIOMETRICS_MODULE: "sourcedata-files?kind=biometrics&project_path=${encodeURIComponent(effectiveProjectPath)}",
            ENVIRONMENT_MODULE: "sourcedata-files?kind=environment&project_path=${encodeURIComponent(effectiveProjectPath)}",
            PHYSIO_MODULE: "sourcedata-files?kind=physio&project_path=${encodeURIComponent(effectiveProjectPath)}",
            EYETRACKING_MODULE: "sourcedata-files?kind=eyetracking&project_path=${encodeURIComponent(effectiveProjectPath)}",
            PARTICIPANTS_MODULE: "sourcedata-files?kind=participants&project_path=${encodeURIComponent(effectiveProjectPath)}",
        }

        for module_path, list_snippet in module_expectations.items():
            content = module_path.read_text(encoding="utf-8")
            self.assertIn(list_snippet, content)
            self.assertIn(
                "/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}",
                content,
            )
            self.assertIn("prism-project-changed", content)

        survey_sourcedata_content = SURVEY_SOURCEDATA_QUICK_SELECT_MODULE.read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "sourcedata-files?project_path=${encodeURIComponent(effectiveProjectPath)}",
            survey_sourcedata_content,
        )
        self.assertIn(
            "/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}",
            survey_sourcedata_content,
        )
        self.assertIn("prism-project-changed", survey_sourcedata_content)

    def test_converter_bootstrap_installs_page_wide_api_fallback(self):
        content = CONVERTER_BOOTSTRAP.read_text(encoding="utf-8")

        self.assertIn(
            "import { installApiFetchFallback } from './shared/api.js';", content
        )
        self.assertIn(
            "import { resolveCurrentProjectPath } from './shared/project-state.js';",
            content,
        )
        self.assertIn("installApiFetchFallback();", content)
        self.assertIn("window.__prismConverterBootstrapInitialized", content)
        self.assertIn("let sessionPickerRequestToken = 0;", content)
        self.assertIn("function hasManualCustomValue(selectEl) {", content)
        self.assertIn("if (sessions.length === 1 && !hasManualCustomValue(sel)) {", content)
        self.assertIn(
            "const requestUrl = `/api/projects/sessions/declared?project_path=${encodeURIComponent(projectPath)}`;",
            content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {", content
        )

    def test_converter_bootstrap_supports_tab_query_parameter(self):
        content = CONVERTER_BOOTSTRAP.read_text(encoding="utf-8")

        self.assertIn("function activateConverterTabFromQuery() {", content)
        self.assertIn(
            "const requestedTab = new URLSearchParams(window.location.search).get('tab');",
            content,
        )
        self.assertIn(
            "window.bootstrap.Tab.getOrCreateInstance(tabButton).show();",
            content,
        )
        self.assertIn("activateConverterTabFromQuery();", content)

    def test_shared_api_exports_fetch_installer_using_native_fetch(self):
        content = SHARED_API.read_text(encoding="utf-8")

        self.assertIn(
            "const nativeFetch = (typeof window !== 'undefined' && typeof window.fetch === 'function')",
            content,
        )
        self.assertIn(
            "async function fetchWithApiFallbackUsing(fetchImpl, url, options = {}, fallbackMessage) {",
            content,
        )
        self.assertIn("export function installApiFetchFallback() {", content)
        self.assertIn("window.__prismApiFetchFallbackInstalled", content)
        self.assertIn(
            "window.fetch = function prismApiFetchWithFallback(url, options = {}) {",
            content,
        )
        self.assertIn("return fetchWithApiFallbackUsing(", content)

    def test_biometrics_module_resets_stale_state_and_uses_explicit_project_path(self):
        content = BIOMETRICS_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { resolveCurrentProjectPath } from '../../shared/project-state.js';",
            content,
        )
        self.assertIn("function clearBiometricsMessages() {", content)
        self.assertIn("function resetBiometricsWorkflowState() {", content)
        self.assertIn(
            "biometricsDataFile.addEventListener('change', function() {", content
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {", content
        )
        self.assertIn(
            "sourcedata-files?kind=biometrics&project_path=${encodeURIComponent(effectiveProjectPath)}",
            content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {", content
        )
        self.assertIn(
            "refreshBiometricsSourcedataQuickSelect();",
            content,
        )
        self.assertIn("formData.append('project_path', currentProjectPath);", content)
        self.assertIn("Please select a project first from the top of the page", content)

    def test_physio_and_eyetracking_modules_reset_stale_state_and_send_project_path(
        self,
    ):
        physio_content = PHYSIO_MODULE.read_text(encoding="utf-8")
        eyetracking_content = EYETRACKING_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { resolveCurrentProjectPath } from '../../shared/project-state.js';",
            physio_content,
        )
        self.assertIn("function clearAutoDetectedPhysioSource() {", physio_content)
        self.assertIn(
            "physioBatchFiles.addEventListener('change', function() {", physio_content
        )
        self.assertIn(
            "physioBatchFolder.addEventListener('change', function() {", physio_content
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {",
            physio_content,
        )
        self.assertIn(
            "sourcedata-files?kind=physio&project_path=${encodeURIComponent(effectiveProjectPath)}",
            physio_content,
        )
        self.assertIn(
            "refreshPhysioSourcedataQuickSelect();",
            physio_content,
        )
        self.assertIn(
            "fetch(`/api/check-sourcedata-physio?project_path=${encodeURIComponent(currentProjectPath)}`)",
            physio_content,
        )
        self.assertIn(
            "formData.append('project_path', currentProjectPath);", physio_content
        )

        self.assertIn(
            "import { resolveCurrentProjectPath } from '../../shared/project-state.js';",
            eyetracking_content,
        )
        self.assertIn(
            "function resetEyetrackingWorkflowState({ clearLog = true } = {}) {",
            eyetracking_content,
        )
        self.assertIn(
            "eyetrackingBatchFiles.addEventListener('change', function() {",
            eyetracking_content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {",
            eyetracking_content,
        )
        self.assertIn(
            "sourcedata-files?kind=eyetracking&project_path=${encodeURIComponent(effectiveProjectPath)}",
            eyetracking_content,
        )
        self.assertIn(
            "refreshEyetrackingSourcedataQuickSelect();",
            eyetracking_content,
        )
        self.assertIn(
            "formData.append('project_path', currentProjectPath);", eyetracking_content
        )
        self.assertIn(
            "Please select a project first from the top of the page",
            eyetracking_content,
        )

    def test_environment_and_participants_modules_include_sourcedata_quick_select(self):
        environment_content = ENVIRONMENT_MODULE.read_text(encoding="utf-8")
        participants_content = PARTICIPANTS_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "import { resolveCurrentProjectPath } from '../../shared/project-state.js';",
            environment_content,
        )
        self.assertIn(
            "sourcedata-files?kind=environment&project_path=${encodeURIComponent(effectiveProjectPath)}",
            environment_content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', () => {",
            environment_content,
        )
        self.assertIn("refreshEnvironmentSourcedataQuickSelect();", environment_content)

        self.assertIn(
            "import { resolveCurrentProjectPath } from '../../shared/project-state.js';",
            participants_content,
        )
        self.assertIn(
            "sourcedata-files?kind=participants&project_path=${encodeURIComponent(effectiveProjectPath)}",
            participants_content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {",
            participants_content,
        )
        self.assertIn("refreshParticipantsSourcedataQuickSelect();", participants_content)

    def test_eyetracking_template_references_bids_modality(self):
        content = EYETRACKING_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("PRISM/BIDS-style eyetracking outputs", content)
        self.assertIn(
            "Eyetracking stays available because BIDS defines an eyetracking modality.",
            content,
        )
        self.assertIn("Uses the BIDS eyetracking suffix", content)

    def test_session_registration_uses_visible_project_path(self):
        content = SESSION_REGISTER.read_text(encoding="utf-8")

        self.assertIn(
            "import { resolveCurrentProjectPath } from './project-state.js';", content
        )
        self.assertIn(
            "const currentProjectPath = resolveCurrentProjectPath();", content
        )
        self.assertIn("project_path: currentProjectPath,", content)
        self.assertIn("populateSessionPickers(currentProjectPath);", content)

    def test_survey_converter_refreshes_project_bound_helpers(self):
        content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        workflow_prepare_content = SURVEY_WORKFLOW_PREPARE_MODULE.read_text(
            encoding="utf-8"
        )
        survey_sourcedata_content = (
            SURVEY_SOURCEDATA_QUICK_SELECT_MODULE.read_text(encoding="utf-8")
        )
        workflow_template_check_content = (
            SURVEY_WORKFLOW_TEMPLATE_CHECK_MODULE.read_text(encoding="utf-8")
        )
        conversion_summary_content = SURVEY_CONVERSION_SUMMARY_MODULE.read_text(
            encoding="utf-8"
        )
        import_form_state_content = SURVEY_IMPORT_FORM_STATE_MODULE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "import { createSurveySourcedataQuickSelectController } from './survey-sourcedata-quick-select.js';",
            content,
        )
        self.assertIn(
            "const surveySourcedataQuickSelectController = createSurveySourcedataQuickSelectController({",
            content,
        )
        self.assertIn("surveySourcedataQuickSelectController.initialize();", content)
        self.assertIn("onProjectChanged: () => {", content)
        self.assertIn("resetSurveyImportFormState();", content)
        self.assertIn(
            "formData.append('project_path', currentProjectPath);",
            workflow_template_check_content,
        )
        self.assertIn(
            "let requestToken = 0;",
            survey_sourcedata_content,
        )
        self.assertIn(
            "`/api/projects/sourcedata-files?project_path=${encodeURIComponent(effectiveProjectPath)}`",
            survey_sourcedata_content,
        )
        self.assertIn("fetch(endpoint)", survey_sourcedata_content)
        self.assertIn(
            "/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}",
            survey_sourcedata_content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function handleProjectChanged() {",
            survey_sourcedata_content,
        )
        self.assertIn("if (activeRequestToken !== requestToken)", survey_sourcedata_content)
        self.assertIn(
            "resetSurveyImportFormState({ clearSelectedInput: true });",
            content,
        )
        self.assertIn(
            "surveySourcedataQuickSelectController.clearSelectedFile();",
            import_form_state_content,
        )
        self.assertIn("function buildVersionWizard(", content)
        self.assertIn("function formatVersionWizardRunLabel(run)", content)
        self.assertIn("Out-of-range share:", conversion_summary_content)
        self.assertIn("data-survey-open-advanced", conversion_summary_content)
        self.assertIn("openAdvancedOptionsValueOffsetEditor", content)
        self.assertIn(
            "convertSessionSelect.value = normalizedSessions.length === 1 ? normalizedSessions[0] : 'all';",
            content,
        )
        self.assertIn(
            "async function parseJsonResponse(response, requestLabel = 'Request') {",
            content,
        )
        self.assertIn(
            "Server response could not be parsed. Please retry once.",
            content,
        )
        self.assertIn(
            "data = await parseJsonResponse(response, 'Survey preparation');",
            workflow_prepare_content,
        )

    def test_survey_converter_project_change_clears_project_bound_selection_state(self):
        content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        import_form_state_content = SURVEY_IMPORT_FORM_STATE_MODULE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "function resetSurveyImportFormState({ clearSelectedInput = false } = {}) {",
            content,
        )
        self.assertIn(
            "surveyImportFormStateController.resetSurveyImportFormState({ clearSelectedInput });",
            content,
        )
        self.assertIn(
            "const surveyImportFormStateController = createSurveyImportFormStateController({",
            content,
        )
        self.assertIn(
            "import { createSurveyImportFormStateController } from './survey-import-form-state.js';",
            content,
        )
        self.assertIn(
            "export function createSurveyImportFormStateController({",
            import_form_state_content,
        )
        self.assertIn(
            "setVersionWizardRetryGateMode(null);\n        setAppliedTaskValueOffsetSelectionSignature('');\n        hideVersionWizard();\n        clearManualValueOffsetAdvice();",
            import_form_state_content,
        )
        self.assertIn(
            "if (clearSelectedInput) {\n            setConvertServerFilePath('');\n            if (convertExcelFile) {\n                convertExcelFile.value = '';\n            }\n        }\n        surveySourcedataQuickSelectController.clearSelectedFile();",
            import_form_state_content,
        )

    def test_survey_converter_prunes_stale_library_and_template_check_ui_branches(self):
        survey_content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        bootstrap_content = CONVERTER_BOOTSTRAP.read_text(encoding="utf-8")
        template_content = SURVEY_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("convertLibraryPathInput", survey_content)
        self.assertNotIn("convertBrowseLibraryBtn", survey_content)
        self.assertNotIn("checkProjectTemplatesBtn", survey_content)
        self.assertNotIn("refreshConvertLanguages()", survey_content)
        self.assertNotIn("surveyI18nWarning", survey_content)
        self.assertNotIn("surveyStructureWarning", survey_content)

        self.assertNotIn(
            "convertLibraryPathInput: document.getElementById('convertLibraryPath')",
            bootstrap_content,
        )
        self.assertNotIn(
            "convertBrowseLibraryBtn: document.getElementById('convertBrowseLibraryBtn')",
            bootstrap_content,
        )
        self.assertNotIn(
            "checkProjectTemplatesBtn: document.getElementById('checkProjectTemplatesBtn')",
            bootstrap_content,
        )

        self.assertNotIn('id="convertLibraryPath"', template_content)
        self.assertNotIn('id="convertBrowseLibraryBtn"', template_content)
        self.assertNotIn('id="checkProjectTemplatesBtn"', template_content)
        self.assertNotIn('id="surveyI18nWarning"', template_content)
        self.assertNotIn('id="surveyStructureWarning"', template_content)

    def test_survey_converter_uses_structured_value_offset_editor(self):
        module_content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        workflow_prepare_content = SURVEY_WORKFLOW_PREPARE_MODULE.read_text(
            encoding="utf-8"
        )
        value_offset_editor_content = SURVEY_VALUE_OFFSET_EDITOR_MODULE.read_text(
            encoding="utf-8"
        )
        template_content = SURVEY_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="convertValueOffsetsEditor"', template_content)
        self.assertIn('id="convertAddValueOffsetRowBtn"', template_content)
        self.assertIn('id="convertValueOffsetRows"', template_content)
        self.assertIn('id="convertValueOffsetsKnownTasks"', template_content)
        self.assertIn('id="convertValueOffsetsEmptyState"', template_content)
        self.assertIn('id="convertApplyValueOffsetsBtn"', template_content)
        self.assertIn('id="convertValueOffsetsStatus"', template_content)
        self.assertIn('class="form-control d-none" id="convertValueOffsets"', template_content)
        self.assertIn('class="alert d-none mb-3 survey-version-card"', template_content)
        self.assertIn('class="badge survey-version-count-badge" id="surveyVersionWizardCount"', template_content)

        self.assertIn("let taskValueOffsetEditorState = [];", module_content)
        self.assertIn("let appliedTaskValueOffsetSelectionSignature = '';", module_content)
        self.assertIn("function getAvailableSurveyTasksForValueOffsets() {", module_content)
        self.assertIn("function hasAppliedTaskValueOffsetSelections() {", module_content)
        self.assertIn("function updateTaskValueOffsetApplyState() {", module_content)
        self.assertIn("function renderTaskValueOffsetEditor() {", module_content)
        self.assertIn("function focusTaskValueOffsetEditor(rowId = null) {", module_content)
        self.assertIn("function ensureTaskValueOffsetEditorRow(task = '') {", module_content)
        self.assertIn("syncTaskValueOffsetTextFromState();", module_content)
        self.assertIn("surveyPreviewSelectionState.availableTasks", module_content)
        self.assertIn(
            "import { createSurveyValueOffsetEditorController } from './survey-value-offset-editor.js';",
            module_content,
        )
        self.assertIn(
            "const surveyValueOffsetEditorController = createSurveyValueOffsetEditorController({",
            module_content,
        )
        self.assertIn("getTemplateWorkflowGate: () => templateWorkflowGate,", module_content)
        self.assertIn("surveyValueOffsetEditorController.initialize();", module_content)
        self.assertIn("surveyValueOffsetEditorController.applyAdvancedOptionsState();", module_content)
        self.assertIn(
            "return surveyValueOffsetEditorController.hasManualTaskValueOffsets();",
            module_content,
        )
        self.assertIn(
            "return surveyValueOffsetEditorController.getAvailableSurveyTasksForValueOffsets();",
            module_content,
        )
        self.assertIn(
            "return surveyValueOffsetEditorController.getManualTaskValueOffsets();",
            module_content,
        )
        self.assertIn(
            "return surveyValueOffsetEditorController.hasAppliedTaskValueOffsetSelections();",
            module_content,
        )
        self.assertIn(
            "surveyValueOffsetEditorController.updateTaskValueOffsetApplyState();",
            module_content,
        )
        self.assertIn(
            "return surveyValueOffsetEditorController.renderTaskValueOffsetEditor();",
            module_content,
        )
        self.assertIn(
            "return surveyValueOffsetEditorController.ensureTaskValueOffsetEditorRow(task);",
            module_content,
        )
        self.assertIn(
            "surveyValueOffsetEditorController.handleApplyTaskValueOffsetsClick();",
            module_content,
        )
        self.assertNotIn("convertAddValueOffsetRowBtn.addEventListener('click'", module_content)
        self.assertIn("convertApplyValueOffsetsBtn?.addEventListener('click'", module_content)
        self.assertIn('survey-version-bulk-mode', module_content)
        self.assertIn('Use one version for all sessions/runs (recommended)', module_content)
        self.assertIn('setContextSelectorsLocked(Boolean(bulkModeToggle && bulkModeToggle.checked));', module_content)
        self.assertNotIn(
            "Complete each offset row with a task and numeric value, then click Apply offsets.",
            module_content,
        )
        self.assertIn("valueOffsetSelectionsPending", module_content)

        self.assertIn(
            "export function createSurveyValueOffsetEditorController({",
            value_offset_editor_content,
        )
        self.assertIn("function applyAdvancedOptionsState()", value_offset_editor_content)
        self.assertIn("function initialize()", value_offset_editor_content)
        self.assertIn(
            "function getTaskValueOffsetMapFromEditorState()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function hasManualTaskValueOffsets()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function hasAppliedTaskValueOffsetSelections()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function getAvailableSurveyTasksForValueOffsets()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function getManualTaskValueOffsets()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function updateTaskValueOffsetApplyState()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function handleApplyTaskValueOffsetsClick()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function renderTaskValueOffsetEditor()",
            value_offset_editor_content,
        )
        self.assertIn(
            "function setTaskValueOffsetEditorStateFromText(rawText)",
            value_offset_editor_content,
        )
        self.assertIn("data-role=\"operator\"", value_offset_editor_content)
        self.assertIn("data-role=\"magnitude\"", value_offset_editor_content)
        self.assertIn(
            "convertAdvancedToggle.addEventListener('change', applyAdvancedOptionsState);",
            value_offset_editor_content,
        )
        self.assertIn(
            "convertAddValueOffsetRowBtn.addEventListener('click', () => {",
            value_offset_editor_content,
        )
        self.assertIn(
            "convertValueOffsetRows.addEventListener('change', (event) => {",
            value_offset_editor_content,
        )
        self.assertIn(
            "convertValueOffsetRows.addEventListener('input', (event) => {",
            value_offset_editor_content,
        )
        self.assertIn(
            "convertValueOffsetRows.addEventListener('click', (event) => {",
            value_offset_editor_content,
        )
        self.assertIn("handleApplyTaskValueOffsetsClick,", value_offset_editor_content)
        self.assertIn(
            "if (Object.keys(multivariantTasks).length > 0 && !hasAppliedVersionWizardSelections()) {",
            workflow_prepare_content,
        )

    def test_survey_participants_metadata_is_extracted_module(self):
        survey_content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        participants_content = SURVEY_PARTICIPANTS_METADATA_MODULE.read_text(
            encoding="utf-8"
        )
        workflow_prepare_content = SURVEY_WORKFLOW_PREPARE_MODULE.read_text(
            encoding="utf-8"
        )
        workflow_preview_content = SURVEY_WORKFLOW_PREVIEW_MODULE.read_text(
            encoding="utf-8"
        )
        workflow_convert_content = SURVEY_WORKFLOW_CONVERT_MODULE.read_text(
            encoding="utf-8"
        )
        workflow_convert_results_content = (
            SURVEY_WORKFLOW_CONVERT_RESULTS_MODULE.read_text(encoding="utf-8")
        )
        workflow_progress_content = SURVEY_WORKFLOW_PROGRESS_MODULE.read_text(
            encoding="utf-8"
        )
        workflow_sourcedata_content = (
            SURVEY_SOURCEDATA_QUICK_SELECT_MODULE.read_text(encoding="utf-8")
        )
        workflow_template_check_content = (
            SURVEY_WORKFLOW_TEMPLATE_CHECK_MODULE.read_text(encoding="utf-8")
        )
        template_results_content = SURVEY_TEMPLATE_RESULTS_MODULE.read_text(
            encoding="utf-8"
        )
        conversion_summary_content = SURVEY_CONVERSION_SUMMARY_MODULE.read_text(
            encoding="utf-8"
        )
        conversion_log_content = SURVEY_CONVERSION_LOG_MODULE.read_text(
            encoding="utf-8"
        )
        convert_feedback_content = SURVEY_CONVERT_FEEDBACK_MODULE.read_text(
            encoding="utf-8"
        )
        file_separator_utils_content = SURVEY_FILE_SEPARATOR_UTILS_MODULE.read_text(
            encoding="utf-8"
        )
        unmatched_templates_content = SURVEY_UNMATCHED_TEMPLATES_MODULE.read_text(
            encoding="utf-8"
        )
        import_form_state_content = SURVEY_IMPORT_FORM_STATE_MODULE.read_text(
            encoding="utf-8"
        )
        near_item_match_review_content = (
            SURVEY_NEAR_ITEM_MATCH_REVIEW_MODULE.read_text(encoding="utf-8")
        )
        workflow_response_utils_content = (
            SURVEY_WORKFLOW_RESPONSE_UTILS_MODULE.read_text(encoding="utf-8")
        )
        version_context_utils_content = (
            SURVEY_VERSION_CONTEXT_UTILS_MODULE.read_text(encoding="utf-8")
        )
        validation_results_content = SURVEY_VALIDATION_RESULTS_MODULE.read_text(
            encoding="utf-8"
        )
        value_offset_utils_content = SURVEY_VALUE_OFFSET_UTILS_MODULE.read_text(
            encoding="utf-8"
        )
        value_offset_editor_content = SURVEY_VALUE_OFFSET_EDITOR_MODULE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "import { createSurveyParticipantsMetadataController } from './survey-participants-metadata.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyWorkflowPrepareController } from './survey-workflow-prepare.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyWorkflowPreviewController } from './survey-workflow-preview.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyWorkflowConvertController } from './survey-workflow-convert.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyWorkflowConvertResultsController } from './survey-workflow-convert-results.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyWorkflowProgressController } from './survey-workflow-progress.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveySourcedataQuickSelectController } from './survey-sourcedata-quick-select.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyWorkflowTemplateCheckController } from './survey-workflow-template-check.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyTemplateResultsController } from './survey-template-results.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyConversionSummaryController } from './survey-conversion-summary.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyConversionLogController } from './survey-conversion-log.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyConvertFeedbackController } from './survey-convert-feedback.js';",
            survey_content,
        )
        self.assertIn(
            "from './survey-file-separator-utils.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyUnmatchedTemplatesController } from './survey-unmatched-templates.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyImportFormStateController } from './survey-import-form-state.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyNearItemMatchReviewController } from './survey-near-item-match-review.js';",
            survey_content,
        )
        self.assertIn(
            "from './survey-workflow-response-utils.js';",
            survey_content,
        )
        self.assertIn(
            "from './survey-version-context-utils.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyValidationResultsController } from './survey-validation-results.js';",
            survey_content,
        )
        self.assertIn(
            "import { createSurveyValueOffsetEditorController } from './survey-value-offset-editor.js';",
            survey_content,
        )
        self.assertIn(
            "from './survey-value-offset-utils.js';",
            survey_content,
        )
        self.assertIn(
            "const participantsMetadataController = createSurveyParticipantsMetadataController({",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowPrepareController = createSurveyWorkflowPrepareController({",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowPreviewController = createSurveyWorkflowPreviewController({",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowConvertController = createSurveyWorkflowConvertController({",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowConvertResultsController = createSurveyWorkflowConvertResultsController({",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowProgressController = createSurveyWorkflowProgressController({",
            survey_content,
        )
        self.assertIn(
            "const surveySourcedataQuickSelectController = createSurveySourcedataQuickSelectController({",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowTemplateCheckController = createSurveyWorkflowTemplateCheckController({",
            survey_content,
        )
        self.assertIn(
            "const surveyTemplateResultsController = createSurveyTemplateResultsController({",
            survey_content,
        )
        self.assertIn(
            "const surveyConversionSummaryController = createSurveyConversionSummaryController({",
            survey_content,
        )
        self.assertIn(
            "const surveyConversionLogController = createSurveyConversionLogController({",
            survey_content,
        )
        self.assertIn(
            "surveyConvertFeedbackController = createSurveyConvertFeedbackController({",
            survey_content,
        )
        self.assertIn(
            "const surveyUnmatchedTemplatesController = createSurveyUnmatchedTemplatesController({",
            survey_content,
        )
        self.assertIn(
            "const surveyImportFormStateController = createSurveyImportFormStateController({",
            survey_content,
        )
        self.assertIn(
            "surveyNearItemMatchReviewController = createSurveyNearItemMatchReviewController({",
            survey_content,
        )
        self.assertIn(
            "const surveyValidationResultsController = createSurveyValidationResultsController({",
            survey_content,
        )
        self.assertIn(
            "const surveyValueOffsetEditorController = createSurveyValueOffsetEditorController({",
            survey_content,
        )
        self.assertIn(
            "participantsMetadataController.displayParticipantMetadataSection(data);",
            survey_content,
        )
        self.assertIn(
            "surveyTemplateResultsController.displayTemplateSingle(data);",
            survey_content,
        )
        self.assertIn(
            "surveyTemplateResultsController.displayTemplateGroups(data);",
            survey_content,
        )
        self.assertIn(
            "surveyTemplateResultsController.displayTemplateQuestions(data);",
            survey_content,
        )
        self.assertIn(
            "surveyConversionSummaryController.displayConversionSummary(summary);",
            survey_content,
        )
        self.assertIn("surveyConversionLogController.initialize();", survey_content)
        self.assertIn(
            "surveyConversionLogController.appendLog(message, type, logElement);",
            survey_content,
        )
        self.assertIn(
            "surveyConversionLogController.resetConversionUI();",
            survey_content,
        )
        self.assertIn(
            "surveyUnmatchedTemplatesController.initialize();",
            survey_content,
        )
        self.assertIn(
            "surveyUnmatchedTemplatesController.displayUnmatchedGroupsError(data);",
            survey_content,
        )
        self.assertIn(
            "surveyImportFormStateController.resetSurveyImportFormState({ clearSelectedInput });",
            survey_content,
        )
        self.assertIn(
            "return surveyNearItemMatchReviewController.promptNearMatchSelection(payload, actionLabel);",
            survey_content,
        )
        self.assertIn(
            "surveyValidationResultsController.displayValidationResults(validation, prefix);",
            survey_content,
        )
        self.assertIn("surveyValueOffsetEditorController.initialize();", survey_content)
        self.assertIn(
            "return normalizeTaskValueOffsetsMap(offsetMap, normalizeNearMatchTaskName);",
            survey_content,
        )
        self.assertIn(
            "return parseTaskValueOffsetsTextWithNormalizer(rawText, normalizeNearMatchTaskName);",
            survey_content,
        )
        self.assertIn(
            "formData.append('selected_tasks', JSON.stringify(selectedSurveyTasks));",
            survey_content,
        )
        self.assertNotIn("function displayTemplateSingle(data)", survey_content)
        self.assertNotIn("function displayTemplateGroups(data)", survey_content)
        self.assertNotIn("function displayTemplateQuestions(data)", survey_content)
        self.assertNotIn("function setupTemplateSaveToProject(data, mode)", survey_content)
        self.assertNotIn("function parseNumericOffsetValue(rawValue)", survey_content)
        self.assertNotIn("function formatSignedOffset(offset)", survey_content)
        self.assertNotIn("function formatOffsetMagnitude(offset)", survey_content)
        self.assertNotIn("function normalizeValidationIssueText(value)", survey_content)
        self.assertNotIn("function renderValidationGroupFiles(group)", survey_content)
        self.assertNotIn("const colors = {", survey_content)
        self.assertNotIn("Review Safe Near Item Matches", survey_content)
        self.assertNotIn("Could not open the requested converter tab.", survey_content)
        self.assertNotIn(
            "return JSON.parse(trimmed);",
            survey_content,
        )
        self.assertNotIn("window.saveUnmatchedTemplate = async function(index)", survey_content)
        self.assertNotIn("window.saveAllUnmatchedTemplates = async function()", survey_content)
        self.assertNotIn("function checkAllGroupsSaved()", survey_content)
        self.assertNotIn(
            "function renderSurveyTaskReviewSummary(taskSummaries)",
            survey_content,
        )
        self.assertNotIn(
            "function bindSurveyTaskSelectionControls()",
            survey_content,
        )
        self.assertNotIn(
            "function updateSurveyTaskSelectionSummaryText()",
            survey_content,
        )
        self.assertIn(
            "surveyWorkflowPrepareController.prepareSurveyWorkflow({",
            workflow_preview_content,
        )
        self.assertIn(
            "surveyWorkflowPrepareController.prepareSurveyWorkflow({",
            workflow_convert_content,
        )
        self.assertIn(
            "surveyWorkflowPreviewController.handlePreviewClick();",
            survey_content,
        )
        self.assertIn(
            "surveyWorkflowConvertController.handleConvertClick();",
            survey_content,
        )
        self.assertIn(
            "surveyWorkflowProgressController.startSurveyRunProgress(mode);",
            survey_content,
        )
        self.assertIn(
            "surveyWorkflowProgressController.finishSurveyRunProgress(mode, outcome);",
            survey_content,
        )
        self.assertIn(
            "surveySourcedataQuickSelectController.initialize();",
            survey_content,
        )
        self.assertIn(
            "surveyWorkflowTemplateCheckController.initialize();",
            survey_content,
        )

        self.assertIn(
            "export function createSurveyParticipantsMetadataController({ escapeHtml }) {",
            participants_content,
        )
        self.assertIn(
            "survey_schema_merge_mode: 'survey_selected'",
            participants_content,
        )
        self.assertIn("survey_selected_schema: schema", participants_content)

        self.assertIn(
            "export function createSurveyWorkflowPrepareController({",
            workflow_prepare_content,
        )
        self.assertIn("formData.append('workflow_command', 'prepare');", workflow_prepare_content)
        self.assertIn("fetch('/api/survey-workflow-command'", workflow_prepare_content)
        self.assertNotIn("fetch('/api/survey-prepare-workflow'", workflow_prepare_content)
        self.assertIn("function finishPreparationPhase(mode, outcome)", workflow_prepare_content)
        self.assertIn("function handleLateSetupBlocker(mode, payload, selectedValueOffsets = {})", workflow_prepare_content)

        self.assertIn(
            "export function createSurveyWorkflowPreviewController({",
            workflow_preview_content,
        )
        self.assertIn(
            "async function handlePreviewClick() {",
            workflow_preview_content,
        )
        self.assertIn("formData.append('workflow_command', 'preview');", workflow_preview_content)
        self.assertIn("fetch('/api/survey-workflow-command'", workflow_preview_content)
        self.assertNotIn("fetch('/api/survey-convert-preview'", workflow_preview_content)
        self.assertIn(
            "surveyWorkflowPrepareController.finishPreparationPhase('preview', preparation.outcome);",
            workflow_preview_content,
        )

        self.assertIn(
            "export function createSurveyWorkflowConvertController({",
            workflow_convert_content,
        )
        self.assertIn(
            "async function handleConvertClick() {",
            workflow_convert_content,
        )
        self.assertIn("formData.append('workflow_command', 'convert');", workflow_convert_content)
        self.assertIn("fetch('/api/survey-workflow-command'", workflow_convert_content)
        self.assertNotIn("fetch('/api/survey-convert-validate'", workflow_convert_content)
        self.assertIn("handleConvertSuccess(data, {", workflow_convert_content)
        self.assertNotIn(
            "appendLog('✓ Validation passed - dataset is valid!', 'success');",
            workflow_convert_content,
        )
        self.assertNotIn(
            "showParticipantRegistryWarning(",
            workflow_convert_content,
        )
        self.assertIn(
            "surveyWorkflowPrepareController.finishPreparationPhase('convert', preparation.outcome);",
            workflow_convert_content,
        )
        self.assertIn(
            "selectedTasks: selectedSurveyTasks,",
            workflow_convert_content,
        )

        self.assertIn(
            "export function createSurveyWorkflowConvertResultsController({",
            workflow_convert_results_content,
        )
        self.assertIn(
            "function handleConvertSuccess(data, { sourceFilename = '' } = {}) {",
            workflow_convert_results_content,
        )
        self.assertIn(
            "appendLog('✓ Validation passed - dataset is valid!', 'success');",
            workflow_convert_results_content,
        )
        self.assertIn(
            "showParticipantRegistryWarning(",
            workflow_convert_results_content,
        )
        self.assertIn(
            "registerSessionInProject(regSessionVal, regTasks, 'survey', normalizedFilename, convType);",
            workflow_convert_results_content,
        )

        self.assertIn(
            "export function createSurveyWorkflowProgressController({",
            workflow_progress_content,
        )
        self.assertIn(
            "function startSurveyRunProgress(mode)",
            workflow_progress_content,
        )
        self.assertIn(
            "function finishSurveyRunProgress(mode, outcome)",
            workflow_progress_content,
        )
        self.assertIn(
            "function getIsSurveyRunAwaitingConfirmation()",
            workflow_progress_content,
        )

        self.assertIn(
            "export function createSurveySourcedataQuickSelectController({",
            workflow_sourcedata_content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function handleProjectChanged() {",
            workflow_sourcedata_content,
        )

        self.assertIn(
            "export function createSurveyWorkflowTemplateCheckController({",
            workflow_template_check_content,
        )
        self.assertIn(
            "async function handleCheckProjectTemplatesClick()",
            workflow_template_check_content,
        )
        self.assertIn(
            "fetch('/api/survey-check-project-templates'",
            workflow_template_check_content,
        )
        self.assertIn(
            "function handleVersionWizardApplyClick()",
            workflow_template_check_content,
        )
        self.assertIn(
            "surveyVersionWizardApplyBtn?.addEventListener('click', handleVersionWizardApplyClick);",
            workflow_template_check_content,
        )
        self.assertIn(
            "setAppliedTemplateVersionSelectionSignature(currentSignature);",
            workflow_template_check_content,
        )
        self.assertIn(
            "setVersionWizardRetryGateMode(null);",
            workflow_template_check_content,
        )
        self.assertIn("handleVersionWizardApplyClick,", workflow_template_check_content)

        self.assertIn(
            "export function createSurveyTemplateResultsController({",
            template_results_content,
        )
        self.assertIn(
            "fetch('/api/limesurvey-save-to-project',",
            template_results_content,
        )
        self.assertIn(
            "fetch(`/api/library-template/${encodeURIComponent(templateKey)}`);",
            template_results_content,
        )

        self.assertIn(
            "export function createSurveyConversionSummaryController({",
            conversion_summary_content,
        )
        self.assertIn(
            "function displayConversionSummary(summary)",
            conversion_summary_content,
        )
        self.assertIn(
            "function bindSurveyTaskSelectionControls()",
            conversion_summary_content,
        )
        self.assertIn(
            "data-survey-open-advanced",
            conversion_summary_content,
        )

        self.assertIn(
            "export function createSurveyConversionLogController({",
            conversion_log_content,
        )
        self.assertIn(
            "function initialize()",
            conversion_log_content,
        )
        self.assertIn(
            "toggleLogBtn.addEventListener('click', function() {",
            conversion_log_content,
        )
        self.assertIn(
            "function appendLog(message, type = 'info', logElement = null)",
            conversion_log_content,
        )
        self.assertIn(
            "function resetConversionUI()",
            conversion_log_content,
        )

        self.assertIn(
            "export function createSurveyConvertFeedbackController({",
            convert_feedback_content,
        )
        self.assertIn(
            "function getProjectSaveSummary(data)",
            convert_feedback_content,
        )
        self.assertIn(
            "function getParticipantRegistryWarning(payload)",
            convert_feedback_content,
        )
        self.assertIn(
            "function showParticipantRegistryWarning(messagePrefix, warning)",
            convert_feedback_content,
        )
        self.assertIn(
            "Could not open the requested converter tab.",
            convert_feedback_content,
        )

        self.assertIn(
            "export function isDelimitedSurveyFilename(filename)",
            file_separator_utils_content,
        )
        self.assertIn(
            "export function getSelectedSeparator(filename = '', convertSeparator = null)",
            file_separator_utils_content,
        )
        self.assertIn(
            "export function updateSeparatorVisibility(filename = '', surveySeparatorGroup = null)",
            file_separator_utils_content,
        )

        self.assertIn(
            "export function createSurveyUnmatchedTemplatesController({",
            unmatched_templates_content,
        )
        self.assertIn(
            "function displayUnmatchedGroupsError(data)",
            unmatched_templates_content,
        )
        self.assertIn(
            "window.saveUnmatchedTemplate = saveUnmatchedTemplate;",
            unmatched_templates_content,
        )
        self.assertIn(
            "window.saveAllUnmatchedTemplates = saveAllUnmatchedTemplates;",
            unmatched_templates_content,
        )

        self.assertIn(
            "export function createSurveyImportFormStateController({",
            import_form_state_content,
        )
        self.assertIn(
            "function resetSurveyImportFormState({ clearSelectedInput = false } = {})",
            import_form_state_content,
        )
        self.assertIn(
            "setConvertServerFilePath('');",
            import_form_state_content,
        )

        self.assertIn(
            "export function createSurveyNearItemMatchReviewController({",
            near_item_match_review_content,
        )
        self.assertIn(
            "function collectNearMatchCandidates(payload)",
            near_item_match_review_content,
        )
        self.assertIn(
            "function buildNearMatchConfirmationMessage(payload, actionLabel)",
            near_item_match_review_content,
        )
        self.assertIn(
            "function promptNearMatchSelection(payload, actionLabel)",
            near_item_match_review_content,
        )
        self.assertIn(
            "Review Safe Near Item Matches",
            near_item_match_review_content,
        )

        self.assertIn(
            "export function summarizeServerResponseText(rawText)",
            workflow_response_utils_content,
        )
        self.assertIn(
            "export async function parseJsonResponse(response, requestLabel = 'Request')",
            workflow_response_utils_content,
        )
        self.assertIn(
            "return JSON.parse(trimmed);",
            workflow_response_utils_content,
        )

        self.assertIn(
            "export function normalizeVersionSelectionSession(session)",
            version_context_utils_content,
        )
        self.assertIn(
            "export function normalizeVersionSelectionRun(run)",
            version_context_utils_content,
        )
        self.assertIn(
            "export function buildVersionSelectionKey({ task, session = null, run = null })",
            version_context_utils_content,
        )
        self.assertIn(
            "export function deriveDetectedContexts(taskRuns, previewParticipants, detectedSessions = [])",
            version_context_utils_content,
        )

        self.assertIn(
            "export function createSurveyValidationResultsController({",
            validation_results_content,
        )
        self.assertIn(
            "function displayValidationResults(validation, prefix = '')",
            validation_results_content,
        )
        self.assertIn(
            "function renderValidationGroupFiles(group)",
            validation_results_content,
        )
        self.assertIn(
            "function extractValidationIssueKind(message)",
            validation_results_content,
        )
        self.assertIn(
            "schema error:",
            validation_results_content,
        )
        self.assertIn(
            "files share this same issue",
            validation_results_content,
        )

        self.assertIn(
            "export function parseNumericOffsetValue(rawValue)",
            value_offset_utils_content,
        )
        self.assertIn(
            "export function normalizeTaskValueOffsets(offsetMap, normalizeTaskName)",
            value_offset_utils_content,
        )
        self.assertIn(
            "export function parseTaskValueOffsetsText(rawText, normalizeTaskName)",
            value_offset_utils_content,
        )
        self.assertIn(
            "Wildcard offsets are disabled in Advanced options.",
            value_offset_utils_content,
        )
        self.assertIn(
            "setAppliedTaskValueOffsetSelectionSignature: (value) => {",
            survey_content,
        )
        self.assertIn(
            "getSurveyPreviewSelectionState: () => surveyPreviewSelectionState,",
            survey_content,
        )
        self.assertIn("getTemplateVersionSelections,", survey_content)
        self.assertIn(
            "getLastPreviewSurveyTasks: () => {",
            survey_content,
        )
        self.assertIn(
            "getAppliedTaskValueOffsetSelectionSignature: () => appliedTaskValueOffsetSelectionSignature,",
            survey_content,
        )
        self.assertIn(
            "hasMultiVersionWizardTasks,",
            survey_content,
        )
        self.assertIn(
            "setAppliedTemplateVersionSelectionSignature: (value) => {",
            survey_content,
        )
        self.assertIn(
            "surveyVersionWizardApplyBtn,",
            survey_content,
        )
        self.assertIn(
            "const surveyWorkflowTemplateCheckController = createSurveyWorkflowTemplateCheckController({",
            survey_content,
        )
        self.assertNotIn(
            "surveyVersionWizardApplyBtn?.addEventListener('click'",
            survey_content,
        )
        self.assertNotIn(
            "appliedTemplateVersionSelectionSignature = getCurrentTemplateVersionSelectionSignature();",
            survey_content,
        )
        self.assertIn(
            "export function createSurveyValueOffsetEditorController({",
            value_offset_editor_content,
        )
        self.assertIn(
            "function initialize()",
            workflow_template_check_content,
        )

    def test_converter_modules_surface_backend_save_paths(self):
        biometrics_content = BIOMETRICS_MODULE.read_text(encoding="utf-8")
        survey_content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        convert_feedback_content = SURVEY_CONVERT_FEEDBACK_MODULE.read_text(
            encoding="utf-8"
        )
        physio_content = PHYSIO_MODULE.read_text(encoding="utf-8")
        eyetracking_content = EYETRACKING_MODULE.read_text(encoding="utf-8")

        self.assertIn("project_output_path", biometrics_content)
        self.assertIn("project_output_paths", biometrics_content)
        self.assertNotIn("Data saved to project folder", biometrics_content)

        self.assertIn("project_output_path", convert_feedback_content)
        self.assertIn("project_output_paths", convert_feedback_content)
        self.assertNotIn("Data saved to project folder", survey_content)

        self.assertIn("result.project_output_path", physio_content)
        self.assertIn("result.project_output_paths", physio_content)
        self.assertNotIn("project dataset root", physio_content)

        self.assertIn("result.project_output_path", eyetracking_content)
        self.assertIn("result.project_output_paths", eyetracking_content)
        self.assertNotIn("Files also saved to project.", eyetracking_content)


if __name__ == "__main__":
    unittest.main()
