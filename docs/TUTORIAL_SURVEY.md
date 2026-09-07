# Author a Survey

Authoring survey templates is the part of PRISM Studio most people spend the
most time in — it's where a paper questionnaire or an existing instrument
becomes the structured template that drives import, scoring, and export
everywhere else. This series stands on its own: no [Getting Started
](TUTORIAL_BEGINNER.md) tutorial is required first.

## Who this is for

- PRISM Studio installed and launchable — see [Installation
  ](INSTALLATION.md) if you haven't done this yet.
- No LimeSurvey instance required — Chapter 6 exports a `.lss` file but
  never needs a live LimeSurvey server to do it.
- No prior PRISM knowledge assumed.

## The scenario

Across this tutorial series you'll build a fictional exercise-recovery
study called **Recovery Check-In**. It has a **Full** version — a 10-item
evening, post-training-session check-in covering mood, soreness, sleep
quality, motivation, stress, fatigue, appetite, hydration, and satisfaction
(all 5-point Likert items), plus a pain intensity item on a 0–100 VAS
(visual analog scale) — and a **Short** version, a 5-item same-day quick
follow-up (mood, soreness, pain intensity, fatigue, sleep quality) that's a
true subset of the Full item set. Later chapters make the study bilingual,
English and German.

**Time:** ~2h45m for all seven chapters. **Outcome:** a bilingual,
two-version, schema-valid `survey-recovery.json` template that also exports
cleanly to LimeSurvey.

<div class="prism-chapter-grid">
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_1_CONCEPTS.html">
    <span class="prism-chapter-icon">1</span>
    <span class="prism-chapter-title">Survey Concepts You Need First</span>
    <span class="prism-chapter-outcome">A clear grasp of official vs. project-local templates and a fresh scratch project</span>
    <span class="prism-chapter-time">~15 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.html">
    <span class="prism-chapter-icon">2</span>
    <span class="prism-chapter-title">Prepare a New Questionnaire in Excel</span>
    <span class="prism-chapter-outcome">A validated, saved <code>survey-recovery.json</code> with all 10 Full version items, English only</span>
    <span class="prism-chapter-time">~30 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_3_TEMPLATE_EDITOR.html">
    <span class="prism-chapter-icon">3</span>
    <span class="prism-chapter-title">Edit and Refine in the Template Editor</span>
    <span class="prism-chapter-outcome">Comfortable editing directly in the browser — single-item, bulk, and paper-pencil export</span>
    <span class="prism-chapter-time">~25 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_4_LANGUAGES_SCALES.html">
    <span class="prism-chapter-icon">4</span>
    <span class="prism-chapter-title">Languages and Scales</span>
    <span class="prism-chapter-outcome">A bilingual EN/DE template with both a Likert and a VAS scale correctly represented</span>
    <span class="prism-chapter-time">~25 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_5_VARIANTS.html">
    <span class="prism-chapter-icon">5</span>
    <span class="prism-chapter-title">Multiple Versions (Variants)</span>
    <span class="prism-chapter-outcome">One template that serves both the Full and Short forms, without maintaining two files</span>
    <span class="prism-chapter-time">~25 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.html">
    <span class="prism-chapter-icon">6</span>
    <span class="prism-chapter-title">Export to LimeSurvey</span>
    <span class="prism-chapter-outcome">A real <code>.lss</code> file, ready to import, with per-question presentation configured</span>
    <span class="prism-chapter-time">~30 min</span>
  </a>
  <a class="prism-chapter-card" href="TUTORIAL_SURVEY_7_VALIDATION.html">
    <span class="prism-chapter-icon">7</span>
    <span class="prism-chapter-title">Validating Your Template</span>
    <span class="prism-chapter-outcome">A clear picture of what "validated" means — schema correctness versus translation completeness</span>
    <span class="prism-chapter-time">~15 min</span>
  </a>
</div>

## What's next

Once you've completed all seven chapters:

- [Recipes](RECIPES.md) and
  [Prepare a Recipe](TUTORIAL_BEGINNER_4_RECIPE.md) — score the responses
  once you actually have them
- [Converter → Survey](studio/converter_survey.md) — import real response
  data against this template
- [LimeSurvey Integration](LIMESURVEY_INTEGRATION.md) — the full round trip:
  import the `.lss`, collect data, bring it back into PRISM
- [Validator](studio/validator.md) — dataset-level validation, once you have
  actual response data to check

```{toctree}
:maxdepth: 1
:hidden:

TUTORIAL_SURVEY_1_CONCEPTS
TUTORIAL_SURVEY_2_EXCEL_TEMPLATE
TUTORIAL_SURVEY_3_TEMPLATE_EDITOR
TUTORIAL_SURVEY_4_LANGUAGES_SCALES
TUTORIAL_SURVEY_5_VARIANTS
TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT
TUTORIAL_SURVEY_7_VALIDATION
```
