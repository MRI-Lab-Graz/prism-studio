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
        const colors = {
            'info': '#17a2b8',
            'success': '#28a745',
            'warning': '#ffc107',
            'error': '#dc3545',
            'step': '#6c757d'
        };
        const targetLog = logElement || conversionLog;
        if (!targetLog) return;

        const timestamp = new Date().toLocaleTimeString();
        const color = colors[type] || colors.info;
        const line = document.createElement('span');
        line.style.color = color;
        line.textContent = `[${timestamp}] ${String(message)}`;
        targetLog.appendChild(line);
        targetLog.appendChild(document.createTextNode('\n'));
        targetLog.scrollTop = targetLog.scrollHeight;
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
