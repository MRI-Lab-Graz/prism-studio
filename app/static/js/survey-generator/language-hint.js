// Why a template is greyed out in the Survey Generator list, and what to change to use it.
// A template needs every ticked export language, so a DE-only one is unusable while EN is ticked.

export function missingLanguages(fileLangs, selectedExportLanguages) {
    return selectedExportLanguages.filter((lang) => !fileLangs.includes(lang));
}

export function languageHint(fileLangs, selectedExportLanguages, baseLanguage) {
    const missing = missingLanguages(fileLangs, selectedExportLanguages);
    if (missing.length === 0) {
        return '';
    }
    const upper = (langs, separator) => langs.map((lang) => lang.toUpperCase()).join(separator);
    const untick = `untick ${upper(missing, ', ')}`;
    const only = `Only in ${upper(fileLangs, '/')}`;
    return fileLangs.includes(baseLanguage)
        ? `${only}: ${untick} to use it.`
        : `${only}: set Base Language to ${fileLangs[0].toUpperCase()} and ${untick} to use it.`;
}
