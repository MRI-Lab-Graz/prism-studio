export function createSurveyWorkflowConvertController({
    convertError,
    convertInfo,
    surveyVersionWizardApplyBtn,
    convertApplyValueOffsetsBtn,
    convertSessionCustom,
    convertSessionSelect,
    convertIdMapFile,
    convertDatasetName,
    convertLanguage,
    convertIdColumn,
    convertSessionColumnOverride,
    convertRunColumnOverride,
    conversionLogContainer,
    conversionLogBody,
    toggleLogBtn,
    templateResultsContainer,
    surveyWorkflowPrepareController,
    clearManualValueOffsetAdvice,
    setTemplateEditorErrorCtaVisible,
    hasMultiVersionWizardTasks,
    hasAppliedVersionWizardSelections,
    updateVersionWizardActionState,
    updateConvertBtn,
    hasManualTaskValueOffsets,
    hasAppliedTaskValueOffsetSelections,
    updateTaskValueOffsetApplyState,
    hasFreshSurveyPreviewSelectionState,
    getSelectedSurveyTasksForConversion,
    resetConversionUI,
    getEffectiveNearMatchTasks,
    getEffectiveTaskValueOffsets,
    ensureSurveyAdvancedOptionsVisible,
    focusTaskValueOffsetEditor,
    getSelectedSurveyFilename,
    getSelectedSurveyFile,
    getSurveySessionValue,
    isAdvancedOptionsEnabled,
    refreshSurveyColumnsBeforeRun,
    setActiveSurveyRun,
    startSurveyRunProgress,
    setIsConvertRunning,
    appendSurveyInputToFormData,
    getConvertServerFilePath,
    appendLog,
    handleConvertSuccess,
    getSelectedSeparator,
    appendTemplateVersionSelections,
    formatSignedOffset,
    advanceSurveyRunProgress,
    displayUnmatchedGroupsError,
    isAbortError,
    enrichSurveyRunErrorMessage,
    clearActiveSurveyRun,
    finishSurveyRunProgress,
    getActiveRunMode,
    getActiveRunCancelledByUser,
    getVersionWizardRetryGateMode,
    setVersionWizardRetryGateMode,
    getTemplateWorkflowGate,
    setTemplateWorkflowGate,
}) {
    async function handleConvertClick() {
        setVersionWizardRetryGateMode(null);
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');
        convertError.textContent = '';
        clearManualValueOffsetAdvice();
        setTemplateEditorErrorCtaVisible(false);
        convertInfo.textContent = '';

        if (hasMultiVersionWizardTasks() && !hasAppliedVersionWizardSelections()) {
            convertInfo.textContent = 'Review the selector below, click Use These Versions, then run Preview again.';
            convertInfo.classList.remove('d-none');
            surveyVersionWizardApplyBtn?.focus();
            updateVersionWizardActionState();
            updateConvertBtn();
            return;
        }

        if (hasManualTaskValueOffsets() && !hasAppliedTaskValueOffsetSelections()) {
            convertInfo.textContent = 'Manual offsets changed. Click Apply offsets, then run Preview again.';
            convertInfo.classList.remove('d-none');
            convertApplyValueOffsetsBtn?.focus();
            updateTaskValueOffsetApplyState();
            updateConvertBtn();
            return;
        }

        const hasFreshPreviewReview = hasFreshSurveyPreviewSelectionState();
        const selectedSurveyTasks = getSelectedSurveyTasksForConversion();
        if (!hasFreshPreviewReview) {
            convertError.textContent = 'Run Preview again before converting. Survey selection and out-of-range review are now part of the workflow.';
            convertError.classList.remove('d-none');
            updateConvertBtn();
            return;
        }

        if (selectedSurveyTasks.length === 0) {
            convertError.textContent = 'Select at least one survey in the Preview review list before converting.';
            convertError.classList.remove('d-none');
            updateConvertBtn();
            return;
        }

        resetConversionUI();
        setTemplateWorkflowGate(null);
        let selectedNearMatchTasks = getEffectiveNearMatchTasks();
        let selectedValueOffsets = {};
        try {
            selectedValueOffsets = getEffectiveTaskValueOffsets();
        } catch (error) {
            convertError.textContent = error.message || 'Invalid task value offsets in Advanced options.';
            convertError.classList.remove('d-none');
            ensureSurveyAdvancedOptionsVisible();
            focusTaskValueOffsetEditor();
            return;
        }

        let allowNearItemMatch = selectedNearMatchTasks.length > 0;
        let convertRunOutcome = 'running';

        if (templateResultsContainer) {
            templateResultsContainer.classList.add('d-none');
            document.getElementById('templateResultSingle')?.classList.add('d-none');
            document.getElementById('templateResultGroups')?.classList.add('d-none');
            document.getElementById('templateResultQuestions')?.classList.add('d-none');
            document.getElementById('participantMetadataSection')?.classList.add('d-none');
        }

        const filenameRaw = getSelectedSurveyFilename();
        if (!filenameRaw) {
            return;
        }

        const file = getSelectedSurveyFile();
        const filename = filenameRaw.toLowerCase();
        const isLssFile = filename.endsWith('.lss');

        const sessionVal = getSurveySessionValue();
        if (!sessionVal) {
            convertError.textContent = 'Please enter a session ID (e.g., 1, 2, 3).';
            convertError.classList.remove('d-none');
            (convertSessionCustom || convertSessionSelect)?.focus();
            return;
        }

        if (isLssFile) {
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i><strong>.lss files contain structure only</strong> (no response data). Use <a href="/template-editor" class="alert-link">Template Editor</a> for template generation, or upload a <strong>.lsa</strong> file (archive with responses).';
            convertError.classList.remove('d-none');
            return;
        }

        const idMap = isAdvancedOptionsEnabled() && convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
        if (idMap && idMap.size === 0) {
            convertError.classList.remove('d-none');
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>ID map file is empty';
            return;
        }

        await refreshSurveyColumnsBeforeRun();

        const idColumnVal = convertIdColumn?.value;
        if (!window._isPrismData && (!idColumnVal || idColumnVal === 'auto' || idColumnVal === '')) {
            convertError.classList.remove('d-none');
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Please select a participant ID column before converting.';
            if (convertIdColumn) {
                convertIdColumn.classList.add('border-danger');
                convertIdColumn.focus();
            }
            return;
        }

        const convertRunAbortController = new AbortController();
        setActiveSurveyRun('convert', convertRunAbortController);
        setIsConvertRunning(true);
        updateConvertBtn();
        startSurveyRunProgress('convert');

        const preparation = await surveyWorkflowPrepareController.prepareSurveyWorkflow({
            mode: 'convert',
            nearMatchTasks: selectedNearMatchTasks,
            valueOffsets: selectedValueOffsets,
            signal: convertRunAbortController.signal,
        });
        if (!preparation.ready) {
            surveyWorkflowPrepareController.finishPreparationPhase('convert', preparation.outcome);
            return;
        }

        selectedNearMatchTasks = preparation.nearMatchTasks;
        selectedValueOffsets = preparation.valueOffsets;
        allowNearItemMatch = selectedNearMatchTasks.length > 0;

        const formData = new FormData();
        appendSurveyInputToFormData(formData);
        if (file) {
            console.log(`[CLIENT DEBUG] Excel file: ${file.name}, size: ${file.size}`);
        } else {
            console.log(`[CLIENT DEBUG] Server source file: ${getConvertServerFilePath()}`);
        }

        if (idMap) {
            console.log(`[CLIENT DEBUG] ID map file before append: ${idMap.name}, size: ${idMap.size}, type: ${idMap.type}`);
            formData.append('id_map', idMap);
            console.log('[CLIENT DEBUG] ID map appended to FormData');
            appendLog(`Using ID map file: ${idMap.name} (${idMap.size} bytes)`, 'step');
        }

        if (isAdvancedOptionsEnabled() && convertDatasetName && convertDatasetName.value.trim()) {
            formData.append('survey', convertDatasetName.value.trim());
        }
        formData.append('selected_tasks', JSON.stringify(selectedSurveyTasks));

        conversionLogContainer.classList.remove('d-none');
        conversionLogBody.classList.remove('d-none');
        const icon = toggleLogBtn.querySelector('i');
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');

        appendLog(`Starting conversion of: ${filenameRaw}`, 'info');
        appendLog('Using library: Project library first, then global', 'step');
        appendLog(`Selected surveys: ${selectedSurveyTasks.join(', ')}`, 'step');

        formData.append('save_to_project', 'true');
        appendLog('Output will be saved under the active project', 'step');

        if (idColumnVal && idColumnVal !== 'auto' && idColumnVal !== '') {
            formData.append('id_column', idColumnVal);
            appendLog(`Using ID column: ${idColumnVal}`, 'step');
        }

        formData.append('session', sessionVal);
        appendLog(`Forcing session ID: ${sessionVal}`, 'step');

        const sessionColVal = (convertSessionColumnOverride && convertSessionColumnOverride.value.trim()) || '';
        const runColVal = (convertRunColumnOverride && convertRunColumnOverride.value.trim()) || '';
        if (sessionColVal) {
            formData.append('session_column', sessionColVal);
        }
        if (runColVal) {
            formData.append('run_column', runColVal);
        }

        formData.append('language', (isAdvancedOptionsEnabled() && convertLanguage) ? convertLanguage.value : 'auto');
        formData.append('separator', getSelectedSeparator(filename));
        formData.append('validate', 'true');
        formData.append('prepared_workflow', 'true');
        formData.append('workflow_command', 'convert');

        const templateSelections = appendTemplateVersionSelections(formData);
        if (templateSelections.length > 0) {
            appendLog(`Template versions: ${templateSelections.map((entry) => `${entry.task}${entry.session ? `;session=${entry.session}` : ''}${entry.run ? `;run=${entry.run}` : ''}=${entry.version}`).join(', ')}`, 'step');
        }

        if (allowNearItemMatch) {
            formData.append('allow_near_item_match', 'true');
            if (selectedNearMatchTasks.length > 0) {
                formData.append('near_match_tasks', JSON.stringify(selectedNearMatchTasks));
            }
            const nearMatchScope = selectedNearMatchTasks.length > 0
                ? `${selectedNearMatchTasks.length} selected survey task(s)`
                : 'all detected survey tasks';
            appendLog(`Applying confirmed near item matches for ${nearMatchScope} (minimal formatting differences only).`, 'warning');
        }

        if (Object.keys(selectedValueOffsets).length > 0) {
            formData.append('value_offsets', JSON.stringify(selectedValueOffsets));
            const offsetSummary = Object.entries(selectedValueOffsets)
                .map(([task, offset]) => `${task}: ${formatSignedOffset(offset)}`)
                .join(', ');
            appendLog(`Applying confirmed value offset(s): ${offsetSummary}.`, 'warning');
        }

        advanceSurveyRunProgress('convert', 20, 'Uploading file and starting conversion...');
        appendLog('Uploading file and starting conversion...', 'info');

        fetch('/api/survey-workflow-command', {
            method: 'POST',
            body: formData,
            signal: convertRunAbortController.signal,
        })
            .then(async response => {
                const contentType = response.headers.get('content-type') || '';
                let data = null;
                advanceSurveyRunProgress('convert', 38, 'Server response received. Validating conversion request...');

                if (contentType.includes('application/json')) {
                    data = await response.json();
                    if (data.log && Array.isArray(data.log)) {
                        data.log.forEach(entry => {
                            appendLog(entry.message, entry.type || entry.level || 'info');
                        });
                    }

                    if (!response.ok) {
                        if (data.error === 'workflow_preparation_stale') {
                            convertRunOutcome = 'action_required';
                            surveyWorkflowPrepareController.handleLateSetupBlocker('convert', data, selectedValueOffsets);
                            return null;
                        }
                        if (data.error === 'id_column_required') {
                            if (convertIdColumn) {
                                convertIdColumn.classList.add('border-danger');
                                convertIdColumn.focus();
                            }
                            throw new Error('Please select the participant ID column.');
                        }
                        if (data.error === 'unmatched_groups') {
                            convertRunOutcome = 'action_required';
                            displayUnmatchedGroupsError(data);
                            return null;
                        }
                        setTemplateWorkflowGate(null);
                        setTemplateEditorErrorCtaVisible(false);
                        throw new Error(data.error || 'Conversion failed');
                    }

                    advanceSurveyRunProgress('convert', 68, 'Applying conversion output and validation details...');
                    return data;
                }

                if (!response.ok) {
                    throw new Error('Conversion failed');
                }
                await response.blob();
                advanceSurveyRunProgress('convert', 68, 'Processing conversion output...');
                return { validation: null };
            })
            .then(data => {
                if (!data) return;

                advanceSurveyRunProgress('convert', 84, 'Finalizing conversion results...');
                handleConvertSuccess(data, {
                    sourceFilename: file ? file.name : '',
                });
                convertRunOutcome = 'success';
                advanceSurveyRunProgress('convert', 100, 'Conversion completed.');
            })
            .catch(err => {
                if (isAbortError(err)) {
                    convertRunOutcome = 'canceled';
                    appendLog('Conversion canceled by user.', 'warning');
                    convertError.classList.add('d-none');
                    convertInfo.textContent = 'Conversion canceled.';
                    convertInfo.classList.remove('d-none');
                    return;
                }
                convertRunOutcome = 'error';
                const enrichedMessage = enrichSurveyRunErrorMessage(err.message);
                appendLog(`Error: ${enrichedMessage}`, 'error');
                if (enrichedMessage !== err.message) {
                    appendLog('Tip: Save the spreadsheet in Excel and re-select it before running again.', 'warning');
                }
                convertError.textContent = enrichedMessage;
                convertError.classList.remove('d-none');
                setTemplateEditorErrorCtaVisible(Boolean(getTemplateWorkflowGate() && getTemplateWorkflowGate().blocked));
            })
            .finally(() => {
                setIsConvertRunning(false);
                const canceledByUser = getActiveRunMode() === 'convert' && getActiveRunCancelledByUser();
                clearActiveSurveyRun('convert');
                const blockedByVersionWizardGate = getVersionWizardRetryGateMode() === 'convert';
                if (convertRunOutcome === 'running') {
                    convertRunOutcome = blockedByVersionWizardGate ? 'paused' : 'canceled';
                }
                if (canceledByUser && convertRunOutcome !== 'success') {
                    convertRunOutcome = 'canceled';
                }
                finishSurveyRunProgress('convert', convertRunOutcome);
                updateConvertBtn();
            });
    }

    return {
        handleConvertClick,
    };
}
