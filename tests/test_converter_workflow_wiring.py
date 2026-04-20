import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERTER_BOOTSTRAP = REPO_ROOT / "app" / "static" / "js" / "converter-bootstrap.js"
SHARED_API = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
SESSION_REGISTER = REPO_ROOT / "app" / "static" / "js" / "shared" / "session-register.js"
EYETRACKING_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_eyetracking.html"
BIOMETRICS_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "biometrics.js"
SURVEY_CONVERT_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-convert.js"
PHYSIO_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "physio.js"
EYETRACKING_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "eyetracking.js"


class TestConverterWorkflowWiring(unittest.TestCase):
    def test_converter_bootstrap_installs_page_wide_api_fallback(self):
        content = CONVERTER_BOOTSTRAP.read_text(encoding="utf-8")

        self.assertIn("import { installApiFetchFallback } from './shared/api.js';", content)
        self.assertIn("import { resolveCurrentProjectPath } from './shared/project-state.js';", content)
        self.assertIn("installApiFetchFallback();", content)
        self.assertIn("let sessionPickerRequestToken = 0;", content)
        self.assertIn("const requestUrl = `/api/projects/sessions/declared?project_path=${encodeURIComponent(projectPath)}`;", content)
        self.assertIn("window.addEventListener('prism-project-changed', function() {", content)

    def test_shared_api_exports_fetch_installer_using_native_fetch(self):
        content = SHARED_API.read_text(encoding="utf-8")

        self.assertIn("const nativeFetch = (typeof window !== 'undefined' && typeof window.fetch === 'function')", content)
        self.assertIn("async function fetchWithApiFallbackUsing(fetchImpl, url, options = {}, fallbackMessage) {", content)
        self.assertIn("export function installApiFetchFallback() {", content)
        self.assertIn("window.__prismApiFetchFallbackInstalled", content)
        self.assertIn("window.fetch = function prismApiFetchWithFallback(url, options = {}) {", content)
        self.assertIn("return fetchWithApiFallbackUsing(", content)

    def test_biometrics_module_resets_stale_state_and_uses_explicit_project_path(self):
        content = BIOMETRICS_MODULE.read_text(encoding="utf-8")

        self.assertIn("import { resolveCurrentProjectPath } from '../../shared/project-state.js';", content)
        self.assertIn("function clearBiometricsMessages() {", content)
        self.assertIn("function resetBiometricsWorkflowState() {", content)
        self.assertIn("biometricsDataFile.addEventListener('change', function() {", content)
        self.assertIn("window.addEventListener('prism-project-changed', function() {", content)
        self.assertIn("formData.append('project_path', currentProjectPath);", content)
        self.assertIn("Please select a project first from the top of the page", content)

    def test_physio_and_eyetracking_modules_reset_stale_state_and_send_project_path(self):
        physio_content = PHYSIO_MODULE.read_text(encoding="utf-8")
        eyetracking_content = EYETRACKING_MODULE.read_text(encoding="utf-8")

        self.assertIn("import { resolveCurrentProjectPath } from '../../shared/project-state.js';", physio_content)
        self.assertIn("function clearAutoDetectedPhysioSource() {", physio_content)
        self.assertIn("physioBatchFiles.addEventListener('change', function() {", physio_content)
        self.assertIn("physioBatchFolder.addEventListener('change', function() {", physio_content)
        self.assertIn("window.addEventListener('prism-project-changed', function() {", physio_content)
        self.assertIn("fetch(`/api/check-sourcedata-physio?project_path=${encodeURIComponent(currentProjectPath)}`)", physio_content)
        self.assertIn("formData.append('project_path', currentProjectPath);", physio_content)

        self.assertIn("import { resolveCurrentProjectPath } from '../../shared/project-state.js';", eyetracking_content)
        self.assertIn("function resetEyetrackingWorkflowState({ clearLog = true } = {}) {", eyetracking_content)
        self.assertIn("eyetrackingBatchFiles.addEventListener('change', function() {", eyetracking_content)
        self.assertIn("window.addEventListener('prism-project-changed', function() {", eyetracking_content)
        self.assertIn("formData.append('project_path', currentProjectPath);", eyetracking_content)
        self.assertIn("Please select a project first from the top of the page", eyetracking_content)

    def test_eyetracking_template_references_bids_modality(self):
        content = EYETRACKING_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("PRISM/BIDS-style eyetracking outputs", content)
        self.assertIn("Eyetracking stays available because BIDS defines an eyetracking modality.", content)
        self.assertIn("Uses the BIDS eyetracking suffix", content)

    def test_session_registration_uses_visible_project_path(self):
        content = SESSION_REGISTER.read_text(encoding="utf-8")

        self.assertIn("import { resolveCurrentProjectPath } from './project-state.js';", content)
        self.assertIn("const currentProjectPath = resolveCurrentProjectPath();", content)
        self.assertIn("project_path: currentProjectPath,", content)
        self.assertIn("populateSessionPickers(currentProjectPath);", content)

    def test_survey_converter_refreshes_project_bound_helpers(self):
        content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")

        self.assertIn("let sourcedataRequestToken = 0;", content)
        self.assertIn("formData.append('project_path', currentProjectPath);", content)
        self.assertIn("function refreshSourcedataQuickSelect(projectPath = resolveCurrentProjectPath()) {", content)
        self.assertIn("fetch(`/api/projects/sourcedata-files?project_path=${encodeURIComponent(projectPath)}`)", content)
        self.assertIn("/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}", content)
        self.assertIn("window.addEventListener('prism-project-changed', function() {", content)

    def test_converter_modules_surface_backend_save_paths(self):
        biometrics_content = BIOMETRICS_MODULE.read_text(encoding="utf-8")
        survey_content = SURVEY_CONVERT_MODULE.read_text(encoding="utf-8")
        physio_content = PHYSIO_MODULE.read_text(encoding="utf-8")
        eyetracking_content = EYETRACKING_MODULE.read_text(encoding="utf-8")

        self.assertIn("project_output_path", biometrics_content)
        self.assertIn("project_output_paths", biometrics_content)
        self.assertNotIn("Data saved to project folder", biometrics_content)

        self.assertIn("project_output_path", survey_content)
        self.assertIn("project_output_paths", survey_content)
        self.assertNotIn("Data saved to project folder", survey_content)

        self.assertIn("result.project_output_path", physio_content)
        self.assertIn("result.project_output_paths", physio_content)
        self.assertNotIn("project dataset root", physio_content)

        self.assertIn("result.project_output_path", eyetracking_content)
        self.assertIn("result.project_output_paths", eyetracking_content)
        self.assertNotIn("Files also saved to project.", eyetracking_content)


if __name__ == "__main__":
    unittest.main()