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
