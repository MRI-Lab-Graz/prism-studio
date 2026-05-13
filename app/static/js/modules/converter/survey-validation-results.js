import { displayConverterValidationResults } from './validation-results-renderer.js';

export function createSurveyValidationResultsController({
    escapeHtml,
}) {
    function displayValidationResults(validation, prefix = '') {
        displayConverterValidationResults(validation, prefix, escapeHtml);
    }

    return {
        displayValidationResults,
    };
}
