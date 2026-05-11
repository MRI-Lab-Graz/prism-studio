export function createSurveyImportFormStateController({
    convertSeparator,
    convertIdMapFile,
    clearIdMapFileBtn,
    convertSessionSelect,
    convertSessionCustom,
    convertAdvancedToggle,
    convertExcelFile,
    templateResultsContainer,
    convertInfo,
    convertError,
    surveySourcedataQuickSelectController,
    cancelVersionWizardSync,
    hideVersionWizard,
    clearManualValueOffsetAdvice,
    setTemplateEditorErrorCtaVisible,
    resetConversionUI,
    resetSurveyRefreshFingerprint,
    setCurrentTemplateData,
    resetDetectedColumnsState,
    applyAdvancedOptionsState,
    populateSessionPickers,
    updateSeparatorVisibility,
    updateConvertBtn,
    setTemplateWorkflowGate,
    setVersionWizardRetryGateMode,
    setAppliedTaskValueOffsetSelectionSignature,
    setConvertServerFilePath,
}) {
    function resetSurveyImportFormState({ clearSelectedInput = false } = {}) {
        setTemplateWorkflowGate(null);
        cancelVersionWizardSync();
        setVersionWizardRetryGateMode(null);
        setAppliedTaskValueOffsetSelectionSignature('');
        hideVersionWizard();
        clearManualValueOffsetAdvice();
        setTemplateEditorErrorCtaVisible(false);
        resetConversionUI();
        resetSurveyRefreshFingerprint();

        setCurrentTemplateData(null);
        window.lastPreviewData = null;
        window.lastParticipantsPreviewData = null;

        // Reset separator to default for next import.
        if (convertSeparator) {
            const hasAuto = Array.from(convertSeparator.options || []).some(o => o.value === 'auto');
            if (hasAuto) {
                convertSeparator.value = 'auto';
            } else if (convertSeparator.options.length > 0) {
                convertSeparator.selectedIndex = 0;
            }
        }

        // Reset detected columns / ID mapping state.
        resetDetectedColumnsState();
        if (convertIdMapFile) convertIdMapFile.value = '';
        clearIdMapFileBtn?.classList.add('d-none');

        // Reset session selections so user starts fresh.
        if (convertSessionSelect) {
            if (convertSessionSelect.options.length > 0) {
                convertSessionSelect.selectedIndex = 0;
            } else {
                convertSessionSelect.value = '';
            }
        }
        if (convertSessionCustom) convertSessionCustom.value = '';

        // Reset optional inputs to their initial state.
        if (convertAdvancedToggle) {
            convertAdvancedToggle.checked = false;
        }
        applyAdvancedOptionsState();

        if (clearSelectedInput) {
            setConvertServerFilePath('');
            if (convertExcelFile) {
                convertExcelFile.value = '';
            }
        }
        surveySourcedataQuickSelectController.clearSelectedFile();

        // Hide stale results from previous preview/convert runs.
        if (templateResultsContainer) {
            templateResultsContainer.classList.add('d-none');
            document.getElementById('templateResultSingle')?.classList.add('d-none');
            document.getElementById('templateResultGroups')?.classList.add('d-none');
            document.getElementById('templateResultQuestions')?.classList.add('d-none');
            document.getElementById('participantMetadataSection')?.classList.add('d-none');
        }

        convertInfo.classList.add('d-none');
        convertInfo.textContent = '';
        convertError.classList.add('d-none');
        convertError.textContent = '';

        populateSessionPickers();
        updateSeparatorVisibility('');
        updateConvertBtn();
    }

    return {
        resetSurveyImportFormState,
    };
}
