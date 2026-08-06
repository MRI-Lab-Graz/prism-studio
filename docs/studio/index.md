# Studio Guide

One page per PRISM Studio screen, in the order most people encounter them. Each page
covers: what the screen does, the exact fields/buttons you'll see, what gets written
and where, and common failures.

## Getting started

<div class="prism-chapter-grid prism-chapter-grid--blue">
  <a class="prism-chapter-card" href="home.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9"/></svg></span>
    <span class="prism-chapter-title">Home</span>
    <span class="prism-chapter-outcome">The landing screen and overall map of PRISM Studio</span>
  </a>
  <a class="prism-chapter-card" href="projects.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a1 1 0 0 1 1-1h4.5l1.5 2H20a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z"/></svg></span>
    <span class="prism-chapter-title">Projects</span>
    <span class="prism-chapter-outcome">Create, open, and re-open PRISM projects</span>
  </a>
  <a class="prism-chapter-card" href="file_management.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="M3 12l9 5 9-5"/><path d="M3 16l9 5 9-5"/></svg></span>
    <span class="prism-chapter-title">File Management</span>
    <span class="prism-chapter-outcome">Bulk rename, reorganize, convert, and delete files in a project</span>
  </a>
</div>

## Import & convert

<div class="prism-chapter-grid prism-chapter-grid--teal">
  <a class="prism-chapter-card" href="converter.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3 21 7l-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 21 3 17l4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg></span>
    <span class="prism-chapter-title">Converter</span>
    <span class="prism-chapter-outcome">Where external data enters a PRISM project</span>
  </a>
  <a class="prism-chapter-card" href="converter_survey.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 3h6v3H9z"/><path d="M9 10h6"/><path d="M9 13h6"/><path d="M9 16h4"/></svg></span>
    <span class="prism-chapter-title">Survey Import</span>
    <span class="prism-chapter-outcome">Questionnaire data from LimeSurvey exports, spreadsheets, SPSS/R</span>
  </a>
  <a class="prism-chapter-card" href="converter_participants.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2c2.3.3 4.5 2 4.5 4.8"/></svg></span>
    <span class="prism-chapter-title">Participants / Sociodemographics</span>
    <span class="prism-chapter-outcome">Produces <code>participants.tsv</code> from a source file</span>
  </a>
  <a class="prism-chapter-card" href="converter_biometrics.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 8.5a4.5 4.5 0 0 0-8.5-2 4.5 4.5 0 0 0-8.5 2c0 5 8.5 10.5 8.5 10.5s8.5-5.5 8.5-10.5Z"/><path d="M4 12h3l1.5-3 2.5 5 1.5-2.5h5"/></svg></span>
    <span class="prism-chapter-title">Biometrics</span>
    <span class="prism-chapter-outcome">Grip strength, balance tests, and other physiological measures</span>
  </a>
  <a class="prism-chapter-card" href="converter_environment.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 18a3.5 3.5 0 0 1-.7-6.93A5 5 0 0 1 15 8a3.5 3.5 0 0 1 1.2 6.98"/><path d="M6.5 18h9.8"/></svg></span>
    <span class="prism-chapter-title">Environment</span>
    <span class="prism-chapter-outcome">Timestamped contextual data alongside a study</span>
  </a>
  <a class="prism-chapter-card" href="converter_eyetracking.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg></span>
    <span class="prism-chapter-title">Eyetracking</span>
    <span class="prism-chapter-outcome">Batch-converts SR Research EyeLink recordings to BIDS-style eyetracking</span>
  </a>
  <a class="prism-chapter-card" href="converter_physio.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l2-7 4 14 2-7h6"/></svg></span>
    <span class="prism-chapter-title">Physio</span>
    <span class="prism-chapter-outcome">Batch-converts Varioport physiological recordings</span>
  </a>
</div>

## Edit & build

<div class="prism-chapter-grid prism-chapter-grid--purple">
  <a class="prism-chapter-card" href="json_editor.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4 4 12l5 8"/><path d="M15 4l5 8-5 8"/></svg></span>
    <span class="prism-chapter-title">JSON Editor</span>
    <span class="prism-chapter-outcome">Edit project-level JSON files directly, e.g. <code>dataset_description.json</code></span>
  </a>
  <a class="prism-chapter-card" href="template_editor.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="5" rx="1"/><rect x="13" y="10" width="8" height="11" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/></svg></span>
    <span class="prism-chapter-title">Template Editor</span>
    <span class="prism-chapter-outcome">Create, edit, validate, and export survey/instrument templates</span>
  </a>
  <a class="prism-chapter-card" href="survey_generator.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4"/><path d="M7 9l5-5 5 5"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></svg></span>
    <span class="prism-chapter-title">Survey Export</span>
    <span class="prism-chapter-outcome">Export templates from your library as a ready-to-run survey</span>
  </a>
  <a class="prism-chapter-card" href="survey_customizer.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h6"/><path d="M16 7h4"/><circle cx="13" cy="7" r="2.2"/><path d="M4 13h2"/><path d="M12 13h8"/><circle cx="9" cy="13" r="2.2"/><path d="M4 19h10"/><path d="M20 19h0"/><circle cx="17" cy="19" r="2.2"/></svg></span>
    <span class="prism-chapter-title">Survey Customizer</span>
    <span class="prism-chapter-outcome">Group, order, and configure template presentation before export</span>
  </a>
  <a class="prism-chapter-card" href="recipe_builder.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6.5L4.5 19a1.5 1.5 0 0 0 1.3 2.3h12.4a1.5 1.5 0 0 0 1.3-2.3L14 9.5V3"/><path d="M7 15h10"/></svg></span>
    <span class="prism-chapter-title">Recipe Builder</span>
    <span class="prism-chapter-outcome">Build scoring recipes: reverse-coding, subscales, composite scores</span>
  </a>
</div>

## Validate & publish

<div class="prism-chapter-grid prism-chapter-grid--green">
  <a class="prism-chapter-card" href="validator.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3Z"/><path d="M9 12l2 2 4-4"/></svg></span>
    <span class="prism-chapter-title">Validator</span>
    <span class="prism-chapter-outcome">The web equivalent of <code>prism-validator</code> on the CLI</span>
  </a>
  <a class="prism-chapter-card" href="export.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 13v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6"/><path d="M12 14V3"/><path d="M8 7l4-4 4 4"/></svg></span>
    <span class="prism-chapter-title">Share / Export</span>
    <span class="prism-chapter-outcome">Where a project leaves Studio — anonymized ZIP, plain export, or archive</span>
  </a>
  <a class="prism-chapter-card" href="specifications.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h6"/></svg></span>
    <span class="prism-chapter-title">Specifications</span>
    <span class="prism-chapter-outcome">How PRISM organizes a project across Core and extension tiers</span>
  </a>
</div>

## Tools

<div class="prism-chapter-grid prism-chapter-grid--amber">
  <a class="prism-chapter-card" href="app_runner.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M10 8.5 16 12l-6 3.5V8.5Z"/></svg></span>
    <span class="prism-chapter-title">PRISM App Runner</span>
    <span class="prism-chapter-outcome">Run containerized BIDS Apps pipelines against your project</span>
  </a>
</div>

All PRISM Studio screens are covered here now. The older top-level pages this section
replaces (`CONVERTER.md`, `STUDIO_OVERVIEW.md`, `TOOLS.md`, `WEB_INTERFACE.md`,
`SPECIFICATIONS.md`) are being retired — see the main navigation for what's still
live.

```{toctree}
:maxdepth: 1
:hidden:

home
projects
file_management
converter
converter_survey
converter_participants
converter_biometrics
converter_environment
converter_eyetracking
converter_physio
validator
json_editor
template_editor
survey_generator
survey_customizer
recipe_builder
export
specifications
app_runner
```
