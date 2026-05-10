export function createSurveyValueOffsetEditorController({
    convertAdvancedToggle,
    convertDatasetName,
    convertLanguage,
    convertIdMapFile,
    clearIdMapFileBtn,
    convertValueOffsets,
    convertValueOffsetsEditor,
    convertValueOffsetRows,
    convertAddValueOffsetRowBtn,
    convertApplyValueOffsetsBtn,
    convertValueOffsetsKnownTasks,
    convertValueOffsetsEmptyState,
    convertValueOffsetsStatus,
    convertValueOffsetAdvice,
    convertError,
    isAdvancedOptionsEnabled,
    getIsConvertRunning,
    getIsPreviewRunning,
    getAppliedTaskValueOffsetSelectionSignature,
    setAppliedTaskValueOffsetSelectionSignature,
    updateConvertBtn,
    getNextTaskValueOffsetRowId,
    getSurveyPreviewSelectionState,
    getTemplateVersionSelections,
    getLastPreviewSurveyTasks,
    getTaskValueOffsetEditorState,
    setTaskValueOffsetEditorState,
    normalizeSurveyTaskName,
    parseTaskValueOffsetsText,
    normalizeTaskValueOffsets,
    parseNumericOffsetValue,
    formatOffsetMagnitude,
    formatSignedOffset,
    escapeHtml,
}) {
    function getAvailableSurveyTasksForValueOffsets() {
        const ordered = [];
        const seen = new Set();
        const pushTask = (value) => {
            const task = normalizeSurveyTaskName(value);
            if (!task || seen.has(task)) {
                return;
            }
            seen.add(task);
            ordered.push(task);
        };

        const selectionState = (typeof getSurveyPreviewSelectionState === 'function')
            ? getSurveyPreviewSelectionState()
            : {};
        const selectedTasks = Array.isArray(selectionState && selectionState.selectedTasks)
            ? selectionState.selectedTasks
            : [];
        const availableTasks = Array.isArray(selectionState && selectionState.availableTasks)
            ? selectionState.availableTasks
            : [];
        selectedTasks.forEach(pushTask);
        availableTasks.forEach(pushTask);

        const templateSelections = (typeof getTemplateVersionSelections === 'function')
            ? getTemplateVersionSelections()
            : [];
        templateSelections.forEach((entry) => pushTask(entry && entry.task));

        const previewTasks = (typeof getLastPreviewSurveyTasks === 'function')
            ? getLastPreviewSurveyTasks()
            : [];
        previewTasks.forEach((entry) => pushTask(entry && entry.task));

        getTaskValueOffsetEditorState().forEach((entry) => pushTask(entry && entry.task));

        return ordered;
    }

    function createTaskValueOffsetRow(task = '', offset = null) {
        const normalizedTask = normalizeSurveyTaskName(task);
        const parsedOffset = parseNumericOffsetValue(offset);
        const nextId = typeof getNextTaskValueOffsetRowId === 'function'
            ? getNextTaskValueOffsetRowId()
            : (getTaskValueOffsetEditorState().reduce((maxId, entry) => {
                return Math.max(maxId, Number(entry && entry.id) || 0);
            }, 0) + 1);
        return {
            id: nextId,
            task: normalizedTask,
            operator: parsedOffset !== null && parsedOffset < 0 ? '-' : '+',
            magnitude: parsedOffset !== null ? formatOffsetMagnitude(parsedOffset) : ''
        };
    }

    function getPreferredTaskValueOffsetTask() {
        const availableTasks = getAvailableSurveyTasksForValueOffsets();
        if (availableTasks.length === 0) {
            return '';
        }

        const usedTasks = new Set(
            getTaskValueOffsetEditorState()
                .map((entry) => normalizeSurveyTaskName(entry && entry.task))
                .filter(Boolean)
        );
        return availableTasks.find((task) => !usedTasks.has(task)) || availableTasks[0] || '';
    }

    function getTaskValueOffsetMapFromEditorState() {
        const normalized = {};
        getTaskValueOffsetEditorState().forEach((entry) => {
            const task = normalizeSurveyTaskName(entry && entry.task);
            const magnitude = parseNumericOffsetValue(entry && entry.magnitude);
            if (!task || magnitude === null) {
                return;
            }
            normalized[task] = entry && entry.operator === '-'
                ? -Math.abs(magnitude)
                : Math.abs(magnitude);
        });
        return normalized;
    }

    function getCurrentTaskValueOffsetSelectionSignature() {
        const offsets = Object.entries(getTaskValueOffsetMapFromEditorState())
            .map(([task, offset]) => [normalizeSurveyTaskName(task), Number(offset)])
            .filter(([task, offset]) => task && Number.isFinite(offset))
            .sort((left, right) => String(left[0]).localeCompare(String(right[0])));
        if (offsets.length === 0) {
            return '';
        }
        return JSON.stringify(offsets);
    }

    function hasManualTaskValueOffsets() {
        return Object.keys(getTaskValueOffsetMapFromEditorState()).length > 0;
    }

    function hasIncompleteTaskValueOffsetRows() {
        return getTaskValueOffsetEditorState().some((entry) => {
            const task = normalizeSurveyTaskName(entry && entry.task);
            const magnitudeRaw = String(entry && entry.magnitude ? entry.magnitude : '').trim();
            const parsedMagnitude = parseNumericOffsetValue(magnitudeRaw);
            return (Boolean(task) || Boolean(magnitudeRaw)) && (!task || parsedMagnitude === null);
        });
    }

    function hasAppliedTaskValueOffsetSelections() {
        if (!hasManualTaskValueOffsets()) {
            return true;
        }
        const currentSignature = getCurrentTaskValueOffsetSelectionSignature();
        const appliedSignature = typeof getAppliedTaskValueOffsetSelectionSignature === 'function'
            ? getAppliedTaskValueOffsetSelectionSignature()
            : '';
        return Boolean(
            currentSignature
            && appliedSignature
            && currentSignature === appliedSignature
        );
    }

    function getManualTaskValueOffsets() {
        if (!isAdvancedOptionsEnabled() || !convertValueOffsets) {
            return {};
        }
        if (convertValueOffsetRows) {
            syncTaskValueOffsetTextFromState();
            return getTaskValueOffsetMapFromEditorState();
        }
        return parseTaskValueOffsetsText(convertValueOffsets.value);
    }

    function syncTaskValueOffsetTextFromState() {
        if (!convertValueOffsets) {
            return;
        }
        const offsetMap = getTaskValueOffsetMapFromEditorState();
        convertValueOffsets.value = Object.entries(offsetMap)
            .map(([task, offset]) => `${task} = ${formatSignedOffset(offset)}`)
            .join('\n');
    }

    function renderTaskValueOffsetEditor() {
        if (!convertValueOffsetRows) {
            return;
        }

        const enabled = isAdvancedOptionsEnabled();
        const availableTasks = getAvailableSurveyTasksForValueOffsets();
        let editorState = getTaskValueOffsetEditorState();

        if (enabled && editorState.length === 0 && availableTasks.length > 0) {
            editorState = [createTaskValueOffsetRow(getPreferredTaskValueOffsetTask())];
            setTaskValueOffsetEditorState(editorState);
        }

        if (convertValueOffsetsKnownTasks) {
            convertValueOffsetsKnownTasks.textContent = availableTasks.length > 0
                ? `Available tasks: ${availableTasks.join(', ')}`
                : 'Run Preview to populate available survey tasks.';
        }

        if (convertAddValueOffsetRowBtn) {
            convertAddValueOffsetRowBtn.disabled = !enabled || availableTasks.length === 0;
        }

        if (convertValueOffsetsEditor) {
            convertValueOffsetsEditor.classList.toggle('opacity-75', !enabled);
        }

        if (editorState.length === 0) {
            convertValueOffsetRows.innerHTML = '';
            if (convertValueOffsetsEmptyState) {
                convertValueOffsetsEmptyState.textContent = availableTasks.length > 0
                    ? 'No offset rows configured yet.'
                    : 'Run Preview to populate available survey tasks.';
                convertValueOffsetsEmptyState.classList.remove('d-none');
            }
            return;
        }

        if (convertValueOffsetsEmptyState) {
            convertValueOffsetsEmptyState.classList.add('d-none');
        }

        const rowsHtml = editorState.map((entry) => {
            const optionTasks = [];
            const seenTasks = new Set();
            const pushTask = (value) => {
                const task = normalizeSurveyTaskName(value);
                if (!task || seenTasks.has(task)) {
                    return;
                }
                seenTasks.add(task);
                optionTasks.push(task);
            };

            pushTask(entry && entry.task);
            availableTasks.forEach(pushTask);

            const taskOptionsHtml = optionTasks.length > 0
                ? [
                    '<option value="">Choose survey task</option>',
                    ...optionTasks.map((task) => {
                        const selected = normalizeSurveyTaskName(entry && entry.task) === task ? ' selected' : '';
                        return `<option value="${escapeHtml(task)}"${selected}>${escapeHtml(task)}</option>`;
                    })
                ].join('')
                : '<option value="">Run Preview to populate tasks</option>';

            const operator = entry && entry.operator === '-' ? '-' : '+';
            const magnitude = entry && entry.magnitude ? escapeHtml(String(entry.magnitude)) : '';

            return `
                <div class="row g-2 align-items-end" data-offset-row-id="${entry.id}">
                    <div class="col-md-6">
                        <label class="form-label small mb-1" for="convertValueOffsetTask-${entry.id}">Task</label>
                        <select
                            class="form-select form-select-sm"
                            id="convertValueOffsetTask-${entry.id}"
                            data-role="task"
                            ${!enabled ? 'disabled' : ''}
                        >
                            ${taskOptionsHtml}
                        </select>
                    </div>
                    <div class="col-md-2 col-lg-2">
                        <label class="form-label small mb-1" for="convertValueOffsetOperator-${entry.id}">Operator</label>
                        <select
                            class="form-select form-select-sm"
                            id="convertValueOffsetOperator-${entry.id}"
                            data-role="operator"
                            ${!enabled ? 'disabled' : ''}
                        >
                            <option value="+" ${operator === '+' ? 'selected' : ''}>+</option>
                            <option value="-" ${operator === '-' ? 'selected' : ''}>-</option>
                        </select>
                    </div>
                    <div class="col-md-3 col-lg-3">
                        <label class="form-label small mb-1" for="convertValueOffsetMagnitude-${entry.id}">Value</label>
                        <input
                            type="number"
                            min="0"
                            step="any"
                            class="form-control form-control-sm"
                            id="convertValueOffsetMagnitude-${entry.id}"
                            data-role="magnitude"
                            placeholder="e.g. 1"
                            value="${magnitude}"
                            ${!enabled ? 'disabled' : ''}
                        />
                    </div>
                    <div class="col-md-1 col-lg-1 d-grid">
                        <button
                            type="button"
                            class="btn btn-outline-secondary btn-sm"
                            data-role="remove"
                            aria-label="Remove task value offset row"
                            ${!enabled ? 'disabled' : ''}
                        >
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        convertValueOffsetRows.innerHTML = rowsHtml;
        updateTaskValueOffsetApplyState();
    }

    function setTaskValueOffsetEditorStateFromText(rawText) {
        let parsed = {};
        try {
            parsed = parseTaskValueOffsetsText(rawText);
        } catch (error) {
            console.warn('Could not parse seeded task value offsets:', error);
        }

        const nextState = Object.entries(normalizeTaskValueOffsets(parsed))
            .map(([task, offset]) => createTaskValueOffsetRow(task, offset));
        setTaskValueOffsetEditorState(nextState);
        renderTaskValueOffsetEditor();
        syncTaskValueOffsetTextFromState();
        updateTaskValueOffsetApplyState();
    }

    function clearTaskValueOffsetEditorState() {
        setTaskValueOffsetEditorState([]);
        if (typeof setAppliedTaskValueOffsetSelectionSignature === 'function') {
            setAppliedTaskValueOffsetSelectionSignature('');
        }
        renderTaskValueOffsetEditor();
        syncTaskValueOffsetTextFromState();
        updateTaskValueOffsetApplyState();
    }

    function ensureTaskValueOffsetEditorRow(task = '') {
        const normalizedTask = normalizeSurveyTaskName(task);
        const editorState = getTaskValueOffsetEditorState();
        if (normalizedTask) {
            const existing = editorState.find((entry) => normalizeSurveyTaskName(entry && entry.task) === normalizedTask);
            if (existing) {
                return existing.id;
            }
        }

        const defaultTask = normalizedTask || getPreferredTaskValueOffsetTask();
        const nextRow = createTaskValueOffsetRow(defaultTask);
        setTaskValueOffsetEditorState(editorState.concat(nextRow));
        renderTaskValueOffsetEditor();
        syncTaskValueOffsetTextFromState();
        return nextRow.id;
    }

    function focusTaskValueOffsetEditor(rowId = null) {
        const focusRoot = rowId && convertValueOffsetRows
            ? convertValueOffsetRows.querySelector(`[data-offset-row-id="${rowId}"]`)
            : convertValueOffsetsEditor;
        const target = focusRoot && typeof focusRoot.querySelector === 'function'
            ? focusRoot.querySelector('[data-role="task"]:not([disabled]), [data-role="magnitude"]:not([disabled])')
            : null;

        if (convertValueOffsetsEditor && typeof convertValueOffsetsEditor.scrollIntoView === 'function') {
            convertValueOffsetsEditor.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        if (target && typeof target.focus === 'function') {
            target.focus();
            return;
        }

        if (convertAddValueOffsetRowBtn && typeof convertAddValueOffsetRowBtn.focus === 'function') {
            convertAddValueOffsetRowBtn.focus();
            return;
        }

        convertValueOffsets?.focus();
    }

    function clearManualValueOffsetAdvice() {
        if (!convertValueOffsetAdvice) {
            return;
        }
        convertValueOffsetAdvice.classList.add('d-none');
        convertValueOffsetAdvice.textContent = '';
    }

    function handleTaskValueOffsetEditorChanged() {
        clearManualValueOffsetAdvice();
        convertError?.classList.add('d-none');
        if (convertError) {
            convertError.textContent = '';
        }
        syncTaskValueOffsetTextFromState();
        updateTaskValueOffsetApplyState();
        updateConvertBtn();
    }

    function updateTaskValueOffsetApplyState() {
        const enabled = isAdvancedOptionsEnabled();
        const hasRows = getTaskValueOffsetEditorState().length > 0;
        const hasIncompleteRows = hasIncompleteTaskValueOffsetRows();
        const hasManualOffsets = hasManualTaskValueOffsets();
        const hasAppliedOffsets = hasAppliedTaskValueOffsetSelections();
        const isConvertRunning = typeof getIsConvertRunning === 'function'
            ? Boolean(getIsConvertRunning())
            : false;
        const isPreviewRunning = typeof getIsPreviewRunning === 'function'
            ? Boolean(getIsPreviewRunning())
            : false;

        if (convertApplyValueOffsetsBtn) {
            convertApplyValueOffsetsBtn.disabled = !enabled || !hasRows || isConvertRunning || isPreviewRunning;
            convertApplyValueOffsetsBtn.classList.remove('btn-outline-primary', 'btn-success');
            convertApplyValueOffsetsBtn.classList.add(hasManualOffsets && hasAppliedOffsets ? 'btn-success' : 'btn-outline-primary');
            convertApplyValueOffsetsBtn.innerHTML = hasManualOffsets && hasAppliedOffsets
                ? '<i class="fas fa-check me-1"></i>Offsets applied'
                : '<i class="fas fa-list-check me-1"></i>Apply offsets';

            if (!enabled) {
                convertApplyValueOffsetsBtn.title = 'Enable advanced options to configure manual offsets.';
            } else if (!hasRows) {
                convertApplyValueOffsetsBtn.title = 'Add at least one task offset row first.';
            } else if (hasIncompleteRows) {
                convertApplyValueOffsetsBtn.title = 'Complete each offset row with a task and numeric value, then click Apply offsets.';
            } else if (isConvertRunning || isPreviewRunning) {
                convertApplyValueOffsetsBtn.title = 'Wait for the current run to finish.';
            } else if (hasAppliedOffsets) {
                convertApplyValueOffsetsBtn.title = 'Offsets are applied. Run Preview to validate with these settings.';
            } else {
                convertApplyValueOffsetsBtn.title = 'Apply these offsets, then rerun Preview.';
            }
        }

        if (convertValueOffsetsStatus) {
            convertValueOffsetsStatus.classList.toggle('d-none', !enabled);
            convertValueOffsetsStatus.classList.remove('text-muted', 'text-success', 'text-warning');
            if (!enabled) {
                convertValueOffsetsStatus.textContent = '';
            } else if (!hasRows) {
                convertValueOffsetsStatus.classList.add('text-muted');
                convertValueOffsetsStatus.textContent = 'No manual offsets configured.';
            } else if (hasIncompleteRows) {
                convertValueOffsetsStatus.classList.add('text-warning');
                convertValueOffsetsStatus.textContent = 'Complete each row with a task and numeric value, then click Apply offsets.';
            } else if (hasAppliedOffsets) {
                convertValueOffsetsStatus.classList.add('text-success');
                convertValueOffsetsStatus.textContent = 'Offsets applied. Run Preview to validate the current scale settings.';
            } else {
                convertValueOffsetsStatus.classList.add('text-warning');
                convertValueOffsetsStatus.textContent = 'Offsets changed. Click Apply offsets, then run Preview again.';
            }
        }
    }

    function applyAdvancedOptionsState() {
        const enabled = isAdvancedOptionsEnabled();

        if (convertDatasetName) {
            convertDatasetName.disabled = !enabled;
            if (!enabled) convertDatasetName.value = '';
        }

        if (convertLanguage) {
            convertLanguage.disabled = !enabled;
            if (!enabled) convertLanguage.value = 'auto';
        }

        if (convertIdMapFile) {
            convertIdMapFile.disabled = !enabled;
            if (!enabled) {
                convertIdMapFile.value = '';
                clearIdMapFileBtn?.classList.add('d-none');
            }
        }

        if (convertValueOffsets) {
            convertValueOffsets.disabled = !enabled;
            if (!enabled) {
                convertValueOffsets.value = '';
                clearTaskValueOffsetEditorState();
                clearManualValueOffsetAdvice();
            } else {
                renderTaskValueOffsetEditor();
                syncTaskValueOffsetTextFromState();
            }
        }

        if (clearIdMapFileBtn) {
            clearIdMapFileBtn.disabled = !enabled;
        }

        updateTaskValueOffsetApplyState();
        updateConvertBtn();
    }

    function initialize() {
        if (convertAdvancedToggle) {
            convertAdvancedToggle.addEventListener('change', applyAdvancedOptionsState);
        }

        if (convertValueOffsets) {
            convertValueOffsets.addEventListener('input', () => {
                clearManualValueOffsetAdvice();
                convertError?.classList.add('d-none');
                if (convertError) {
                    convertError.textContent = '';
                }
                updateTaskValueOffsetApplyState();
                updateConvertBtn();
            });
        }

        if (convertAddValueOffsetRowBtn) {
            convertAddValueOffsetRowBtn.addEventListener('click', () => {
                const rowId = ensureTaskValueOffsetEditorRow();
                handleTaskValueOffsetEditorChanged();
                focusTaskValueOffsetEditor(rowId);
            });
        }

        if (convertValueOffsetRows) {
            const getRowIdFromTarget = (target) => {
                const row = target && typeof target.closest === 'function'
                    ? target.closest('[data-offset-row-id]')
                    : null;
                return row ? Number(row.getAttribute('data-offset-row-id')) : null;
            };

            const getRowState = (rowId) => {
                return getTaskValueOffsetEditorState().find((entry) => entry.id === rowId) || null;
            };

            convertValueOffsetRows.addEventListener('change', (event) => {
                const target = event.target;
                const role = target && target.getAttribute ? target.getAttribute('data-role') : '';
                const rowId = getRowIdFromTarget(target);
                const rowState = rowId !== null ? getRowState(rowId) : null;
                if (!rowState) {
                    return;
                }

                if (role === 'task') {
                    rowState.task = normalizeSurveyTaskName(target.value);
                    handleTaskValueOffsetEditorChanged();
                    return;
                }

                if (role === 'operator') {
                    rowState.operator = target.value === '-' ? '-' : '+';
                    handleTaskValueOffsetEditorChanged();
                }
            });

            convertValueOffsetRows.addEventListener('input', (event) => {
                const target = event.target;
                const role = target && target.getAttribute ? target.getAttribute('data-role') : '';
                if (role !== 'magnitude') {
                    return;
                }

                const rowId = getRowIdFromTarget(target);
                const rowState = rowId !== null ? getRowState(rowId) : null;
                if (!rowState) {
                    return;
                }

                const rawValue = String(target.value || '').trim();
                const parsedValue = parseNumericOffsetValue(rawValue);
                rowState.magnitude = rawValue && parsedValue !== null
                    ? formatOffsetMagnitude(parsedValue)
                    : rawValue;
                handleTaskValueOffsetEditorChanged();
            });

            convertValueOffsetRows.addEventListener('click', (event) => {
                const target = event.target && typeof event.target.closest === 'function'
                    ? event.target.closest('[data-role="remove"]')
                    : null;
                if (!target) {
                    return;
                }

                const rowId = getRowIdFromTarget(target);
                if (rowId === null) {
                    return;
                }

                const nextState = getTaskValueOffsetEditorState().filter((entry) => entry.id !== rowId);
                setTaskValueOffsetEditorState(nextState);
                renderTaskValueOffsetEditor();
                handleTaskValueOffsetEditorChanged();
            });
        }

        setTaskValueOffsetEditorStateFromText(convertValueOffsets ? convertValueOffsets.value : '');
        applyAdvancedOptionsState();
    }

    return {
        initialize,
        applyAdvancedOptionsState,
        createTaskValueOffsetRow,
        getAvailableSurveyTasksForValueOffsets,
        getPreferredTaskValueOffsetTask,
        syncTaskValueOffsetTextFromState,
        setTaskValueOffsetEditorStateFromText,
        clearTaskValueOffsetEditorState,
        ensureTaskValueOffsetEditorRow,
        focusTaskValueOffsetEditor,
        renderTaskValueOffsetEditor,
        handleTaskValueOffsetEditorChanged,
        clearManualValueOffsetAdvice,
        getTaskValueOffsetMapFromEditorState,
        getCurrentTaskValueOffsetSelectionSignature,
        getManualTaskValueOffsets,
        hasManualTaskValueOffsets,
        hasIncompleteTaskValueOffsetRows,
        hasAppliedTaskValueOffsetSelections,
        updateTaskValueOffsetApplyState,
    };
}
