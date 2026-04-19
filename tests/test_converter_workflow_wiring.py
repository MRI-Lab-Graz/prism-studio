import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERTER_BOOTSTRAP = REPO_ROOT / "app" / "static" / "js" / "converter-bootstrap.js"
SHARED_API = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
BIOMETRICS_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "biometrics.js"
SURVEY_CONVERT_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "survey-convert.js"
PHYSIO_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "physio.js"
EYETRACKING_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "eyetracking.js"


class TestConverterWorkflowWiring(unittest.TestCase):
    def test_converter_bootstrap_installs_page_wide_api_fallback(self):
        content = CONVERTER_BOOTSTRAP.read_text(encoding="utf-8")

        self.assertIn("import { installApiFetchFallback } from './shared/api.js';", content)
        self.assertIn("installApiFetchFallback();", content)
        self.assertIn("fetch('/api/projects/sessions/declared')", content)

    def test_shared_api_exports_fetch_installer_using_native_fetch(self):
        content = SHARED_API.read_text(encoding="utf-8")

        self.assertIn("const nativeFetch = (typeof window !== 'undefined' && typeof window.fetch === 'function')", content)
        self.assertIn("async function fetchWithApiFallbackUsing(fetchImpl, url, options = {}, fallbackMessage) {", content)
        self.assertIn("export function installApiFetchFallback() {", content)
        self.assertIn("window.__prismApiFetchFallbackInstalled", content)
        self.assertIn("window.fetch = function prismApiFetchWithFallback(url, options = {}) {", content)
        self.assertIn("return fetchWithApiFallbackUsing(", content)

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