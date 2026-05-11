export function createSurveyWorkflowTemplateCheckController({
    checkProjectTemplatesBtn,
    surveyVersionWizardApplyBtn,
    convertError,
    conversionLogContainer,
    conversionLogBody,
    toggleLogBtn,
    getSelectedSurveyFilename,
    convertIdColumn,
    appendLog,
    resolveCurrentProjectPath,
    appendSurveyInputToFormData,
    getSelectedSeparator,
    parseJsonResponse,
    setTemplateWorkflowGate,
    setTemplateEditorErrorCtaVisible,
    convertInfo,
    buildVersionWizard,
    hideVersionWizard,
    updateConvertBtn,
    hasMultiVersionWizardTasks,
    hasCompleteVersionWizardSelections,
    getCurrentTemplateVersionSelectionSignature,
    setAppliedTemplateVersionSelectionSignature,
    setVersionWizardRetryGateMode,
    getTemplateWorkflowGate,
    updateVersionWizardActionState,
}) {
    async function handleCheckProjectTemplatesClick() {
        convertError.classList.add('d-none');
        convertError.textContent = '';

        conversionLogContainer.classList.remove('d-none');
        conversionLogBody.classList.remove('d-none');
        const icon = toggleLogBtn.querySelector('i');
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');

        const selectedFilename = getSelectedSurveyFilename();
        const selectedIdColumn = (convertIdColumn && convertIdColumn.value && convertIdColumn.value !== 'auto')
            ? convertIdColumn.value
            : '';

        if (selectedFilename) {
            appendLog(`Checking official templates against input: ${selectedFilename}`, 'info');
        }
        appendLog('Checking local project survey templates...', 'info');
        checkProjectTemplatesBtn.disabled = true;

        try {
            const formData = new FormData();
            const currentProjectPath = resolveCurrentProjectPath();
            appendSurveyInputToFormData(formData);
            if (currentProjectPath) {
                formData.append('project_path', currentProjectPath);
            }
            if (selectedIdColumn) {
                formData.append('id_column', selectedIdColumn);
            }
            formData.append('separator', getSelectedSeparator(selectedFilename ? selectedFilename.toLowerCase() : ''));

            const response = await fetch('/api/survey-check-project-templates', {
                method: 'POST',
                body: formData,
            });
            const data = await parseJsonResponse(response, 'Template check');

            if (!response.ok) {
                if (data.error === 'id_column_required') {
                    if (convertIdColumn) {
                        convertIdColumn.classList.add('border-danger');
                        convertIdColumn.focus();
                    }
                    throw new Error('Please select a participant ID column, then run template check again.');
                }
                throw new Error(data.error || 'Template check could not be completed');
            }

            const templateCount = Number.isFinite(data.template_count) ? data.template_count : 0;
            const tasks = Array.isArray(data.tasks) ? data.tasks : [];
            const localTemplates = Array.isArray(data.local_templates) ? data.local_templates : [];
            const templateWarnings = Array.isArray(data.warnings) ? data.warnings : [];
            const matching = (data && typeof data.matching === 'object' && data.matching)
                ? data.matching
                : null;

            if (matching && matching.input_file) {
                const officialCount = Number.isFinite(matching.official_template_count)
                    ? matching.official_template_count
                    : 0;
                appendLog(`Official templates available: ${officialCount}`, 'info');

                const matchedTasks = Array.isArray(matching.matched_tasks) ? matching.matched_tasks : [];
                if (matchedTasks.length > 0) {
                    appendLog(`Official templates matched from input: ${matchedTasks.join(', ')}`, 'success');
                } else {
                    appendLog('No official template matches were detected from the selected input file.', 'warning');
                }

                const copiedTasks = Array.isArray(matching.copied_tasks) ? matching.copied_tasks : [];
                if (copiedTasks.length > 0) {
                    appendLog(`Copied to project library: ${copiedTasks.join(', ')}`, 'info');
                }

                const existingTasks = Array.isArray(matching.existing_tasks) ? matching.existing_tasks : [];
                if (existingTasks.length > 0) {
                    appendLog(`Already present in project library: ${existingTasks.join(', ')}`, 'info');
                }

                const missingOfficial = Array.isArray(matching.missing_official_tasks)
                    ? matching.missing_official_tasks
                    : [];
                if (missingOfficial.length > 0) {
                    appendLog(`Not found in official library by task name: ${missingOfficial.join(', ')}`, 'warning');
                }

                if (matching.match_error) {
                    appendLog(`Template matching note: ${matching.match_error}`, 'warning');
                }
            }

            appendLog(`Local templates found (${templateCount}): ${localTemplates.length ? localTemplates.join(', ') : '(none)'}`, 'info');
            if (tasks.length) {
                appendLog(`Tasks covered: ${tasks.join(', ')}`, 'info');
            }
            if (templateWarnings.length) {
                appendLog(`Template quality warnings: ${templateWarnings.length}`, 'warning');
                templateWarnings.slice(0, 30).forEach((warn) => {
                    const fileName = (warn.file || '').split('/').pop() || 'template';
                    appendLog(`  - ${fileName}: ${warn.message}`, 'warning');
                });
                if (templateWarnings.length > 30) {
                    appendLog(`  ... and ${templateWarnings.length - 30} more warning(s)`, 'warning');
                }
            }

            if (data.ok) {
                setTemplateWorkflowGate(null);
                setTemplateEditorErrorCtaVisible(false);
                appendLog('Project template check passed.', 'success');
                convertInfo.innerHTML = '<i class="fas fa-check-circle me-2"></i>Project templates look good. Continue with Preview (Dry-Run).';
                convertInfo.classList.remove('d-none');
            } else {
                const nextTemplateWorkflowGate = data.workflow_gate || {
                    blocked: true,
                    message: data.message || 'Project templates require completion before import.',
                };
                setTemplateWorkflowGate(nextTemplateWorkflowGate);
                setTemplateEditorErrorCtaVisible(true);

                appendLog('Template check found templates that still need project-level fields.', 'warning');
                appendLog(`  ${nextTemplateWorkflowGate.message}`, 'warning');
                if (Array.isArray(nextTemplateWorkflowGate.next_steps)) {
                    nextTemplateWorkflowGate.next_steps.forEach((step) => appendLog(`  - ${step}`, 'warning'));
                }

                const issues = Array.isArray(data.issues) ? data.issues : [];
                issues.slice(0, 30).forEach((issue) => {
                    const fileName = (issue.file || '').split('/').pop() || 'template';
                    appendLog(`  - ${fileName}: ${issue.message}`, 'warning');
                });
                if (issues.length > 30) {
                    appendLog(`  ... and ${issues.length - 30} more item(s)`, 'warning');
                }

                convertInfo.innerHTML = '<i class="fas fa-clipboard-check me-2"></i>Some copied survey templates still need project-level metadata. Complete them in Template Editor, then run Preview again.';
                convertInfo.classList.remove('d-none');
            }

            const multivariantTasks = (data && typeof data.multivariant_tasks === 'object' && data.multivariant_tasks)
                ? data.multivariant_tasks
                : {};
            if (Object.keys(multivariantTasks).length > 0) {
                buildVersionWizard(
                    multivariantTasks,
                    (data && typeof data.task_runs === 'object' && data.task_runs) || {},
                    [],
                    Array.isArray(data.detected_sessions) ? data.detected_sessions : []
                );
                appendLog(`Multi-version questionnaire(s) detected: ${Object.keys(multivariantTasks).join(', ')}. Review the selector below, click Use These Versions, then preview or convert.`, 'info');
            } else {
                hideVersionWizard();
            }
        } catch (error) {
            appendLog(`Template check error: ${error.message}`, 'error');
            convertError.textContent = error.message;
            convertError.classList.remove('d-none');
            setTemplateEditorErrorCtaVisible(true);
        } finally {
            updateConvertBtn();
        }
    }

    function initialize() {
        if (checkProjectTemplatesBtn) {
            checkProjectTemplatesBtn.addEventListener('click', handleCheckProjectTemplatesClick);
        }
        surveyVersionWizardApplyBtn?.addEventListener('click', handleVersionWizardApplyClick);
    }

    function handleVersionWizardApplyClick() {
        const hasMultiVersionTasks = typeof hasMultiVersionWizardTasks === 'function'
            ? hasMultiVersionWizardTasks()
            : false;
        const hasCompleteSelections = typeof hasCompleteVersionWizardSelections === 'function'
            ? hasCompleteVersionWizardSelections()
            : false;

        if (!hasMultiVersionTasks || !hasCompleteSelections) {
            if (typeof updateVersionWizardActionState === 'function') {
                updateVersionWizardActionState();
            }
            return;
        }

        const currentSignature = typeof getCurrentTemplateVersionSelectionSignature === 'function'
            ? getCurrentTemplateVersionSelectionSignature()
            : '';

        if (typeof setAppliedTemplateVersionSelectionSignature === 'function') {
            setAppliedTemplateVersionSelectionSignature(currentSignature);
        }
        if (typeof setVersionWizardRetryGateMode === 'function') {
            setVersionWizardRetryGateMode(null);
        }

        const templateWorkflowGate = typeof getTemplateWorkflowGate === 'function'
            ? getTemplateWorkflowGate()
            : null;
        const hasBlockedTemplateGate = Boolean(templateWorkflowGate && templateWorkflowGate.blocked);
        const infoText = String(convertInfo?.textContent || '').trim().toLowerCase();
        if (!hasBlockedTemplateGate && (infoText.includes('multi-version') || infoText.includes('questionnaire version'))) {
            convertInfo.classList.add('d-none');
            convertInfo.textContent = '';
        }

        if (typeof updateVersionWizardActionState === 'function') {
            updateVersionWizardActionState();
        }
        updateConvertBtn();
    }

    return {
        initialize,
        handleCheckProjectTemplatesClick,
        handleVersionWizardApplyClick,
    };
}
