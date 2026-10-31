/** The Languages field is a pull-down plus green chips, like the project page: the options are the
 *  backend's ISO 639-1 codes (language-codes.js), the chosen ones move out of the list into chips. */
const names = new Intl.DisplayNames(['en'], { type: 'language' });

/** "de (German)"; just the code when it has no name. */
export function languageLabel(code) {
    let name;
    try { name = names.of(code); } catch { name = undefined; }
    return name && name !== code ? `${code} (${name})` : code;
}

/** [{ value, label }] for the codes in `known` that are not in `chosen`. */
export function languageOptions(known, chosen) {
    if (!known) return [];
    return [...known].filter((code) => !chosen.includes(code)).sort()
        .map((value) => ({ value, label: languageLabel(value) }));
}

/** [{ value, label }] for the DefaultLanguage pull-down: the chosen languages (plus a stored default that is not among them). */
export function defaultLanguageOptions(chosen, current) {
    const codes = current && !chosen.includes(current) ? [...chosen, current] : chosen;
    return codes.map((value) => ({ value, label: languageLabel(value) }));
}
