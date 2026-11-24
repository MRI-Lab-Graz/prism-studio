import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_BUILDER_TEMPLATE = REPO_ROOT / "app" / "templates" / "recipe_builder.html"
RECIPE_BUILDER_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "recipe_builder.js"


class TestRecipeBuilderWorkflowWiring(unittest.TestCase):
    def test_recipe_builder_template_uses_shared_header_and_help_panel_macros(self):
        content = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)

    def test_recipe_builder_template_has_modality_picker_filled_from_the_project(self):
        content = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="rbModalityPicker"', content)
        self.assertNotIn('<option value="survey" selected>', content)
        self.assertNotIn('<option value="biometrics">', content)

    def test_recipe_builder_script_shows_modality_load_failure_via_modality_state(self):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("modules/recipe-builder/modality-state.js", content)
        self.assertIn("modalityListState(", content)

    def test_selected_modality_never_falls_back_to_survey(self):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("=== 'biometrics' ? 'biometrics' : 'survey'", content)
        self.assertIn("modalityOptions(", content)

    def test_recipe_builder_template_links_to_projects_page_when_no_project_loaded(
        self,
    ):
        content = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("url_for('projects.projects_page')", content)
        self.assertNotIn("url_for('projects.projects')", content)

    def test_recipe_builder_script_uses_api_fallback_for_load_and_save_requests(self):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "const recipeBuilderScriptUrl = document.currentScript?.src || window.location.href;",
            content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", content)
        self.assertIn(
            "sharedFetchWithApiFallbackPromise = import(sharedApiModuleUrl).then(({ fetchWithApiFallback }) => {",
            content,
        )
        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            content,
        )
        self.assertIn("const response = await fetchWithApiFallback(", content)
        self.assertIn(
            "'/api/recipe-builder/surveys?dataset_path=' + encodeURIComponent(path) + includeGlobal + modalityQuery",
            content,
        )
        self.assertIn(
            "'&dataset_path=' + encodeURIComponent(path) + includeGlobal + modalityQuery",
            content,
        )
        self.assertIn(
            "'&dataset_path=' + encodeURIComponent(path) + modalityQuery",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/recipe-builder/save', {",
            content,
        )
        self.assertIn("const modality = selectedModality();", content)

    def test_recipe_builder_script_ignores_stale_async_load_responses(self):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("let surveyListRequestToken = 0;", content)
        self.assertIn("let loadRequestToken = 0;", content)
        self.assertIn("if (requestToken !== surveyListRequestToken) return;", content)
        self.assertIn(
            "if (requestToken !== loadRequestToken || task !== selectedTask) return;",
            content,
        )

    def test_recipe_builder_script_resets_project_bound_selection_on_project_change(
        self,
    ):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function getCurrentProjectPath() {", content)
        self.assertIn("function resetBuilderState() {", content)
        self.assertIn("selectedTask = '';", content)
        self.assertIn(
            "surveyPicker.innerHTML = '<option value=\"\" disabled selected>— loading ' + modalityLabel + ' templates —</option>';",
            content,
        )
        self.assertIn(
            "surveyPicker.innerHTML = '<option value=\"\" disabled selected>— no project loaded —</option>';",
            content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function () {", content
        )
        self.assertIn("projectPath = getCurrentProjectPath();", content)
        self.assertIn("resetBuilderState();", content)
        self.assertIn("loadSurveyList();", content)
        self.assertIn("modalityPicker && modalityPicker.addEventListener('change', () => {", content)


    def test_run_summary_box_explains_what_happens_when_the_recipe_runs(self):
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="rbRunSummary"', template)
        self.assertIn("What happens when this recipe runs", template)

        self.assertIn("./modules/recipe-builder/missing-data.js", script)
        # The box is redrawn whenever scales or inversion change.
        for renderer in ("function renderScaleCanvas()", "function renderInversionBox()"):
            body = script[script.index(renderer) :]
            body = body[: body.index("\n    }\n")]
            self.assertIn("renderRunSummary()", body, renderer)

    def test_missing_answers_are_one_plain_choice_per_scale(self):
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        # The choice is read from and written back to the recipe fields ...
        self.assertIn("policyFromScore(rawScore)", script)
        self.assertIn("applyPolicyToScore(score,", script)
        # ... and offered in plain words.
        for label in ("Use the answered items", "Require at least", "Require all items"):
            self.assertIn(label, script)

    def test_save_message_says_what_was_saved_and_what_to_do_next(self):
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Recipe saved", script)
        self.assertIn("Analysis Outputs", script)
        # The technical path stays available, but as a detail.
        self.assertIn("_escHtml(data.path", script)


    def test_new_recipes_are_prefilled_from_the_template_but_saved_ones_are_not(self):
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="rbMetaFromTemplate"', template)
        self.assertIn("Pre-filled from the template", template)

        load = script[script.index("async function loadItemsAndRecipe") :]
        load = load[: load.index("configureItemInfoLanguageSelector(")]
        # An existing recipe keeps its own values; only a new one is pre-filled.
        existing, _, fresh = load.partition("if (recipeData.recipe) {")
        branch_existing, _, branch_new = fresh.partition("} else {")
        self.assertIn("importRecipe(recipeData.recipe)", branch_existing)
        self.assertNotIn("prefillMetadataFromTemplate(", branch_existing)
        self.assertIn("prefillMetadataFromTemplate(itemsData.template_metadata)", branch_new)


    def test_recipes_have_no_doi_field(self):
        """A recipe's DOI was never read by any output, so the builder does not offer it."""
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("rbMetaDoi", template)
        self.assertNotIn("rbMetaDoi", script)
        self.assertNotIn("DOI", script)


    def test_saving_keeps_everything_the_builder_does_not_edit(self):
        """buildRecipeJSON used to build a fresh recipe, dropping Psychometrics, Usage,
        References, Transforms.Derived and any other loaded content on save."""
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("./modules/recipe-builder/recipe-merge.js", script)
        self.assertIn("state.loadedRecipe = recipeData.recipe || null", script)

        build = script[script.index("function buildRecipeJSON()") :]
        build = build[: build.index("// ── Preview")]
        self.assertIn("buildRecipe({", build)
        self.assertIn("loaded: state.loadedRecipe", build)
        # The old from-scratch construction is gone.
        self.assertNotIn("RecipeVersion: '1.0'", build)

        # A localized Name/Description is shown as text, not "[object Object]".
        importer = script[script.index("function importRecipe(") :]
        importer = importer[: importer.index("function scoreToScale")]
        self.assertIn("metadataFieldText(s.Name)", importer)

    def test_irv_checkbox_is_wired_into_save_and_import(self):
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="rbIncludeIrv"', template)
        self.assertIn("irvItems:", script)
        importer = script[script.index("function importRecipe(") :]
        importer = importer[: importer.index("function scoreToScale")]
        self.assertIn("splitIrvScore(", importer)
        self.assertIn("rbIncludeIrv", importer)

    def test_recipe_file_import_button_posts_to_the_save_endpoint(self):
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="rbImportRecipeBtn"', template)
        self.assertIn('id="rbImportRecipeFile"', template)
        self.assertIn('accept=".json,application/json"', template)
        self.assertIn("modules/recipe-builder/recipe-file.js", script)
        handler = script[script.index("rbImportRecipeFile") :]
        self.assertIn("parseRecipeFile(", handler)
        self.assertIn("'/api/recipe-builder/save'", handler)

    def test_formula_ui_loads_katex_and_only_calls_the_two_routes(self):
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("vendor/katex/katex.min.css", template)
        self.assertIn("vendor/katex/katex.min.js", template)
        for name in ("katex.min.js", "katex.min.css", "LICENSE"):
            self.assertTrue((REPO_ROOT / "app/static/vendor/katex" / name).exists(), name)

        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/api/recipe-builder/formula-check", script)
        self.assertIn("/api/recipe-builder/formula-latex", script)
        self.assertNotIn("eval(", script)
        self.assertNotIn("new Function", script)
        self.assertIn("katex.render(", script)


    def test_inversion_box_is_foldable_with_an_accessible_toggle(self):
        template = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertRegex(
            template,
            r'<button[^>]*id="rbInversionToggle"[^>]*aria-expanded="false"',
        )
        self.assertIn('id="rbInversionBody"', template)
        self.assertIn("rbInversionToggle", script)
        self.assertIn("setInversionExpanded(state.inverted.size > 0)", script)
        self.assertIn("Hide inversion", script)
        self.assertIn("Show inversion", script)

    def test_new_scale_from_the_dialog_opens_expanded_and_scrolls_into_view(self):
        script = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")
        start = script.index("scaleNameConfirm.addEventListener('click'")
        block = script[start : script.index("scaleNameModal.hide();", start)]

        self.assertLess(
            block.index("state.expandedScaleIds.add(scale.id)"),
            block.index("renderScaleCard(scale)"),
        )
        self.assertIn("scrollIntoView", block)

if __name__ == "__main__":
    unittest.main()
