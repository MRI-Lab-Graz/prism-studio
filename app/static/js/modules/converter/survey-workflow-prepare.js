export function createSurveyWorkflowPrepareController({
    parseJsonResponse,
    buildSurveyWorkflowRequestFormData,
    getEffectiveNearMatchTasks,
    normalizeTaskValueOffsets,
    advanceSurveyRunProgress,
    pauseSurveyRunProgress,
    resumeSurveyRunProgress,
    isAbortError,
    enrichSurveyRunErrorMessage,
    showManualValueOffsetReview,
    promptNearMatchSelection,
    mergeNearMatchTasks,
    applyPreparedSurveyWorkflowContext,
    hasAppliedVersionWizardSelections,
    convertError,
    convertInfo,
    appendLog,
    setTemplateEditorErrorCtaVisible,
    clearActiveSurveyRun,
    finishSurveyRunProgress,
    updateConvertBtn,
    setIsConvertRunning,
    setIsPreviewRunning,
    getTemplateWorkflowGate,
    setTemplateWorkflowGate,
    setVersionWizardRetryGateMode,
    getConfirmedNearMatchTasks,
    setConfirmedNearMatchTasks,
    isConfiguredOffsetFailureForCurrentSelection,
    normalizeNearMatchTaskName,
    parseNumericOffsetValue,
    formatSignedOffset,
}) {
    function getPreparationRunOutcome(outcome) {
        if (outcome === 'blocked') {
            return 'action_required';
        }
        if (outcome === 'paused') {
            return 'paused';
        }
        if (outcome === 'error') {
            return 'error';
        }
        return 'canceled';
    }

    function finishPreparationPhase(mode, outcome) {
        const resolvedOutcome = getPreparationRunOutcome(outcome);
        const modeTitle = mode === 'convert' ? 'Conversion' : 'Preview';
        const hasInfoMessage = Boolean(String((convertInfo && convertInfo.textContent) || '').trim());

        clearActiveSurveyRun(mode);
        if (mode === 'convert') {
            setIsConvertRunning(false);
        } else {
            setIsPreviewRunning(false);
        }

        if (resolvedOutcome === 'canceled' && !hasInfoMessage && convertInfo) {
            convertInfo.textContent = `${modeTitle} canceled.`;
            convertInfo.classList.remove('d-none');
        }

        finishSurveyRunProgress(mode, resolvedOutcome);
        updateConvertBtn();
        return resolvedOutcome;
    }

    function handleLateSetupBlocker(mode, payload, selectedValueOffsets = {}) {
        const modeTitle = mode === 'convert' ? 'Conversion' : 'Preview';
        const rerunInstruction = mode === 'convert'
            ? 'Run Preview again to refresh setup, then rerun conversion.'
            : 'Run Preview again to refresh setup.';
        const blockingError = String(payload?.blocking_error || payload?.error || '').trim();

        if (blockingError === 'value_offset_manual_review_required') {
            const failedTask = normalizeNearMatchTaskName(payload && payload.task) || 'unknown task';
            const failedOffset = parseNumericOffsetValue(payload && payload.configured_offset);
            const failedOffsetLabel = failedOffset === null ? 'configured offset' : formatSignedOffset(failedOffset);
            if (isConfiguredOffsetFailureForCurrentSelection(payload, selectedValueOffsets) && failedTask !== 'unknown task') {
                appendLog(
                    `Manual value offset for task ${failedTask} (${failedOffsetLabel}) no longer fits this dataset. ${rerunInstruction}`,
                    'error'
                );
            } else {
                appendLog(
                    `Backend setup detected out-of-range survey values after ${modeTitle.toLowerCase()} started. ${rerunInstruction}`,
                    'warning'
                );
            }
            showManualValueOffsetReview(payload, mode, selectedValueOffsets);
            return true;
        }

        if (blockingError === 'near_item_match_confirmation_required') {
            appendLog(
                `Backend setup reported new near-item matches after ${modeTitle.toLowerCase()} started. ${rerunInstruction}`,
                'warning'
            );
            if (convertInfo) {
                convertInfo.textContent = `Near item matches still need confirmation. ${rerunInstruction}`;
                convertInfo.classList.remove('d-none');
            }
            return true;
        }

        if (blockingError === 'project_template_completion_required') {
            const workflowGate = payload.workflow_gate || {
                blocked: true,
                message: payload.message || 'Project templates must be completed before import can continue.'
            };
            setTemplateWorkflowGate(workflowGate);
            setTemplateEditorErrorCtaVisible(true);

            appendLog('Template metadata updates are required before import.', 'warning');
            appendLog(`   ${workflowGate.message}`, 'warning');
            if (Array.isArray(workflowGate.next_steps)) {
                workflowGate.next_steps.forEach(step => appendLog(`   • ${step}`, 'warning'));
            }
            if (Array.isArray(payload.template_issues) && payload.template_issues.length) {
                payload.template_issues.slice(0, 20).forEach(issue => {
                    const name = (issue.file || '').split('/').pop() || 'template';
                    appendLog(`   - ${name}: ${issue.message}`, 'warning');
                });
                if (payload.template_issues.length > 20) {
                    appendLog(`   ... and ${payload.template_issues.length - 20} more template item(s)`, 'warning');
                }
            }

            if (convertInfo) {
                convertInfo.innerHTML = '<i class="fas fa-clipboard-check me-2"></i>Some copied survey templates still need project-level metadata. Complete them in Template Editor, then run Preview again.';
                convertInfo.classList.remove('d-none');
            }
            return true;
        }

        if (String(payload?.message || '').trim()) {
            appendLog(payload.message, 'warning');
            if (convertInfo) {
                convertInfo.textContent = payload.message;
                convertInfo.classList.remove('d-none');
            }
            return true;
        }

        return false;
    }

    async function prepareSurveyWorkflow({
        mode,
        nearMatchTasks = [],
        valueOffsets = {},
        selectedTasks = null,
        signal = null,
    }) {
        const modeLabel = mode === 'convert' ? 'conversion' : 'preview';
        let selectedNearMatchTasks = getEffectiveNearMatchTasks(nearMatchTasks);
        let selectedValueOffsets = normalizeTaskValueOffsets(valueOffsets);

        while (true) {
            const workflowRequest = buildSurveyWorkflowRequestFormData({
                allowNearItemMatch: selectedNearMatchTasks.length > 0,
                nearMatchTasks: selectedNearMatchTasks,
                taskValueOffsets: selectedValueOffsets,
                selectedTasks,
                includeValidation: false,
            });
            if (!workflowRequest.filename) {
                return { ready: false, outcome: 'canceled' };
            }

            let response;
            let data;
            try {
                advanceSurveyRunProgress(mode, 16, `Running ${modeLabel} setup...`);
                workflowRequest.formData.append('workflow_command', 'prepare');
                response = await fetch('/api/survey-workflow-command', {
                    method: 'POST',
                    body: workflowRequest.formData,
                    signal,
                });
                data = await parseJsonResponse(response, 'Survey preparation');
            } catch (error) {
                if (isAbortError(error)) {
                    return { ready: false, outcome: 'canceled' };
                }
                if (convertError) {
                    convertError.textContent = enrichSurveyRunErrorMessage(error.message || 'Survey preparation failed');
                    convertError.classList.remove('d-none');
                }
                return { ready: false, outcome: 'error' };
            }

            if (!response.ok) {
                if (data.error === 'value_offset_manual_review_required') {
                    showManualValueOffsetReview(data, mode, selectedValueOffsets);
                    return { ready: false, outcome: 'blocked' };
                }

                if (data.error === 'near_item_match_confirmation_required') {
                    pauseSurveyRunProgress(mode, 'Waiting for near-match confirmation...');
                    const selection = await promptNearMatchSelection(data, mode === 'convert' ? 'conversion setup' : 'preview setup');
                    if (selection.approved && selection.selectedTasks.length > 0) {
                        const mergedConfirmedTasks = mergeNearMatchTasks(
                            getConfirmedNearMatchTasks(),
                            selection.selectedTasks,
                        );
                        setConfirmedNearMatchTasks(mergedConfirmedTasks);
                        selectedNearMatchTasks = getEffectiveNearMatchTasks(selection.selectedTasks);
                        resumeSurveyRunProgress(mode, 36, 'Near matches confirmed. Continuing setup...');
                        continue;
                    }

                    if (convertInfo) {
                        convertInfo.textContent = 'Near item matches were detected but not approved. Import setup was canceled.';
                        convertInfo.classList.remove('d-none');
                    }
                    return { ready: false, outcome: 'canceled' };
                }

                if (data && data.workflow_gate && typeof data.workflow_gate === 'object') {
                    setTemplateWorkflowGate(data.workflow_gate);
                    const workflowGate = getTemplateWorkflowGate();
                    setTemplateEditorErrorCtaVisible(Boolean(workflowGate && workflowGate.blocked));
                }

                if (convertError) {
                    convertError.textContent = String(data?.message || data?.error || 'Survey preparation failed');
                    convertError.classList.remove('d-none');
                }
                return { ready: false, outcome: 'error' };
            }

            const multivariantTasks = applyPreparedSurveyWorkflowContext(data);
            const workflowGate = getTemplateWorkflowGate();
            if (workflowGate && workflowGate.blocked) {
                if (convertInfo) {
                    convertInfo.textContent = workflowGate.message || 'Template completion is required before import can continue.';
                    convertInfo.classList.remove('d-none');
                }
                return { ready: false, outcome: 'blocked' };
            }

            if (Object.keys(multivariantTasks).length > 0 && !hasAppliedVersionWizardSelections()) {
                setVersionWizardRetryGateMode(mode);
                const retryModeLabel = mode === 'convert' ? 'conversion' : 'preview';
                if (convertInfo) {
                    convertInfo.textContent = `Multi-version options are available. Review the selector below, click Use These Versions, then run ${retryModeLabel} again.`;
                    convertInfo.classList.remove('d-none');
                }
                return { ready: false, outcome: 'paused' };
            }

            setVersionWizardRetryGateMode(null);
            advanceSurveyRunProgress(mode, 48, `Setup complete. Starting ${modeLabel}...`);
            return {
                ready: true,
                nearMatchTasks: selectedNearMatchTasks,
                valueOffsets: selectedValueOffsets,
            };
        }
    }

    return {
        finishPreparationPhase,
        handleLateSetupBlocker,
        prepareSurveyWorkflow,
    };
}
