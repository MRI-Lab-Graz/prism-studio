import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_MANAGEMENT_TEMPLATE = REPO_ROOT / "app" / "templates" / "file_management.html"
FILE_MANAGEMENT_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "file_management.js"


class TestFileManagementWorkflowWiring(unittest.TestCase):
    def test_file_management_script_uses_api_fallback_for_all_tool_requests(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn(
            "await fetchWithApiFallback('/api/file-management/raw-peek', { method: 'POST', body: formData });",
            content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/file-management/wide-to-long-preview', {",
            content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/file-management/wide-to-long', {", content
        )
        self.assertIn("await fetchWithApiFallback('/api/batch-convert', {", content)
        self.assertIn("await fetchWithApiFallback('/api/physio-rename', {", content)
        self.assertIn(
            "await fetchWithApiFallback('/api/file-management/subject-rewrite', {",
            content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/file-management/entity-rewrite', {",
            content,
        )
        self.assertNotIn(
            "await fetch('/api/file-management/wide-to-long-preview'", content
        )
        self.assertNotIn("await fetch('/api/file-management/wide-to-long'", content)

    def test_file_management_script_guards_unsupported_flat_project_root_copy(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function renamerCanCopyToProject() {", content)
        self.assertIn(
            "Flat output can be downloaded or copied to rawdata/sourcedata. Enable folders to copy into the PRISM root.",
            content,
        )
        self.assertIn("organizeFlatStructure.disabled = true;", content)

    def test_file_management_copy_actions_follow_active_project_state(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function getCurrentProjectPath() {", content)
        self.assertIn(
            "if (wideLongConvertBtn) wideLongConvertBtn.disabled = !hasFile || !hasCurrentProject;",
            content,
        )
        self.assertIn(
            "if (organizeCopyBtn) organizeCopyBtn.disabled = !hasFiles || !hasCurrentProject;",
            content,
        )
        self.assertIn(
            "if (renamerCopyBtn) renamerCopyBtn.disabled = disabled || !renamerCanCopyToProject() || !hasCurrentProject;",
            content,
        )
        self.assertIn("formData.append('project_path', currentProjectPath);", content)
        self.assertIn(
            "window.addEventListener('prism-project-changed', () => {", content
        )
        self.assertIn(
            "No active project selected. Open a project before saving converted files.",
            content,
        )
        self.assertIn(
            "No active project selected. Open a project before copying files.", content
        )
        self.assertIn(
            "No active project selected. Open a project before copying renamed files.",
            content,
        )

    def test_file_management_sequential_renamer_copy_locks_project_path_per_batch(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("const copyProjectPath = getCurrentProjectPath();", content)
        self.assertIn("projectPath: copyProjectPath,", content)
        self.assertIn(
            "const currentProjectPath = String(opts.projectPath || getCurrentProjectPath()).trim();",
            content,
        )

    def test_file_management_template_defaults_flat_toggle_to_supported_destinations(
        self,
    ):
        content = FILE_MANAGEMENT_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="organizeFlatStructure" disabled', content)
        self.assertIn(
            "Project root keeps PRISM folders; use rawdata or sourcedata for flat copies.",
            content,
        )

    def test_file_management_template_exposes_server_file_pick_buttons(self):
        content = FILE_MANAGEMENT_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="renamerBrowseServerFileBtn"', content)
        self.assertIn('id="renamerClearServerSelectionBtn"', content)
        self.assertIn('id="organizeBrowseServerFileBtn"', content)
        self.assertIn('id="organizeClearServerFilesBtn"', content)

    def test_file_management_script_submits_server_file_paths(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("formData.append('server_file_paths', entry.sourcePath);", content)
        self.assertIn("formData.append('server_file_paths', serverFilePath);", content)
        self.assertIn("const organizeBrowseServerFileBtn = document.getElementById('organizeBrowseServerFileBtn');", content)
        self.assertIn("const renamerBrowseServerFileBtn = document.getElementById('renamerBrowseServerFileBtn');", content)

    def test_file_management_subject_rewrite_supports_preview_and_example_rule(self):
        template = FILE_MANAGEMENT_TEMPLATE.read_text(encoding="utf-8")
        script = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        renamer_panel_start = template.find('id="fm-renamer-panel"')
        organizer_panel_start = template.find('id="fm-organizer-panel"')
        rewrite_btn_position = template.find('id="repoSubjectRewriteBtn"')

        self.assertNotEqual(renamer_panel_start, -1)
        self.assertNotEqual(organizer_panel_start, -1)
        self.assertNotEqual(rewrite_btn_position, -1)
        self.assertGreater(rewrite_btn_position, renamer_panel_start)
        self.assertLess(rewrite_btn_position, organizer_panel_start)
        self.assertIn('id="repoSubjectRewriteBtn"', template)
        self.assertIn('id="repoSubjectRewritePreviewBtn"', template)
        self.assertIn('id="repoSubjectRewriteExample"', template)
        self.assertIn('id="repoSubjectRewriteKeep"', template)
        self.assertIn('id="repoSubjectRewriteAllowMultiple"', template)
        self.assertNotIn('id="repoSubjectRewriteAnotherExampleBtn"', template)
        self.assertIn('Preview is required before Apply.', template)
        self.assertNotIn('id="repoSubjectRewriteMode"', template)
        self.assertIn(
            "const repoSubjectRewriteAllowMultiple = document.getElementById('repoSubjectRewriteAllowMultiple');",
            script,
        )
        self.assertIn("runRepoSubjectRewrite('preview')", script)
        self.assertIn("action: 'examples'", script)
        self.assertIn("runRepoSubjectRewrite('apply')", script)
        self.assertIn("mode: 'example_keep'", script)
        self.assertIn("allow_multiple_sources: allowMultipleSources,", script)
        self.assertIn("Run Preview first, then apply.", script)
        self.assertIn("Many-to-one mode is enabled", script)
        self.assertIn("showing first ${mappingPreviewLimit} of ${mappingTotal} entries.", script)
        self.assertIn("payload.subject_token_sources", script)
        self.assertIn("Conflict sources (sample paths):", script)
        self.assertIn("loadRepoSubjectExamples();", script)

    def test_file_management_entity_rewrite_supports_modality_part_and_actions(self):
        template = FILE_MANAGEMENT_TEMPLATE.read_text(encoding="utf-8")
        script = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="repoEntityRewriteModality"', template)
        self.assertIn('id="repoEntityRewritePart"', template)
        self.assertIn('id="repoEntityRewriteCurrentValue"', template)
        self.assertIn('id="repoEntityRewriteCurrentValueSelect"', template)
        self.assertIn('id="repoEntityRewriteActionRename"', template)
        self.assertIn('id="repoEntityRewriteActionDelete"', template)
        self.assertIn('id="repoEntityRewriteValue"', template)
        self.assertIn('id="repoEntityRewritePreviewBtn"', template)
        self.assertIn('id="repoEntityRewriteBtn"', template)
        self.assertIn('Preview is required before Apply.', template)
        self.assertIn("runRepoEntityRewrite('preview')", script)
        self.assertIn("runRepoEntityRewrite('apply')", script)
        self.assertIn("action: 'options'", script)
        self.assertIn("const rawEntityValues = payload.entity_values", script)
        self.assertIn("updateRepoEntityCurrentValueDisplay();", script)
        self.assertIn("const repoEntityRewriteCurrentValueSelect = document.getElementById('repoEntityRewriteCurrentValueSelect');", script)
        self.assertIn("const selectedCurrentValue = getRepoEntitySelectedCurrentValue();", script)
        self.assertIn("current_value: selectedCurrentValue,", script)
        self.assertIn("operation: selectedOperation,", script)
        self.assertIn("replacement: selectedOperation === 'rename' ? selectedValue : '',", script)
        self.assertIn("loadRepoEntityRewriteOptions();", script)


if __name__ == "__main__":
    unittest.main()
