/**
 * A template whose texts have no language yet (a Pavlovia survey file carries none): the editor asks
 * which language the texts are in, then keys every text under it.
 */

const LANG_CODE_RE = /^[a-z]{2}(-[A-Z]{2})?$/;
const NON_ITEM_KEYS = new Set(['Technical', 'Study', 'Metadata', 'I18n', 'LimeSurvey', 'Scoring', 'Normative', '_aliases', '_reverse_aliases']);
const STUDY_TEXT_FIELDS = ['OriginalName', 'Description', 'Instructions', 'License'];

const itemKeys = (template) => Object.keys(template).filter((key) => !NON_ITEM_KEYS.has(key));

export function needsPrimaryLanguage(template) {
    return !!template && typeof template === 'object'
        && itemKeys(template).length > 0
        && !(template.Technical && template.Technical.Language);
}

function keyLevels(levels, lang) {
    if (!levels || typeof levels !== 'object') {
        return;
    }
    for (const [code, text] of Object.entries(levels)) {
        if (typeof text === 'string') {
            levels[code] = { [lang]: text };
        }
    }
}

export function applyPrimaryLanguage(template, lang) {
    if (!LANG_CODE_RE.test(lang)) {
        throw new Error('Not a language code: use a code like "de" or "de-AT".');
    }
    template.Technical = { ...(template.Technical || {}), Language: lang };
    const study = template.Study || {};
    for (const field of STUDY_TEXT_FIELDS) {
        if (typeof study[field] === 'string') {
            study[field] = { [lang]: study[field] };
        }
    }
    for (const key of itemKeys(template)) {
        const item = template[key];
        if (!item || typeof item !== 'object') {
            continue;
        }
        if (typeof item.Description === 'string') {
            item.Description = { [lang]: item.Description };
        }
        keyLevels(item.Levels, lang);
    }
    return template;
}
