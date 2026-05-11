export function createSurveyNearItemMatchReviewController({
    normalizeNearMatchTaskName,
    escapeHtml,
}) {
    function collectNearMatchCandidates(payload) {
        if (!Array.isArray(payload && payload.near_match_candidates)) {
            return [];
        }
        return payload.near_match_candidates
            .map((candidate) => {
                const source = String(candidate && candidate.source_column || '').trim();
                const target = String(candidate && candidate.target_item || '').trim();
                const task = normalizeNearMatchTaskName(candidate && candidate.task);
                const run = candidate && candidate.run !== undefined ? candidate.run : null;
                if (!source || !target || !task) {
                    return null;
                }
                return { source, target, task, run };
            })
            .filter(Boolean);
    }

    function buildNearMatchConfirmationMessage(payload, actionLabel) {
        const candidates = collectNearMatchCandidates(payload);
        if (candidates.length === 0) {
            return '';
        }

        const lines = candidates.map((candidate) => {
            const run = (candidate.run !== undefined && candidate.run !== null && String(candidate.run).trim() !== '')
                ? `, run ${candidate.run}`
                : '';
            return `- ${candidate.source} -> ${candidate.target} (task ${candidate.task}${run})`;
        });

        return [
            `Safe near item matches detected during ${actionLabel}.`,
            '',
            'Exact matching is always used first.',
            'These optional near matches only tolerate minimal differences (separator/zero-padding) and are count-guarded.',
            '',
            `Apply ${candidates.length} near match(es) and rerun?`,
            '',
            ...lines,
        ].join('\n');
    }

    function promptNearMatchSelection(payload, actionLabel) {
        const candidates = collectNearMatchCandidates(payload);
        if (candidates.length === 0) {
            return Promise.resolve({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
        }

        const taskCounts = new Map();
        candidates.forEach((candidate) => {
            const count = taskCounts.get(candidate.task) || 0;
            taskCounts.set(candidate.task, count + 1);
        });
        const tasks = Array.from(taskCounts.entries())
            .sort((left, right) => left[0].localeCompare(right[0]))
            .map(([task, count]) => ({ task, count }));

        if (!(window.bootstrap && typeof window.bootstrap.Modal === 'function')) {
            const promptMessage = buildNearMatchConfirmationMessage(payload, actionLabel);
            const approved = Boolean(promptMessage) && window.confirm(promptMessage);
            return Promise.resolve({
                approved,
                selectedTasks: approved ? tasks.map((entry) => entry.task) : [],
                selectedCandidateCount: approved ? candidates.length : 0,
            });
        }

        return new Promise((resolve) => {
            const modalEl = document.createElement('div');
            modalEl.className = 'modal fade';
            modalEl.tabIndex = -1;
            modalEl.setAttribute('aria-hidden', 'true');

            const actionText = escapeHtml(String(actionLabel || 'preview'));
            const taskChecklistHtml = tasks
                .map((entry, index) => {
                    const task = escapeHtml(entry.task);
                    const countLabel = `${entry.count} item${entry.count === 1 ? '' : 's'}`;
                    return `
                        <div class="form-check mb-2">
                            <input
                                class="form-check-input"
                                type="checkbox"
                                id="nearMatchTask_${index}"
                                value="${task}"
                                data-role="near-task-checkbox"
                                checked
                            >
                            <label class="form-check-label" for="nearMatchTask_${index}">
                                <strong>${task}</strong>
                                <span class="text-muted small">(${countLabel})</span>
                            </label>
                        </div>
                    `;
                })
                .join('');

            const tableRowsHtml = candidates
                .map((candidate) => {
                    const runLabel = (candidate.run !== undefined && candidate.run !== null && String(candidate.run).trim() !== '')
                        ? escapeHtml(String(candidate.run))
                        : '-';
                    return `
                        <tr data-task="${escapeHtml(candidate.task)}">
                            <td><code>${escapeHtml(candidate.source)}</code></td>
                            <td><code>${escapeHtml(candidate.target)}</code></td>
                            <td>${escapeHtml(candidate.task)}</td>
                            <td>${runLabel}</td>
                        </tr>
                    `;
                })
                .join('');

            const summaryHtml = tasks
                .map(entry => `<strong>${escapeHtml(entry.task)}</strong>: ${entry.count} item${entry.count === 1 ? '' : 's'}`)
                .join(', ');

            modalEl.innerHTML = `
                <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <div class="d-flex align-items-center align-self-center overflow-hidden w-100 me-3">
                                <h5 class="modal-title flex-shrink-0">Review Safe Near Item Matches</h5>
                                <div class="text-muted ms-3 border-start ps-3 small text-truncate" title="${summaryHtml.replace(/<[^>]+>/g, '')}">
                                    ${summaryHtml}
                                </div>
                            </div>
                            <button type="button" class="btn-close" aria-label="Close" data-role="close-btn"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-1">Safe near item matches were detected during ${actionText}.</p>
                            <p class="text-muted small mb-3">Exact matching runs first. Near matching only allows minimal separator and zero-padding differences and only when count-safe checks pass.</p>

                            <div class="row g-3">
                                <div class="col-12 col-lg-4">
                                    <div class="d-flex gap-2 mb-2">
                                        <button type="button" class="btn btn-sm btn-outline-secondary" data-role="select-all-tasks">Select all</button>
                                        <button type="button" class="btn btn-sm btn-outline-secondary" data-role="clear-all-tasks">Clear all</button>
                                    </div>
                                    <div class="border rounded p-2" style="max-height: 360px; overflow-y: auto;">
                                        ${taskChecklistHtml}
                                    </div>
                                    <small class="text-muted d-block mt-2">Tick the survey tasks you want to allow for near matching.</small>
                                </div>
                                <div class="col-12 col-lg-8">
                                    <div class="table-responsive border rounded" style="max-height: 360px; overflow-y: auto;">
                                        <table class="table table-sm table-striped align-middle mb-0">
                                            <thead class="table-light" style="position: sticky; top: 0; z-index: 1;">
                                                <tr>
                                                    <th scope="col">Source Column</th>
                                                    <th scope="col">Template Item</th>
                                                    <th scope="col">Task</th>
                                                    <th scope="col">Run</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${tableRowsHtml}
                                            </tbody>
                                        </table>
                                    </div>
                                    <small class="text-muted d-block mt-2">All candidate near matches are shown above.</small>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <span class="me-auto text-muted small" data-role="selection-meta"></span>
                            <button type="button" class="btn btn-outline-secondary" data-role="cancel-btn">Cancel</button>
                            <button type="button" class="btn btn-primary" data-role="apply-btn">Apply Selected Tasks and Rerun</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modalEl);

            const modal = new window.bootstrap.Modal(modalEl, {
                backdrop: 'static',
                keyboard: false,
            });

            const taskCheckboxes = Array.from(
                modalEl.querySelectorAll('input[data-role="near-task-checkbox"]')
            );
            const selectionMeta = modalEl.querySelector('[data-role="selection-meta"]');
            const applyBtn = modalEl.querySelector('[data-role="apply-btn"]');
            const cancelBtn = modalEl.querySelector('[data-role="cancel-btn"]');
            const closeBtn = modalEl.querySelector('[data-role="close-btn"]');
            const selectAllBtn = modalEl.querySelector('[data-role="select-all-tasks"]');
            const clearAllBtn = modalEl.querySelector('[data-role="clear-all-tasks"]');
            const tableRows = Array.from(modalEl.querySelectorAll('tbody tr[data-task]'));

            let pendingResult = null;

            function collectSelectionState() {
                const selectedTasks = taskCheckboxes
                    .filter((checkbox) => checkbox.checked)
                    .map((checkbox) => normalizeNearMatchTaskName(checkbox.value));
                const selectedTaskSet = new Set(selectedTasks);
                const selectedCandidateCount = candidates.reduce((count, candidate) => {
                    return count + (selectedTaskSet.has(candidate.task) ? 1 : 0);
                }, 0);
                return {
                    selectedTasks,
                    selectedTaskSet,
                    selectedCandidateCount,
                };
            }

            function updateSelectionUi() {
                const state = collectSelectionState();
                if (selectionMeta) {
                    selectionMeta.textContent = `Selected surveys: ${state.selectedTasks.length}/${tasks.length} | Selected items: ${state.selectedCandidateCount}/${candidates.length}`;
                }
                if (applyBtn) {
                    applyBtn.disabled = state.selectedTasks.length === 0;
                }
                tableRows.forEach((row) => {
                    const task = normalizeNearMatchTaskName(row.getAttribute('data-task') || '');
                    const selected = state.selectedTaskSet.has(task);
                    row.classList.toggle('table-secondary', !selected);
                    row.classList.toggle('opacity-50', !selected);
                });
            }

            function setAllTaskSelections(checked) {
                taskCheckboxes.forEach((checkbox) => {
                    checkbox.checked = checked;
                });
                updateSelectionUi();
            }

            function finalizeAndClose(result) {
                pendingResult = result;
                modal.hide();
            }

            taskCheckboxes.forEach((checkbox) => {
                checkbox.addEventListener('change', updateSelectionUi);
            });

            if (selectAllBtn) {
                selectAllBtn.addEventListener('click', () => setAllTaskSelections(true));
            }
            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', () => setAllTaskSelections(false));
            }
            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    finalizeAndClose({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
                });
            }
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    finalizeAndClose({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
                });
            }
            if (applyBtn) {
                applyBtn.addEventListener('click', () => {
                    const state = collectSelectionState();
                    if (state.selectedTasks.length === 0) {
                        return;
                    }
                    finalizeAndClose({
                        approved: true,
                        selectedTasks: state.selectedTasks,
                        selectedCandidateCount: state.selectedCandidateCount,
                    });
                });
            }

            modalEl.addEventListener('hidden.bs.modal', () => {
                const result = pendingResult || {
                    approved: false,
                    selectedTasks: [],
                    selectedCandidateCount: 0,
                };
                modal.dispose();
                modalEl.remove();
                resolve(result);
            }, { once: true });

            updateSelectionUi();
            modal.show();
        });
    }

    return {
        collectNearMatchCandidates,
        buildNearMatchConfirmationMessage,
        promptNearMatchSelection,
    };
}
