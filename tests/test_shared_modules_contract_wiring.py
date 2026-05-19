import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_API_MODULE = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
SHARED_PROJECT_STATE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "shared" / "project-state.js"
)
SHARED_JOB_POLLING_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "shared" / "job-polling.js"
)


class TestSharedModulesContractWiring(unittest.TestCase):
    def test_shared_api_module_keeps_fallback_and_credentials_contract(self):
        content = SHARED_API_MODULE.read_text(encoding="utf-8")

        self.assertIn("function getFallbackApiOrigin() {", content)
        self.assertIn("const configuredOrigin = (window.PRISM_API_ORIGIN || '').trim();", content)
        self.assertIn("const currentOrigin = (window.location && typeof window.location.origin === 'string')", content)
        self.assertIn("if ((protocol === 'http:' || protocol === 'https:') && currentOrigin && currentOrigin !== 'null') {", content)
        self.assertIn("return 'http://127.0.0.1:5001';", content)
        self.assertIn("function canRetryApiWithFallback(url) {", content)
        self.assertIn("url.startsWith('/api/') || url.startsWith('/editor/api/')", content)
        self.assertIn("function canRetryRelativePathWithFallback(url) {", content)
        self.assertIn("return isRelativePathRequest && protocol !== 'http:' && protocol !== 'https:';", content)
        self.assertIn("function normalizeFetchOptionsForRuntime(url, options = {}) {", content)
        self.assertIn("return { ...options, credentials: 'include' };", content)
        self.assertIn("if (window.__prismApiFetchFallbackInstalled) {", content)
        self.assertIn("window.__prismApiFetchFallbackInstalled = true;", content)

    def test_shared_project_state_module_keeps_store_then_global_fallback_chain(self):
        content = SHARED_PROJECT_STATE_MODULE.read_text(encoding="utf-8")

        self.assertIn("export function getProjectStateStore() {", content)
        self.assertIn("window.prismProjectStateStore && typeof window.prismProjectStateStore.getState === 'function'", content)
        self.assertIn("export function getProjectStateSnapshot() {", content)
        self.assertIn("if (typeof window.getCurrentProjectState === 'function') {", content)
        self.assertIn("path: normalizeStateValue(window.currentProjectPath)", content)
        self.assertIn("icon: normalizeStateValue(window.currentProjectIcon)", content)
        self.assertIn("export function resolveCurrentProjectIcon() {", content)
        self.assertIn("export function setProjectStateSnapshot(path, name, icon = '') {", content)
        self.assertIn("window.currentProjectIcon = nextState.icon;", content)

    def test_shared_job_polling_module_keeps_abort_retry_and_timeout_bounds(self):
        content = SHARED_JOB_POLLING_MODULE.read_text(encoding="utf-8")

        self.assertIn("function createAbortError(message) {", content)
        self.assertIn("new DOMException(message, 'AbortError')", content)
        self.assertIn("const error = new Error(message);", content)
        self.assertIn("if (Date.now() - startedAt > timeoutMs) {", content)
        self.assertIn("maxConsecutiveErrors = 4", content)
        self.assertIn("if (consecutiveErrors >= maxConsecutiveErrors) {", content)
        self.assertIn("throw new Error(statusFailureMessage);", content)
        self.assertIn("if (!isDone(statusData)) {", content)
        self.assertIn("if (!isSuccess(statusData)) {", content)


if __name__ == "__main__":
    unittest.main()
