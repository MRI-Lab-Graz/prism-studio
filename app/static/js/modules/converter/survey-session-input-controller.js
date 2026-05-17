import { getSessionInputValue } from './session-picker.js';

export function createSurveySessionInputController({
    convertSessionSelect = null,
    convertSessionCustom = null,
    biometricsSessionSelect = null,
    biometricsSessionCustom = null,
} = {}) {
    function getSessionValue(selectEl, customEl) {
        return getSessionInputValue(selectEl, customEl);
    }

    function getSurveySessionValue() {
        return getSessionValue(convertSessionSelect, convertSessionCustom);
    }

    function getBiometricsSessionValue() {
        return getSessionValue(biometricsSessionSelect, biometricsSessionCustom);
    }

    function populateSurveySessionPickerFromDetected(detectedSessions) {
        if (!convertSessionSelect || !Array.isArray(detectedSessions) || detectedSessions.length === 0) {
            return false;
        }

        const normalizedSessions = [...new Set(
            detectedSessions
                .map((value) => String(value || '').trim())
                .filter(Boolean)
        )];
        if (normalizedSessions.length === 0) {
            return false;
        }

        while (convertSessionSelect.options.length > 1) {
            convertSessionSelect.remove(1);
        }

        const allOpt = document.createElement('option');
        allOpt.value = 'all';
        allOpt.textContent = '✓ All sessions';
        convertSessionSelect.appendChild(allOpt);

        normalizedSessions.forEach((ses) => {
            const opt = document.createElement('option');
            opt.value = ses;
            opt.textContent = ses;
            convertSessionSelect.appendChild(opt);
        });

        if (!getSurveySessionValue()) {
            convertSessionSelect.value = normalizedSessions.length === 1 ? normalizedSessions[0] : 'all';
        }
        if (convertSessionCustom) {
            convertSessionCustom.value = '';
        }

        return true;
    }

    return {
        populateSurveySessionPickerFromDetected,
        getSurveySessionValue,
        getBiometricsSessionValue,
    };
}
