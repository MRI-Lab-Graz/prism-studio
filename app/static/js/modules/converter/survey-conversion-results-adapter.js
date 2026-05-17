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

    function displayUnmatchedGroupsError(data) {
        return getSurveyUnmatchedTemplatesController()?.displayUnmatchedGroupsError(data);
    }

    function displayValidationResults(validation, prefix = '') {
        return getSurveyValidationResultsController()?.displayValidationResults(validation, prefix);
    }

    return {
        appendLog,
        resetConversionUI,
        displayConversionSummary,
        displayUnmatchedGroupsError,
        displayValidationResults,
    };
}
