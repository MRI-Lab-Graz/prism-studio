export function createSurveyWorkflowPreviewController({
    convertError,
    convertInfo,
    surveyVersionWizardApplyBtn,
    convertApplyValueOffsetsBtn,
    convertIdMapFile,
    convertSessionColumnOverride,
    convertRunColumnOverride,
    convertLanguage,
    convertDatasetName,
    conversionLogContainer,
    conversionLogBody,
    toggleLogBtn,
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
    clearSurveyPreviewSelectionState,
    resetConversionUI,
    getEffectiveNearMatchTasks,
    getEffectiveTaskValueOffsets,
    ensureSurveyAdvancedOptionsVisible,
    focusTaskValueOffsetEditor,
    getSurveyPreviewContextKey,
    getSelectedSurveyFilename,
    getSelectedSurveyFile,
    isAdvancedOptionsEnabled,
    refreshSurveyColumnsBeforeRun,
    setActiveSurveyRun,
    startSurveyRunProgress,
    setIsPreviewRunning,
    appendSurveyInputToFormData,
    getSurveySessionValue,
    getSelectedSeparator,
    appendTemplateVersionSelections,
    appendLog,
    formatSignedOffset,
    setTemplateWorkflowGate,
    getTemplateWorkflowGate,
    getConvertServerFilePath,
    advanceSurveyRunProgress,
    parseJsonResponse,
    displayUnmatchedGroupsError,
    populateSurveySessionPickerFromDetected,
    getParticipantRegistryWarning,
    setSurveyPreviewSelectionState,
    displayConversionSummary,
    normalizeSurveyTaskName,
    displayValidationResults,
    formatVersionWizardRunLabel,
    showParticipantRegistryWarning,
    buildVersionWizard,
    hideVersionWizard,
    enrichSurveyRunErrorMessage,
    isAbortError,
    clearActiveSurveyRun,
    finishSurveyRunProgress,
    getActiveRunMode,
    getActiveRunCancelledByUser,
    getVersionWizardRetryGateMode,
    setVersionWizardRetryGateMode,
}) {
    async function handlePreviewClick() {
        setVersionWizardRetryGateMode(null);
        let templateWorkflowGate = getTemplateWorkflowGate();
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

        clearSurveyPreviewSelectionState();
        resetConversionUI();
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
        let previewRunOutcome = 'running';
        const previewContextKey = getSurveyPreviewContextKey();

        const filenameRaw = getSelectedSurveyFilename();
        if (!filenameRaw) {
            return;
        }
        const file = getSelectedSurveyFile();

        // Validate ID map before sending
        const idMap = isAdvancedOptionsEnabled() && convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
        if (idMap) {
            // Just check that a file is selected; don't read it (avoids stream issues)
            console.log(`[CLIENT DEBUG] ID map file selected: ${idMap.name} (size: ${idMap.size} bytes, type: ${idMap.type})`);
            if (idMap.size === 0) {
                convertError.classList.remove('d-none');
                convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>ID map file is empty';
                return;
            }
        }

        await refreshSurveyColumnsBeforeRun();

        // Validate ID column selection for non-PRISM data
        const previewIdCol = document.getElementById('convertIdColumn')?.value;
        if (!window._isPrismData && (!previewIdCol || previewIdCol === 'auto' || previewIdCol === '')) {
            convertError.classList.remove('d-none');
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Please select a participant ID column before previewing.';
            const idSelect = document.getElementById('convertIdColumn');
            if (idSelect) {
                idSelect.classList.add('border-danger');
                idSelect.focus();
            }
            return;
        }

        const previewRunAbortController = new AbortController();
        setActiveSurveyRun('preview', previewRunAbortController);
        setIsPreviewRunning(true);
        updateConvertBtn();
        startSurveyRunProgress('preview');
        const preparation = await surveyWorkflowPrepareController.prepareSurveyWorkflow({
            mode: 'preview',
            nearMatchTasks: selectedNearMatchTasks,
            valueOffsets: selectedValueOffsets,
            signal: previewRunAbortController.signal,
        });
        if (!preparation.ready) {
            surveyWorkflowPrepareController.finishPreparationPhase('preview', preparation.outcome);
            return;
        }
        selectedNearMatchTasks = preparation.nearMatchTasks;
        selectedValueOffsets = preparation.valueOffsets;
        allowNearItemMatch = selectedNearMatchTasks.length > 0;

        const formData = new FormData();
        appendSurveyInputToFormData(formData);

        if (idMap) {
            console.log(`[CLIENT DEBUG] About to append id_map to FormData: ${idMap.name} (size: ${idMap.size} bytes)`);
            formData.append('id_map', idMap);
            console.log('[CLIENT DEBUG] Successfully appended id_map to FormData');
        }

        // Add ID column if selected
        if (previewIdCol && previewIdCol !== 'auto' && previewIdCol !== '') {
            formData.append('id_column', previewIdCol);
        }

        const sessionVal = getSurveySessionValue();
        if (sessionVal) {
            formData.append('session', sessionVal);
        }

        // Append session/run column overrides if user has specified them
        const previewSessionColVal = (convertSessionColumnOverride && convertSessionColumnOverride.value.trim()) || '';
        const previewRunColVal = (convertRunColumnOverride && convertRunColumnOverride.value.trim()) || '';
        if (previewSessionColVal) {
            formData.append('session_column', previewSessionColVal);
        }
        if (previewRunColVal) {
            formData.append('run_column', previewRunColVal);
        }

        formData.append('language', (isAdvancedOptionsEnabled() && convertLanguage) ? convertLanguage.value : 'auto');
        formData.append('separator', getSelectedSeparator(filenameRaw.toLowerCase()));
        if (isAdvancedOptionsEnabled() && convertDatasetName && convertDatasetName.value.trim()) {
            formData.append('survey', convertDatasetName.value.trim());
        }
        const templateSelections = appendTemplateVersionSelections(formData);

        // Default: run validation in preview
        formData.append('validate', 'true');
        formData.append('prepared_workflow', 'true');
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
        templateWorkflowGate = null;
        setTemplateWorkflowGate(null);

        // Show log container
        conversionLogContainer.classList.remove('d-none');
        conversionLogBody.classList.remove('d-none');
        const icon = toggleLogBtn.querySelector('i');
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');

        appendLog('🔍 PREVIEW MODE (Dry-Run)', 'info');
        appendLog('═══════════════════════════════════════', 'info');
        appendLog(`Analyzing file: ${filenameRaw}`, 'step');
        if (idMap) {
            appendLog(`With ID map: ${idMap.name}`, 'step');
        }
        if (templateSelections.length > 0) {
            appendLog(`Template versions: ${templateSelections.map((entry) => `${entry.task}${entry.session ? `;session=${entry.session}` : ''}${entry.run ? `;run=${entry.run}` : ''}=${entry.version}`).join(', ')}`, 'step');
        }
        appendLog('Preview only — no files will be written to disk.', 'info');
        appendLog('', 'info');

        console.log('[CLIENT DEBUG] FormData ready, sending to /api/survey-convert-preview');
        console.log('[CLIENT DEBUG] FormData contains:', {
            excel: file ? file.name : null,
            excel_size: file ? file.size : null,
            source_file_path: file ? null : getConvertServerFilePath(),
            id_map: idMap ? idMap.name : null,
            id_map_size: idMap ? idMap.size : null
        });
        advanceSurveyRunProgress('preview', 20, 'Uploading file and starting preview...');

        fetch('/api/survey-convert-preview', {
            method: 'POST',
            body: formData,
            signal: previewRunAbortController.signal,
        })
            .then(async response => {
                const data = await parseJsonResponse(response, 'Survey preview');
                advanceSurveyRunProgress('preview', 38, 'Server response received. Building preview summary...');

                // DEBUG: Log the FULL response to understand structure
                console.log('[SURVEY-PREVIEW FULL RESPONSE]', data);
                console.log('[SURVEY-PREVIEW RESPONSE]', {
                    status: response.ok,
                    detected_sessions: data.detected_sessions,
                    session_column: data.session_column,
                    has_preview: !!data.preview,
                    all_keys: Object.keys(data)
                });

                if (!response.ok) {
                    if (data.error === 'workflow_preparation_stale') {
                        previewRunOutcome = 'action_required';
                        surveyWorkflowPrepareController.handleLateSetupBlocker('preview', data, selectedValueOffsets);
                        return null;
                    }
                    if (data.error === 'id_column_required') {
                        const idSelect = document.getElementById('convertIdColumn');
                        if (idSelect) {
                            idSelect.classList.add('border-danger');
                            idSelect.focus();
                        }
                        throw new Error('Please select the participant ID column.');
                    }
                    if (data.error === 'unmatched_groups') {
                        previewRunOutcome = 'action_required';
                        displayUnmatchedGroupsError(data);
                        return null;
                    }
                    templateWorkflowGate = null;
                    setTemplateWorkflowGate(null);
                    setTemplateEditorErrorCtaVisible(false);
                    throw new Error(data.error || 'Preview failed');
                }

                advanceSurveyRunProgress('preview', 65, 'Processing preview details and validation results...');

                const sessionsLoaded = populateSurveySessionPickerFromDetected(data.detected_sessions);
                if (sessionsLoaded) {
                    appendLog(`✓ Sessions auto-detected: ${data.detected_sessions.join(', ')}`, 'success');
                } else if (data.session_column) {
                    appendLog(`⚠ Session column '${data.session_column}' found but no sessions detected. Enter session manually.`, 'warning');
                }

                // Update "Auto-detect" option label with what was actually detected
                if (convertSessionColumnOverride) {
                    const autoOpt = convertSessionColumnOverride.querySelector('option[value=""]');
                    if (autoOpt) autoOpt.textContent = data.session_column ? `Auto-detect (${data.session_column})` : 'Auto-detect';
                }
                if (convertRunColumnOverride) {
                    const autoOpt = convertRunColumnOverride.querySelector('option[value=""]');
                    if (autoOpt) autoOpt.textContent = data.run_column ? `Auto-detect (${data.run_column})` : 'Auto-detect';
                }

                const preview = data.preview;
                const participantRegistryWarning = getParticipantRegistryWarning(data);

                if (!preview) {
                    previewRunOutcome = 'action_required';
                    appendLog('⚠ No preview data received', 'warning');
                    return;
                }

                // Display summary
                appendLog('📊 SUMMARY', 'info');
                appendLog(`   Total participants: ${preview.summary.total_participants}`, 'info');
                appendLog(`   Unique participants: ${preview.summary.unique_participants}`, 'info');
                appendLog(`   Tasks detected: ${preview.summary.tasks.join(', ')}`, 'info');
                if (preview.summary.session_column) {
                    appendLog(`   Session column: ${preview.summary.session_column}`, 'info');
                }
                if (preview.summary.run_column) {
                    appendLog(`   Run column: ${preview.summary.run_column}`, 'info');
                }
                const totalFilesToCreate =
                    preview.summary.total_files ??
                    preview.summary.total_files_to_create ??
                    preview.summary.files_created ??
                    (Array.isArray(preview.files_to_create) ? preview.files_to_create.length : 'n/a');
                appendLog(`   Total files to create: ${totalFilesToCreate}`, 'info');
                appendLog('', 'info');

                const previewFiles = Array.isArray(preview.files_to_create)
                    ? preview.files_to_create.map(fileEntry => {
                        if (typeof fileEntry === 'string') {
                            return {
                                type: 'data',
                                path: fileEntry,
                                description: 'Survey data file'
                            };
                        }
                        return {
                            type: fileEntry.type || 'data',
                            path: fileEntry.path || '',
                            description: fileEntry.description || 'Survey data file'
                        };
                    })
                    : [];

                let validationSummaryErrors = 0;
                let validationSummaryWarnings = 0;
                let validationRuntimeError = '';
                const previewSurveyTasks = Array.isArray(data.survey_tasks) ? data.survey_tasks : [];
                const previewManualReviewTasks = previewSurveyTasks.filter((entry) => entry && entry.manual_review_required);

                // Display conversion summary (template matches, tool columns, unmatched) before validation
                if (data.conversion_summary) {
                    setSurveyPreviewSelectionState(previewSurveyTasks, previewContextKey);
                    displayConversionSummary(data.conversion_summary);
                } else {
                    setSurveyPreviewSelectionState(previewSurveyTasks, previewContextKey);
                }

                if (previewManualReviewTasks.length > 0) {
                    appendLog(`Survey review: ${previewManualReviewTasks.length} survey(s) still contain out-of-range values.`, 'warning');
                    previewManualReviewTasks.forEach((entry) => {
                        const task = normalizeSurveyTaskName(entry && entry.task);
                        const review = entry && entry.out_of_range ? entry.out_of_range : null;
                        const detail = review && review.message
                            ? ` ${review.message}`
                            : '';
                        appendLog(`   • ${task}${detail}`, 'warning');
                    });
                    appendLog('   Review the Preview Review list above. Deselect those surveys or use Advanced options if the offset is truly structural.', 'warning');
                    appendLog('', 'info');
                }

                if (data.workflow_gate && data.workflow_gate.blocked) {
                    templateWorkflowGate = data.workflow_gate;
                    setTemplateWorkflowGate(templateWorkflowGate);
                    setTemplateEditorErrorCtaVisible(true);
                    appendLog('Template metadata updates are required before import.', 'warning');
                    appendLog(`   ${data.workflow_gate.message}`, 'warning');
                    if (Array.isArray(data.workflow_gate.next_steps)) {
                        data.workflow_gate.next_steps.forEach(step => appendLog(`   • ${step}`, 'warning'));
                    }
                } else {
                    templateWorkflowGate = null;
                    setTemplateWorkflowGate(null);
                    setTemplateEditorErrorCtaVisible(false);
                }

                // Show validation results if backend ran validation during preview
                if (data.validation) {
                    const v = data.validation;
                    const errorCount = (v.errors || []).length;
                    const warningCount = (v.warnings || []).length;
                    const parsedSummaryErrors = v.summary ? Number(v.summary.total_errors) : NaN;
                    const parsedSummaryWarnings = v.summary ? Number(v.summary.total_warnings) : NaN;
                    const summaryErrors = Number.isFinite(parsedSummaryErrors)
                        ? parsedSummaryErrors
                        : errorCount;
                    const summaryWarnings = Number.isFinite(parsedSummaryWarnings)
                        ? parsedSummaryWarnings
                        : warningCount;

                    validationSummaryErrors = summaryErrors;
                    validationSummaryWarnings = summaryWarnings;
                    validationRuntimeError = typeof v.error === 'string' ? v.error.trim() : '';

                    if (summaryErrors === 0 && summaryWarnings === 0) {
                        appendLog('✓ Validation (preview) passed - dataset is valid!', 'success');
                    } else if (summaryErrors === 0) {
                        appendLog(`⚠ Validation (preview) passed with ${summaryWarnings} warning(s)`, 'warning');
                    } else {
                        appendLog(`✗ Validation (preview) failed with ${summaryErrors} error(s)`, 'error');
                    }

                    if (summaryErrors > 0) {
                        let printed = 0;
                        const maxToShow = 20;

                        if (v.formatted && Array.isArray(v.formatted.errors)) {
                            for (const group of v.formatted.errors) {
                                for (const fileIssue of (group.files || [])) {
                                    if (printed >= maxToShow) break;
                                    const msg = (fileIssue && fileIssue.message) ? fileIssue.message : (group.message || 'Validation error');
                                    appendLog(`  - ${msg}`, 'error');
                                    printed++;
                                }
                                if (printed >= maxToShow) break;
                            }
                        }

                        if (printed === 0 && Array.isArray(v.errors)) {
                            for (const err of v.errors) {
                                if (printed >= maxToShow) break;
                                if (typeof err === 'string') {
                                    appendLog(`  - ${err}`, 'error');
                                    printed++;
                                }
                            }
                        }

                        if (summaryErrors > printed) {
                            appendLog(`  ... and ${summaryErrors - printed} more errors (see details below)`, 'error');
                        }
                    }

                    if (summaryWarnings > 0) {
                        appendLog(`⚠ ${summaryWarnings} warning(s) found`, 'warning');
                    }

                    if (validationRuntimeError) {
                        appendLog(`✗ Validation preview backend issue: ${validationRuntimeError}`, 'error');
                    }

                    displayValidationResults(data.validation);
                    appendLog('', 'info');
                }

                // Display data issues
                if (preview.data_issues && preview.data_issues.length > 0) {
                    appendLog(`Data issues found (${preview.data_issues.length})`, 'warning');
                    appendLog('   Fix these issues before conversion:', 'warning');
                    appendLog('', 'warning');

                    preview.data_issues.slice(0, 10).forEach(issue => {
                        const severity = issue.severity.toUpperCase();
                        appendLog(`   [${severity}] ${issue.type}`, 'warning');
                        appendLog(`   → ${issue.message}`, 'warning');

                        if (issue.type === 'duplicate_ids' && issue.details) {
                            const dups = Object.keys(issue.details).slice(0, 5);
                            appendLog(`   → Duplicates: ${dups.join(', ')}`, 'warning');
                        } else if (issue.type === 'unexpected_values') {
                            appendLog(`   → Column: ${issue.column} (task: ${issue.task}, item: ${issue.item})`, 'warning');
                            if (issue.unexpected) {
                                appendLog(`   → Unexpected values: ${issue.unexpected.slice(0, 5).join(', ')}`, 'warning');
                            }
                        } else if (issue.type === 'out_of_range') {
                            appendLog(`   → Column: ${issue.column} (task: ${issue.task}, item: ${issue.item})`, 'warning');
                            appendLog(`   → Expected range: ${issue.range}`, 'warning');
                            appendLog(`   → Out of range count: ${issue.out_of_range_count}`, 'warning');
                        } else if (issue.type === 'missing_from_participants_tsv') {
                            if (issue.details) {
                                appendLog(`   → ${issue.details}`, 'warning');
                            }
                            if (issue.next_step) {
                                appendLog(`   → ${issue.next_step}`, 'warning');
                            }
                        }
                        appendLog('', 'warning');
                    });

                    if (preview.data_issues.length > 10) {
                        appendLog(`   ... and ${preview.data_issues.length - 10} more issues`, 'warning');
                    }
                    appendLog('', 'info');
                } else {
                    appendLog('✓ No data issues detected', 'success');
                    appendLog('', 'info');
                }

                if (typeof window.setParticipantsAdditionalVariablesEnabled === 'function') {
                    window.setParticipantsAdditionalVariablesEnabled(false);
                }

                // Display participants.tsv preview
                if (preview.participants_tsv && Object.keys(preview.participants_tsv).length > 0) {
                    const tsv = preview.participants_tsv;
                    window.lastPreviewData = preview;
                    const hasAdditionalVariableCandidates = Boolean(tsv.unused_columns && tsv.unused_columns.length > 0);
                    if (typeof window.setParticipantsAdditionalVariablesEnabled === 'function') {
                        window.setParticipantsAdditionalVariablesEnabled(hasAdditionalVariableCandidates);
                    }

                    appendLog('📝 PARTICIPANTS.TSV PREVIEW', 'info');
                    appendLog('   This file will be created with the following structure:', 'info');
                    appendLog('', 'info');

                    appendLog(`   Columns (${tsv.columns.length} total):`, 'info');
                    tsv.columns.forEach(col => {
                        appendLog(`     • ${col}`, 'info');
                    });

                    if (Object.keys(tsv.mappings).length > 0) {
                        appendLog('', 'info');
                        appendLog('   Column Mappings:', 'info');
                        Object.entries(tsv.mappings).forEach(([outputCol, mappingInfo]) => {
                            const hasMapping = mappingInfo.has_value_mapping;
                            const indicator = hasMapping ? '🔄' : '✓';
                            appendLog(`     ${indicator} ${outputCol} ← ${mappingInfo.source_column}`, 'info');
                            if (hasMapping && Object.keys(mappingInfo.value_mapping).length > 0) {
                                appendLog('        (has value transformation mapping)', 'info');
                            }
                        });
                    }

                    if (tsv.sample_rows.length > 0) {
                        appendLog('', 'info');
                        const sampleCount = Math.min(5, tsv.sample_rows.length);
                        appendLog(`   Sample Data (showing first ${sampleCount} of ${tsv.total_rows} participants):`, 'info');
                        appendLog(`   ${'-'.repeat(100)}`, 'info');
                        const header = tsv.columns.map(col => col.padEnd(20)).join(' | ');
                        appendLog(`   ${header}`, 'info');
                        appendLog(`   ${'-'.repeat(100)}`, 'info');
                        tsv.sample_rows.slice(0, 5).forEach(rowData => {
                            const row = tsv.columns.map(col => String(rowData[col] || 'n/a').padEnd(20)).join(' | ');
                            appendLog(`   ${row}`, 'info');
                        });
                        if (tsv.sample_rows.length > 5) {
                            appendLog(`   ... and ${tsv.sample_rows.length - 5} more rows shown above (total ${tsv.total_rows} participants)`, 'info');
                        }
                        appendLog(`   ${'-'.repeat(100)}`, 'info');
                    }

                    if (tsv.notes.length > 0) {
                        appendLog('', 'info');
                        appendLog('   📌 Notes:', 'info');
                        tsv.notes.forEach(note => {
                            appendLog(`     • ${note}`, 'info');
                        });
                    }

                    if (tsv.unused_columns && tsv.unused_columns.length > 0) {
                        appendLog('', 'info');
                        appendLog(`   Unused columns (${tsv.unused_columns.length} available for participants.tsv):`, 'warning');
                        appendLog('      These columns are not being imported as survey data and could be included', 'warning');
                        appendLog('      in participants.tsv if you create/update participants_mapping.json:', 'warning');
                        tsv.unused_columns.slice(0, 10).forEach(item => {
                            if (typeof item === 'object') {
                                const fieldCode = item.field_code || '';
                                const description = item.description || '';
                                appendLog(`      • ${fieldCode}`, 'warning');
                                if (description) {
                                    appendLog(`        ↳ ${description}`, 'warning');
                                }
                            } else {
                                appendLog(`      • ${item}`, 'warning');
                            }
                        });
                        if (tsv.unused_columns.length > 10) {
                            appendLog(`      ... and ${tsv.unused_columns.length - 10} more columns`, 'warning');
                        }
                        appendLog('', 'info');
                        appendLog('   💡 TIP: Click "Add Additional Variables (Optional)", save the mapping, then run "2. Extract & Convert" to apply it.', 'info');
                    }
                    appendLog('', 'info');
                }

                // Display participant preview
                appendLog('👥 PARTICIPANT PREVIEW (first 10)', 'info');
                preview.participants.slice(0, 10).forEach(p => {
                    const completeness = p.completeness_percent;
                    const status = completeness > 80 ? '✓' : (completeness > 50 ? '⚠' : '✗');
                    const hasRun = p.run_id !== null && p.run_id !== undefined && p.run_id !== '';
                    const runLabel = hasRun ? `, ${formatVersionWizardRunLabel(p.run_id)}` : '';
                    appendLog(`   ${status} ${p.participant_id} (${p.session_id}${runLabel})`, 'info');
                    appendLog(`      Raw ID: ${p.raw_id}`, 'info');
                    appendLog(`      Completeness: ${completeness}% (${p.total_items - p.missing_values}/${p.total_items} items)`, 'info');
                });

                if (preview.participants.length > 10) {
                    appendLog(`   ... and ${preview.participants.length - 10} more participants`, 'info');
                }
                appendLog('', 'info');

                // Display column mapping preview
                appendLog('📋 COLUMN MAPPING (first 15)', 'info');
                const cols = Object.entries(preview.column_mapping).slice(0, 15);
                if (cols.length === 0) {
                    appendLog('   (no mapped survey columns available in preview)', 'info');
                } else {
                    cols.forEach(([col, info]) => {
                        const runInfo = info.run ? ` (run ${info.run})` : '';
                        const status = info.has_unexpected_values ? '⚠' : '✓';
                        appendLog(`   ${status} ${col}`, 'info');
                        appendLog(`      → Task: ${info.task}${runInfo}, Item: ${info.base_item}`, 'info');
                        appendLog(`      → Missing: ${info.missing_percent}% (${info.missing_count} values)`, 'info');
                        if (info.has_unexpected_values) {
                            appendLog('      ⚠ Has unexpected values!', 'warning');
                        }
                    });
                }

                if (Object.keys(preview.column_mapping).length > 15) {
                    appendLog(`   ... and ${Object.keys(preview.column_mapping).length - 15} more columns`, 'info');
                }
                appendLog('', 'info');

                // Display file structure
                appendLog('📁 FILES TO CREATE', 'info');
                const fileTypes = {};
                previewFiles.forEach(f => {
                    fileTypes[f.type] = (fileTypes[f.type] || 0) + 1;
                });

                appendLog(`   Metadata files: ${fileTypes.metadata || 0}`, 'info');
                appendLog(`   Sidecar files: ${fileTypes.sidecar || 0}`, 'info');
                appendLog(`   Data files: ${fileTypes.data || 0}`, 'info');
                appendLog('', 'info');

                appendLog('   Sample files:', 'info');
                const shownByType = { metadata: 0, sidecar: 0, data: 0 };
                previewFiles.forEach(f => {
                    if (shownByType[f.type] < 3) {
                        appendLog(`   - ${f.path}`, 'info');
                        appendLog(`     ${f.description}`, 'info');
                        shownByType[f.type]++;
                    }
                });

                appendLog('', 'info');
                appendLog('═══════════════════════════════════════', 'info');

                let previewErrorCount = validationSummaryErrors;
                let previewWarningCount = validationSummaryWarnings;

                if (validationRuntimeError && previewErrorCount === 0 && previewWarningCount === 0) {
                    previewErrorCount = 1;
                }

                const dataIssueCount = preview.data_issues ? preview.data_issues.length : 0;
                const surveyReviewCount = previewManualReviewTasks.length;
                if (dataIssueCount > 0) {
                    previewWarningCount += dataIssueCount;
                }
                if (surveyReviewCount > 0) {
                    previewWarningCount += surveyReviewCount;
                }

                console.log(`Counts - Errors: ${previewErrorCount}, Warnings: ${previewWarningCount}`);

                if (templateWorkflowGate && templateWorkflowGate.blocked) {
                    previewRunOutcome = 'action_required';
                    appendLog('Preview paused: update copied template metadata first.', 'warning');
                    appendLog(`   ${templateWorkflowGate.issue_count || previewErrorCount || 1} template item(s) need edits before import`, 'warning');
                    convertInfo.innerHTML = '<i class="fas fa-clipboard-check me-2"></i>Some copied survey templates still need project-level metadata. Complete them in Template Editor, then run Preview again.';
                    setTemplateEditorErrorCtaVisible(true);
                } else if (previewErrorCount > 0) {
                    previewRunOutcome = 'action_required';
                    appendLog('Preview complete: validation issues found.', 'warning');
                    appendLog(`   ${previewErrorCount} error(s) must be fixed before converting`, 'error');
                    if (previewWarningCount > 0) {
                        appendLog(`   ${previewWarningCount} warning(s)`, 'warning');
                    }
                    if (dataIssueCount > 0) {
                        appendLog(`   ${dataIssueCount} data issue(s)`, 'warning');
                    }
                    convertInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Preview completed, but validation found errors. Fix these issues before converting.';
                    setTemplateEditorErrorCtaVisible(true);
                } else if (previewWarningCount > 0 || dataIssueCount > 0) {
                    previewRunOutcome = 'success';
                    appendLog('✓ Preview completed (with warnings)', 'warning');
                    if (previewWarningCount > 0) {
                        appendLog(`   ${previewWarningCount} warning(s) - review recommended`, 'warning');
                    }
                    if (dataIssueCount > 0) {
                        appendLog(`   ${dataIssueCount} data issue(s)`, 'warning');
                    }
                    if (surveyReviewCount > 0) {
                        appendLog(`   ${surveyReviewCount} survey review item(s)`, 'warning');
                    }
                    convertInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Preview completed with warnings. Review above before converting.';
                    setTemplateEditorErrorCtaVisible(false);
                } else {
                    previewRunOutcome = 'success';
                    appendLog('✓ Preview completed successfully', 'success');
                    convertInfo.innerHTML = '<i class="fas fa-info-circle me-2"></i>Preview complete. Review the log above, then click <strong>Convert</strong> to proceed.';
                    setTemplateEditorErrorCtaVisible(false);
                }

                if (!(templateWorkflowGate && templateWorkflowGate.blocked) && participantRegistryWarning) {
                    const prefix = previewErrorCount > 0
                        ? 'Preview found additional issues.'
                        : 'Preview completed with a participant registry warning.';
                    showParticipantRegistryWarning(prefix, participantRegistryWarning);
                }

                // Re-print all errors and warnings at the bottom.
                if (previewErrorCount > 0 || previewWarningCount > 0 || validationRuntimeError) {
                    appendLog('', 'info');
                    appendLog('─── ISSUES RECAP ───────────────────────────────', 'warning');

                    // Validation errors
                    if (data.validation) {
                        const v = data.validation;
                        let recapPrinted = 0;
                        const recapMax = 30;

                        if (v.formatted && Array.isArray(v.formatted.errors)) {
                            for (const group of v.formatted.errors) {
                                for (const fileIssue of (group.files || [])) {
                                    if (recapPrinted >= recapMax) break;
                                    const msg = (fileIssue && fileIssue.message) ? fileIssue.message : (group.message || 'Validation error');
                                    appendLog(`  ✗ ${msg}`, 'error');
                                    recapPrinted++;
                                }
                                if (recapPrinted >= recapMax) break;
                            }
                        }

                        if (recapPrinted === 0 && Array.isArray(v.errors)) {
                            for (const err of v.errors) {
                                if (recapPrinted >= recapMax) break;
                                if (typeof err === 'string') {
                                    appendLog(`  ✗ ${err}`, 'error');
                                    recapPrinted++;
                                }
                            }
                        }

                        if (validationSummaryErrors > recapPrinted) {
                            appendLog(`  ... and ${validationSummaryErrors - recapPrinted} more error(s) — scroll up for the full list`, 'error');
                        }

                        // Validation warnings
                        if (v.formatted && Array.isArray(v.formatted.warnings)) {
                            let warnPrinted = 0;
                            for (const group of v.formatted.warnings) {
                                for (const fileIssue of (group.files || [])) {
                                    if (warnPrinted >= recapMax) break;
                                    const msg = (fileIssue && fileIssue.message) ? fileIssue.message : (group.message || 'Validation warning');
                                    appendLog(`  ⚠ ${msg}`, 'warning');
                                    warnPrinted++;
                                }
                                if (warnPrinted >= recapMax) break;
                            }
                            if (validationSummaryWarnings > warnPrinted && warnPrinted > 0) {
                                appendLog(`  ... and ${validationSummaryWarnings - warnPrinted} more warning(s) — scroll up for the full list`, 'warning');
                            }
                        } else if (validationSummaryWarnings > 0 && Array.isArray(v.warnings)) {
                            let warnPrinted = 0;
                            for (const w of v.warnings) {
                                if (warnPrinted >= recapMax) break;
                                if (typeof w === 'string') {
                                    appendLog(`  ⚠ ${w}`, 'warning');
                                    warnPrinted++;
                                }
                            }
                        }

                        if (validationRuntimeError) {
                            appendLog(`  ✗ Backend issue: ${validationRuntimeError}`, 'error');
                        }
                    }

                    // Data issues
                    if (preview.data_issues && preview.data_issues.length > 0) {
                        preview.data_issues.forEach(issue => {
                            const sev = issue.severity === 'error' ? '✗' : '⚠';
                            const level = issue.severity === 'error' ? 'error' : 'warning';
                            appendLog(`  ${sev} [${issue.type}] ${issue.message}`, level);
                        });
                    }

                    appendLog('────────────────────────────────────────────────', 'warning');
                }

                appendLog('═══════════════════════════════════════', 'info');

                // Show version plan wizard for multi-variant questionnaires detected during preview
                const mvTasks = (data && typeof data.multivariant_tasks === 'object' && data.multivariant_tasks)
                    ? data.multivariant_tasks : {};
                if (Object.keys(mvTasks).length > 0) {
                    buildVersionWizard(
                        mvTasks,
                        (data && typeof data.task_runs === 'object' && data.task_runs)
                        || (data.conversion_summary && typeof data.conversion_summary.task_runs === 'object' && data.conversion_summary.task_runs)
                        || {},
                        (preview && Array.isArray(preview.participants)) ? preview.participants : [],
                        Array.isArray(data.detected_sessions) ? data.detected_sessions : []
                    );
                    appendLog(`Multi-version questionnaire(s) detected: ${Object.keys(mvTasks).join(', ')}. Adjust the version selector below if needed.`, 'info');
                } else {
                    hideVersionWizard();
                }

                convertInfo.classList.remove('d-none');
                if (previewRunOutcome === 'running') {
                    previewRunOutcome = 'success';
                }
                advanceSurveyRunProgress('preview', 100, 'Preview completed.');
            })
            .catch(err => {
                if (isAbortError(err)) {
                    previewRunOutcome = 'canceled';
                    appendLog('Preview canceled by user.', 'warning');
                    convertError.classList.add('d-none');
                    convertInfo.textContent = 'Preview canceled.';
                    convertInfo.classList.remove('d-none');
                    return;
                }
                previewRunOutcome = 'error';
                const enrichedMessage = enrichSurveyRunErrorMessage(err.message);
                appendLog(`Error: ${enrichedMessage}`, 'error');
                if (enrichedMessage !== err.message) {
                    appendLog('Tip: Save the spreadsheet in Excel and re-select it before running again.', 'warning');
                }
                convertError.textContent = enrichedMessage;
                convertError.classList.remove('d-none');
                setTemplateEditorErrorCtaVisible(Boolean(templateWorkflowGate && templateWorkflowGate.blocked));
            })
            .finally(() => {
                setIsPreviewRunning(false);
                const canceledByUser = getActiveRunMode() === 'preview' && getActiveRunCancelledByUser();
                clearActiveSurveyRun('preview');
                const blockedByVersionWizardGate = getVersionWizardRetryGateMode() === 'preview';
                if (previewRunOutcome === 'running') {
                    previewRunOutcome = blockedByVersionWizardGate ? 'paused' : 'canceled';
                }
                if (canceledByUser && previewRunOutcome !== 'success') {
                    previewRunOutcome = 'canceled';
                }
                finishSurveyRunProgress('preview', previewRunOutcome);
                updateConvertBtn();
            });
    }

    return {
        handlePreviewClick,
    };
}
