// Why a template is greyed out in the Survey Generator list, and what to change to use it.
// A template is usable when it has the Base Language; export languages are chosen later,
// in Customize & Export.

export function languageHint(fileLangs, baseLanguage) {
    if (fileLangs.includes(baseLanguage)) {
        return '';
    }
    const upper = fileLangs.map((lang) => lang.toUpperCase());
    return `Only in ${upper.join('/')}: set Base Language to ${upper[0]} to use it.`;
}
