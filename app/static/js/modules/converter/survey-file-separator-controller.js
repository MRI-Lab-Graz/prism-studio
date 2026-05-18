import {
    getSelectedSeparator,
    isDelimitedSurveyFilename,
    updateSeparatorVisibility,
} from './survey-file-separator-utils.js';

export function createSurveyFileSeparatorController({
    convertSeparator = null,
    surveySeparatorGroup = null,
} = {}) {
    return {
        isDelimitedSurveyFilename,
        getSelectedSeparator: (filename = '') => getSelectedSeparator(filename, convertSeparator),
        updateSeparatorVisibility: (filename = '') => updateSeparatorVisibility(filename, surveySeparatorGroup),
    };
}
