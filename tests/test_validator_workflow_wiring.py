import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR_TEMPLATE = REPO_ROOT / "app" / "templates" / "index.html"
VALIDATOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "index.js"
RESULTS_TEMPLATE = REPO_ROOT / "app" / "templates" / "results.html"
RESULTS_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "results.js"
VALIDATION_BLUEPRINT = (
    REPO_ROOT / "app" / "src" / "web" / "blueprints" / "validation.py"
)


class TestValidatorWorkflowWiring(unittest.TestCase):
    def test_validator_template_preserves_default_library_and_resume_controls(self):
        content = VALIDATOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "data-default-value=\"{{ default_library_path | default('') }}\"", content
        )
        self.assertIn('id="resumeValidationWrap"', content)
        self.assertIn('id="resumeValidationBtn"', content)

    def test_validator_script_uses_fallback_and_resumable_progress(self):
        content = VALIDATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "const validationResumeStorageKey = 'prism_active_validation_job';", content
        )
        self.assertIn(
            "async function fetchWithApiFallback(url, options = {}, fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.')",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback(progressUrl, {", content
        )
        self.assertIn(
            "const response = await fetchWithApiFallback(requestUrl, {", content
        )
        self.assertIn("persistActiveValidationJob({", content)
        self.assertIn("async function resumeStoredValidationJob() {", content)
        self.assertIn("resumeStoredValidationJob();", content)

    def test_validator_script_refreshes_default_library_path_and_only_submits_explicit_override(
        self,
    ):
        content = VALIDATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("let libraryDefaultRequestToken = 0;", content)
        self.assertIn(
            "function hasExplicitLibraryPathOverride(value, defaultValue) {", content
        )
        self.assertIn("function getExplicitLibraryPathOverride() {", content)
        self.assertIn("async function refreshDefaultLibraryPath() {", content)
        self.assertIn("/api/validation/default-library-path", content)
        self.assertIn(
            "const libraryPathOverride = getExplicitLibraryPathOverride();", content
        )
        self.assertIn(
            "validationData.append('library_path', libraryPathOverride);", content
        )
        self.assertIn("formData.append('library_path', libraryPathOverride);", content)
        self.assertNotIn("function getEffectiveLibraryPath() {", content)

    def test_validator_drop_handler_no_longer_marks_folder_as_selected(self):
        content = VALIDATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "Folder drag and drop cannot reliably select the dataset root here. Use Browse Folder instead.",
            content,
        )
        self.assertNotIn("updateUploadButton('folder', null, files.length);", content)

    def test_validation_blueprint_resolves_default_library_and_stores_warning_visibility(
        self,
    ):
        content = VALIDATION_BLUEPRINT.read_text(encoding="utf-8")

        self.assertIn(
            "def _get_default_validation_library_path(project_path: str | None = None) -> str:",
            content,
        )
        self.assertIn("def _resolve_requested_validation_library_path(", content)
        self.assertIn(
            '@validation_bp.route("/api/validation/default-library-path", methods=["GET"])',
            content,
        )
        self.assertIn('results["show_bids_warnings"] = show_bids_warnings', content)
        self.assertIn('"project_path": dataset_path,', content)

    def test_results_template_exposes_revalidate_mode_controls_and_progress_panel(self):
        content = RESULTS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="revalidateForm"', content)
        self.assertIn('id="revalidateMode"', content)
        self.assertIn('value="standard"', content)
        self.assertIn('value="prism-only"', content)
        self.assertIn('value="bids-only"', content)
        self.assertIn('id="revalidateProgressPanel"', content)
        self.assertIn('id="revalidateProgressBar"', content)
        self.assertIn('id="revalidateProgressError"', content)

    def test_results_script_revalidates_via_ajax_progress_polling(self):
        content = RESULTS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("const revalidateForm = document.getElementById('revalidateForm');", content)
        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn("async function pollRevalidationProgress(progressUrl, progressFloor = 0)", content)
        self.assertIn("headers: { 'X-Requested-With': 'XMLHttpRequest' },", content)
        self.assertIn("method: 'POST'", content)
        self.assertIn("await pollRevalidationProgress(payload.progress_url, 5);", content)
        self.assertIn("setActionsDisabled(true);", content)
        self.assertIn("showRevalidationError(error.message || 'Re-validation failed.');", content)


if __name__ == "__main__":
    unittest.main()
