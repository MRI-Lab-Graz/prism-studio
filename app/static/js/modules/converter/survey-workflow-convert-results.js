export function createSurveyWorkflowConvertResultsController({
    convertInfo,
    setTemplateEditorErrorCtaVisible,
    appendLog,
    displayConversionSummary,
    getSurveySessionValue,
    registerSessionInProject,
    getProjectSaveSummary,
    getParticipantRegistryWarning,
    showParticipantRegistryWarning,
    displayValidationResults,
}) {
    function appendParticipantRegistryWarningLogs(participantRegistryWarning) {
        if (!participantRegistryWarning) {
            return;
        }

        appendLog(`⚠ ${participantRegistryWarning.message}`, 'warning');
        if (participantRegistryWarning.details) {
            appendLog(`   ${participantRegistryWarning.details}`, 'warning');
        }
        if (participantRegistryWarning.next_step) {
            appendLog(`   ${participantRegistryWarning.next_step}`, 'warning');
        }
    }

    function finalizeProjectSaveOutcome(data, participantRegistryWarning) {
        if (data.project_saved) {
            const saveSummary = getProjectSaveSummary(data);
            appendLog(`✓ Data saved to project: ${saveSummary.target}${saveSummary.countNote}`, 'success');
            if (participantRegistryWarning) {
                appendParticipantRegistryWarningLogs(participantRegistryWarning);
                showParticipantRegistryWarning(
                    `Conversion complete. First saved path: ${saveSummary.target}${saveSummary.countNote}`,
                    participantRegistryWarning,
                );
            } else {
                convertInfo.textContent = `Conversion complete. First saved path: ${saveSummary.target}${saveSummary.countNote}`;
            }
            return;
        }

        appendLog('⚠ Conversion finished, but nothing was copied into the project.', 'warning');
        if (participantRegistryWarning) {
            appendParticipantRegistryWarningLogs(participantRegistryWarning);
            showParticipantRegistryWarning(
                'Conversion finished, but nothing was copied into the project. Review the conversion log.',
                participantRegistryWarning,
            );
        } else {
            convertInfo.textContent = 'Conversion finished, but nothing was copied into the project. Review the conversion log.';
        }
    }

    function handleConvertSuccess(data, { sourceFilename = '' } = {}) {
        const participantRegistryWarning = getParticipantRegistryWarning(data);

        if (data.conversion_summary) {
            displayConversionSummary(data.conversion_summary);
        }

        const regSessionVal = getSurveySessionValue();
        const regTasks = (data.conversion_summary && data.conversion_summary.tasks_included) || [];
        if (data.project_saved && regSessionVal && regTasks.length) {
            const normalizedFilename = String(sourceFilename || '');
            const srcExt = normalizedFilename.toLowerCase().split('.').pop();
            const convType = srcExt === 'lsa' ? 'survey-lsa' : 'survey-xlsx';
            registerSessionInProject(regSessionVal, regTasks, 'survey', normalizedFilename, convType);
        }

        if (data.validation) {
            const validation = data.validation;
            const errorCount = (validation.errors || []).length;
            const warningCount = (validation.warnings || []).length;
            setTemplateEditorErrorCtaVisible(errorCount > 0);

            if (errorCount === 0 && warningCount === 0) {
                appendLog('✓ Validation passed - dataset is valid!', 'success');
            } else if (errorCount === 0) {
                appendLog(`⚠ Validation passed with ${warningCount} warning(s)`, 'warning');
            } else {
                appendLog(`Validation found ${errorCount} error(s)`, 'error');
            }

            displayValidationResults(validation);
        }

        finalizeProjectSaveOutcome(data, participantRegistryWarning);

        appendLog('═══════════════════════════════════════════════', 'info');
        appendLog('✓ Conversion completed successfully', 'success');
        appendLog('═══════════════════════════════════════════════', 'info');

        convertInfo.classList.remove('d-none');
    }

    return {
        handleConvertSuccess,
    };
}