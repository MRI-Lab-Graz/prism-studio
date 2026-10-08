// Which export languages the selected templates (customizer groups) can offer.
// A language is only usable when every group has it, so nobody is surprised by an empty export.

export function languageChoices(groups) {
    const withLanguages = groups.map((group) => ({
        name: group.name,
        languages: group.detected_languages || ['en'],
    }));
    const languages = [...new Set(withLanguages.flatMap((group) => group.languages))].sort();
    const shared = languages.filter((lang) => withLanguages.every((group) => group.languages.includes(lang)));
    const missing = {};
    for (const lang of languages) {
        if (shared.includes(lang)) {
            continue;
        }
        missing[lang] = [...new Set(withLanguages.filter((group) => !group.languages.includes(lang)).map((group) => group.name))];
    }
    return { languages, shared, missing };
}

// The languages to export, resolved against what the templates offer: only shared languages can be
// chosen, the base language is always one of the chosen ones, and the base comes first.
export function resolveLanguages(groups, { base_language: wantedBase, languages: wanted }) {
    const choices = languageChoices(groups);
    let selected = (wanted || []).filter((lang) => choices.shared.includes(lang));
    if (!selected.length) {
        selected = choices.shared.includes(wantedBase) ? [wantedBase] : choices.shared.slice(0, 1);
    }
    if (!selected.length) {
        selected = [wantedBase];
    }
    const base = selected.includes(wantedBase) ? wantedBase : selected[0];
    return { ...choices, selected: [base, ...selected.filter((lang) => lang !== base)], base };
}

// "German (DE)" for any language code the browser knows, the bare code otherwise.
export function languageLabel(code) {
    try {
        const name = new Intl.DisplayNames(['en'], { type: 'language' }).of(code);
        return name && name.toLowerCase() !== code.toLowerCase() ? `${name} (${code.toUpperCase()})` : code.toUpperCase();
    } catch (_error) {
        return code.toUpperCase();
    }
}
