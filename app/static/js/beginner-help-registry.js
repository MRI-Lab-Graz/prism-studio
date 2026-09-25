// Central beginner-help hint registry.
// Keys default to field id, but fields can override via data-help-key.
//
// Writing rule: a beginner hint must answer a question a first-time user has
// ("what is this?", "which one do I pick?", "what happens if I get it wrong?").
// Never restate the field label or the always-visible help text next to it —
// experienced users already see that, and repeating it is exactly what makes
// beginner mode feel noisy. If the visible text already answers it, add no hint.
(function registerBeginnerHelpRegistry(global) {
    const SESSION_HINT = 'A session is one measurement occasion (e.g. pre / post, or baseline / follow-up). Use the same label for everything collected at that occasion, in every converter.';
    const SESSION_LABEL_HINT = 'Letters and numbers only, without "ses-" (e.g. pre, followup, 1). Labels must match exactly across converters: "1" and "01" are two different sessions.';
    const SEPARATOR_HINT = 'If the preview shows all values squeezed into one column, your file probably uses semicolons (;), which is common for Excel exports on German/European systems.';

    const exact = {
        beginnerHelpModeToggle: 'Turn this off once you know your way around. It hides these tips on every page, and you can switch it back on any time.',
        projectName: 'Pick a short name you will still recognize later, e.g. sleep_study_2026.',
        projectPath: 'PRISM creates a new subfolder here, named after your project. Choose a location that is backed up, because the project will hold your raw data.',
        globalLibraryPath: 'Most users never change this. PRISM ships with a built-in template library. Point it elsewhere only if your lab shares its own templates.',
        globalRecipesPath: 'Recipes turn questionnaire answers into scores (sum scores, subscales). Keep the default unless your lab maintains its own recipes.',
        backendMonitoringToggle: 'Only needed for troubleshooting or bug reports. Leave it off for normal use.',
        dedicatedTerminalToggle: 'Only needed for troubleshooting. Leave it off unless someone asks you for startup logs.',
        convertSurveyFile: 'Use the raw export from your survey tool, typically one row per participant (and session). Your file is only read, never modified.',
        datasetFolder: 'The dataset root is the folder that contains dataset_description.json and the sub-* folders.',
        library_path: 'Leave empty. PRISM finds templates in your project and the global library automatically.',
        convertSeparator: SEPARATOR_HINT,
        participantsSeparator: SEPARATOR_HINT,
        convertIdMapFile: 'Use this when the survey used different codes than the rest of your study (e.g. anonymous LimeSurvey tokens). Skip it if the file already contains your participant IDs.',
        convertIdColumn: 'The column that says who answered, e.g. a participant code like P001. It becomes the sub-<label> in all output filenames.',
        convertDatasetName: 'Only needed if your file contains several questionnaires and you want to convert just one. Leave empty to convert everything PRISM recognizes.',
        convertLanguage: 'Only matters for multilingual templates: pick the language your participants actually saw.',
        convertSessionSelect: SESSION_HINT,
        convertSessionCustom: SESSION_LABEL_HINT,
        biometricsSessionSelect: SESSION_HINT,
        biometricsSessionCustom: SESSION_LABEL_HINT,
        biometricsDataFile: 'Expected shape: one row per participant (and session), one column per measure, e.g. height, weight, grip strength.',
        physioBatchFiles: 'Use the raw recordings as they came off the Varioport device. Your source files are only read, never modified.',
        physioBatchFolder: 'Handy when all recordings sit in one folder (e.g. sourcedata/physio). Only compatible files are picked up.',
        eyetrackingBatchFiles: '.edf is the raw EyeLink format. .tsv / .tsv.gz are already-exported sample tables. Use whichever your lab has.',
        renamerFiles: 'Nothing is renamed until you confirm. You will see a preview of every new filename first.',
        organizeFiles: 'Your originals stay untouched because PRISM copies them. Filenames should already follow the sub-XX_... pattern. If they don\'t, use the Renamer first.',
        wideLongFile: 'Wide = one row per participant, time points in separate columns (score_t1, score_t2). Long = one row per participant per time point. Mixed models in R/Python usually want long.',
        envDataFile: 'PRISM looks up weather, air quality, etc. for the time and place of each row. The file needs at least a participant column and a date/time column.',
        envSessionOverride: 'Must match the session label used in your other data exactly: "pre" is not "Pre", and "1" is not "01".',
        envLocationQuery: 'Usually your lab or testing site, i.e. where participants were actually measured.',
        envLat: 'Tip: use the location search above instead of typing coordinates by hand.',
        convertSessionColumnOverride: 'Only needed if one file contains several time points. Otherwise leave it on Auto-detect.',
        convertRunColumnOverride: 'A run is a repetition within the same session (e.g. the same questionnaire filled in twice in one visit). Most studies have no runs, so leave it on Auto-detect.',
        templateImportInput: 'Quickest way to start: export your questionnaire from LimeSurvey or an Excel codebook, import it here, then fill in what is missing.',
        jsonFileInput: 'JSON sidecars are the small .json files next to data files that describe them (units, labels, device). Editing them changes metadata, never your data.',
        derivFormat: 'SPSS users: .sav (value labels included). R, Python, or Jamovi: CSV. Excel is best for a quick look.',
        derivSurvey: 'Comma-separated recipe names, e.g. phq9, gad7.',
        derivIdLength: 'Longer codes make accidental collisions between participants less likely. The default of 8 is plenty for most studies.',
        rbMetaName: 'The full instrument name as cited in papers, e.g. Patient Health Questionnaire-9.',
        rbMetaDesc: 'One sentence on what the scale measures, e.g. "Depressive symptoms over the last two weeks."',
        rbMetaDoi: 'DOI of the original validation paper, which makes the recipe citable.',
        lsVersionSelect: 'Not sure? LimeSurvey shows its version in the admin area footer.',
        lsWelcomeText: 'Shown on the first page. It usually covers the study purpose, duration, and that participation is voluntary. The templates above are a good starting point.',
        lsEndText: 'Shown after submitting. Thank participants and give a contact for questions.',
        openmindsEnableExport: 'Only needed if a repository or collaborator asks for openMINDS metadata (e.g. EBRAINS). Otherwise leave it off.'
    };

    global.PRISM_BEGINNER_HELP_REGISTRY = { exact };
})(window);
