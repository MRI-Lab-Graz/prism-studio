/**
 * Read a finished PRISM template (.json) for the Template Editor's import.
 * Anything that is not a plausible PRISM template gets a plain message; deeper
 * problems are left to the editor's own validation after import.
 */

export function parsePrismTemplateJson(text, modality) {
    let data;
    try {
        data = JSON.parse(String(text).replace(/^﻿/, ''));
    } catch (_error) {
        throw new Error('This file is not valid JSON.');
    }

    if (!data || typeof data !== 'object' || Array.isArray(data)) {
        throw new Error('This JSON is not a PRISM template (expected an object with a Study block).');
    }

    const study = data.Study;
    if (!study || typeof study !== 'object' || Array.isArray(study)) {
        throw new Error('This JSON is not a PRISM template (no Study block).');
    }

    if (study.BiometricName && !study.TaskName && modality === 'survey') {
        throw new Error('This looks like a biometrics template: switch Modality to biometrics and import it again.');
    }
    if (study.TaskName && !study.BiometricName && modality === 'biometrics') {
        throw new Error('This looks like a survey template: switch Modality to survey and import it again.');
    }

    return data;
}

// A Pavlovia survey is SurveyJS JSON (pages/elements), not a PRISM template.
export function isPavloviaSurvey(text) {
    try {
        const data = JSON.parse(String(text).replace(/^\ufeff/, ''));
        return !!data && !Array.isArray(data) && (Array.isArray(data.pages) || Array.isArray(data.elements));
    } catch (_error) {
        return false;
    }
}
