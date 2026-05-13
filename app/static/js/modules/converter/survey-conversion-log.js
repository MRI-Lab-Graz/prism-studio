import { appendConverterLogLine } from './log-renderer.js';

export function createSurveyConversionLogController({
    toggleLogBtn,
    conversionLogBody,
    conversionLogContainer,
    validationResultsContainer,
    conversionSummaryContainer,
    conversionSummaryBody,
    conversionLog,
    validationSummary,
    validationDetails,
    hideSurveyRunProgress,
}) {
    function initialize() {
        if (toggleLogBtn) {
            toggleLogBtn.addEventListener('click', function() {
                conversionLogBody.classList.toggle('d-none');
                const icon = toggleLogBtn.querySelector('i');
                if (conversionLogBody.classList.contains('d-none')) {
                    icon.classList.remove('fa-chevron-down');
                    icon.classList.add('fa-chevron-right');
                } else {
                    icon.classList.remove('fa-chevron-right');
                    icon.classList.add('fa-chevron-down');
                }
            });
        }
    }

    function appendLog(message, type = 'info', logElement = null) {
        appendConverterLogLine(message, type, logElement, conversionLog);
    }

    function resetConversionUI() {
        hideSurveyRunProgress();
        conversionLogContainer.classList.add('d-none');
        validationResultsContainer.classList.add('d-none');
        if (conversionSummaryContainer) conversionSummaryContainer.classList.add('d-none');
        if (conversionSummaryBody) conversionSummaryBody.innerHTML = '';
        conversionLog.innerHTML = '';
        validationSummary.innerHTML = '';
        validationDetails.innerHTML = '';
    }

    return {
        initialize,
        appendLog,
        resetConversionUI,
    };
}
