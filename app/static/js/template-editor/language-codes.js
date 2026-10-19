/** Language codes in templates are ISO 639-1 ("en") with an optional region ("en-US"); the list of
 *  codes comes from the backend (/api/template-editor/language-codes), the one place that has it. */
const FORMAT = /^([a-z]{2})(-[A-Z]{2})?$/;

/** '' when `raw` is a usable code, otherwise the message to show. `known` is the backend's list;
 *  without it (not loaded yet) only the format is checked. */
export function languageCodeProblem(raw, known) {
    const code = String(raw ?? '').trim();
    const match = FORMAT.exec(code);
    if (!match) return `"${code}" is not a language code. Use two lowercase letters, optionally with a region, e.g. "en" or "de-AT".`;
    if (known && !known.has(match[1])) return `"${match[1]}" is not an ISO 639-1 language code (e.g. "en", "de", "fr").`;
    return '';
}
