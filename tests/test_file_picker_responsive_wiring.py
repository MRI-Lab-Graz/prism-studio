import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"
UI_MACROS_TEMPLATE = REPO_ROOT / "app" / "templates" / "includes" / "ui" / "macros.html"
CONVERTER_PARTICIPANTS_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_participants.html"
CONVERTER_SURVEY_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_survey.html"
CONVERTER_BIOMETRICS_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_biometrics.html"
CONVERTER_ENVIRONMENT_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_environment.html"
CONVERTER_PHYSIO_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_physio.html"
CONVERTER_EYETRACKING_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_eyetracking.html"
VALIDATOR_TEMPLATE = REPO_ROOT / "app" / "templates" / "index.html"
PROJECT_SETTINGS_TEMPLATE = REPO_ROOT / "app" / "templates" / "includes" / "projects" / "settings_section.html"
PROJECT_EXPORT_TEMPLATE = REPO_ROOT / "app" / "templates" / "includes" / "projects" / "export_section.html"
PRISM_APP_RUNNER_TEMPLATE = REPO_ROOT / "app" / "templates" / "prism_app_runner.html"
FILE_MANAGEMENT_TEMPLATE = REPO_ROOT / "app" / "templates" / "file_management.html"


class TestFilePickerResponsiveWiring(unittest.TestCase):
    def test_base_template_defines_shared_responsive_picker_styles(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(".studio-picker-group > .form-control,", content)
        self.assertIn(".studio-picker-group > .btn,", content)
        self.assertIn(".studio-picker-group > .form-control[readonly] {", content)
        self.assertIn(".studio-picker-group {", content)
        self.assertIn("gap: 0.65rem;", content)
        self.assertIn("align-items: center;", content)
        self.assertIn(".studio-picker-group > .studio-picker-trigger {", content)
        self.assertIn(".studio-picker-group > .studio-picker-clear {", content)
        self.assertIn("@media (max-width: 575.98px) {", content)
        self.assertIn("border-radius: var(--bs-border-radius) !important;", content)

    def test_shared_macros_apply_picker_group_classes(self):
        content = UI_MACROS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('<div class="studio-file-picker {{ wrapper_classes }}">', content)
        self.assertIn('<div class="input-group studio-picker-group">', content)
        self.assertIn('<div class="studio-path-picker {{ wrapper_classes }}">', content)
        self.assertIn('class="btn btn-outline-secondary studio-picker-clear', content)
        self.assertIn('class="btn btn-outline-secondary studio-picker-trigger"', content)

    def test_direct_picker_templates_use_shared_picker_group_class(self):
        templates = {
            CONVERTER_PARTICIPANTS_TEMPLATE: ["participantsChooseFileBtn"],
            CONVERTER_SURVEY_TEMPLATE: ["convertExcelFile", "convertIdMapFile"],
            CONVERTER_BIOMETRICS_TEMPLATE: ["biometricsDataFile"],
            CONVERTER_ENVIRONMENT_TEMPLATE: ["envDataFile"],
            CONVERTER_PHYSIO_TEMPLATE: ["physioBatchFiles", "physioBatchFolder"],
            CONVERTER_EYETRACKING_TEMPLATE: ["eyetrackingBatchFiles"],
            VALIDATOR_TEMPLATE: ["selectedFolderPath", "library_path"],
            PROJECT_SETTINGS_TEMPLATE: ["globalLibraryPath", "globalRecipesPath"],
            PROJECT_EXPORT_TEMPLATE: ["exportOutputFolder"],
            PRISM_APP_RUNNER_TEMPLATE: ["runTemplateflowDir", "runFsLicense", "runContainerPath", "remoteIdentityFile", "remoteKnownHostsFile"],
            FILE_MANAGEMENT_TEMPLATE: ["wideLongPickFileBtn"],
        }

        for template_path, markers in templates.items():
            with self.subTest(template=template_path.name):
                content = template_path.read_text(encoding="utf-8")
                self.assertIn("studio-picker-group", content)
                for marker in markers:
                    self.assertIn(marker, content)


if __name__ == "__main__":
    unittest.main()