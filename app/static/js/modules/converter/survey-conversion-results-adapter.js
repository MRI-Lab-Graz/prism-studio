export function createSurveyConversionResultsAdapter({
    getSurveyConversionSummaryController = () => null,
    getSurveyConversionLogController = () => null,
    getSurveyUnmatchedTemplatesController = () => null,
    getSurveyValidationResultsController = () => null,
} = {}) {
    function appendLog(message, type = 'info', logElement = null) {
        return getSurveyConversionLogController()?.appendLog(message, type, logElement);
    }

    function resetConversionUI() {
        return getSurveyConversionLogController()?.resetConversionUI();
    }

    function displayConversionSummary(summary) {
        return getSurveyConversionSummaryController()?.displayConversionSummary(summary);
    }

    function displayUnmatchedTemplatesCard(unmatched) {
        return getSurveyUnmatchedTemplatesController()?.displayUnmatchedTemplatesCard(unmatched);
    }

    function displayValidationResults(validation, prefix = '') {
        return getSurveyValidationResultsController()?.displayValidationResults(validation, prefix);
    }

    return {
        appendLog,
        resetConversionUI,
        displayConversionSummary,
        displayUnmatchedTemplatesCard,
        displayValidationResults,
    };
}
