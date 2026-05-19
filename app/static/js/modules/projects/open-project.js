export function initOpenProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    getBeginnerHelpModeEnabled,
    resolveProjectIconClass,
    getCurrentProjectState,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showExportCard,
    showMethodsCard,
    bindProjectBoxActionButtons,
}) {
    function setProjectValidationResult(html) {
        const resultDiv = document.getElementById('validationResult');
        if (!resultDiv) return;
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = html;
    }

    function showOpenProjectError(message, title = 'Error') {
        setProjectValidationResult(`
            <div class="validation-result invalid">
                <h5><i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(title)}</h5>
                <p class="mb-0">${escapeHtml(message)}</p>
            </div>
        `);
    }

    function normalizeProjectSummaryCount(value) {
        const parsed = Number.parseInt(String(value ?? ''), 10);
        if (!Number.isFinite(parsed) || parsed < 0) {
            return 0;
        }
        return parsed;
    }

    function normalizeProjectSummaryLabels(values) {
        if (!Array.isArray(values)) {
            return [];
        }

        const seen = new Set();
        const labels = [];
        values.forEach((value) => {
            const text = String(value || '').trim();
            if (!text || seen.has(text)) {
                return;
            }
            seen.add(text);
            labels.push(text);
        });
        return labels;
    }

    function normalizeDataladState(dataladState, fallbackPath = '') {
        const normalizeCount = (value, defaultValue = 0) => {
            const parsed = Number.parseInt(String(value ?? ''), 10);
            return Number.isFinite(parsed) && parsed >= 0 ? parsed : defaultValue;
        };

        const resolvedPath = (typeof dataladState?.path === 'string' ? dataladState.path.trim() : '') || String(fallbackPath || '').trim();
        const defaultMessage = resolvedPath
            ? 'Current project is not a DataLad dataset.'
            : 'Load a project to see DataLad status.';

        if (!dataladState || typeof dataladState !== 'object' || Array.isArray(dataladState)) {
            return {
                enabled: false,
                available: false,
                annexAvailable: false,
                canSave: false,
                canEnable: false,
                message: defaultMessage,
                path: resolvedPath,
                subdatasetsTotalCount: 0,
                subdatasetsRegisteredCount: 0,
                subdatasetsRemainingCount: 0,
                subdatasetsProgressPercent: 0,
                nextMissingSubdataset: '',
            };
        }

        const message = typeof dataladState.message === 'string' && dataladState.message.trim()
            ? dataladState.message.trim()
            : defaultMessage;

        return {
            enabled: Boolean(dataladState.enabled),
            available: Boolean(dataladState.available),
            annexAvailable: Boolean(dataladState.annex_available ?? dataladState.annexAvailable),
            canSave: Boolean(dataladState.can_save ?? dataladState.canSave),
            canEnable: Boolean(dataladState.can_enable ?? dataladState.canEnable),
            message,
            path: resolvedPath,
            subdatasetsTotalCount: normalizeCount(dataladState.subdatasets_total_count ?? dataladState.subdatasetsTotalCount),
            subdatasetsRegisteredCount: normalizeCount(dataladState.subdatasets_registered_count ?? dataladState.subdatasetsRegisteredCount),
            subdatasetsRemainingCount: normalizeCount(dataladState.subdatasets_remaining_count ?? dataladState.subdatasetsRemainingCount),
            subdatasetsProgressPercent: normalizeCount(dataladState.subdatasets_progress_percent ?? dataladState.subdatasetsProgressPercent),
            nextMissingSubdataset: typeof (dataladState.next_missing_subdataset ?? dataladState.nextMissingSubdataset) === 'string'
                ? String(dataladState.next_missing_subdataset ?? dataladState.nextMissingSubdataset).trim()
                : '',
        };
    }

    function setProjectBoxDataladFeedback(message, kind = 'muted') {
        const feedback = document.getElementById('projectBoxDataladFeedback');
        if (!feedback) {
            return;
        }

        const normalizedMessage = String(message || '').trim();
        feedback.className = 'small mt-2';
        if (!normalizedMessage) {
            feedback.classList.add('d-none');
            feedback.textContent = '';
            return;
        }

        feedback.classList.remove('d-none');
        if (kind === 'success') {
            feedback.classList.add('text-success');
        } else if (kind === 'danger') {
            feedback.classList.add('text-danger');
        } else {
            feedback.classList.add('text-muted');
        }
        feedback.textContent = normalizedMessage;
    }

    function renderProjectBoxDataladState(dataladState, fallbackPath = '') {
        const status = document.getElementById('projectBoxDataladStatus');
        const hint = document.getElementById('projectBoxDataladHint');
        const stateBadge = document.getElementById('projectBoxDataladStateBadge');
        const enableButton = document.getElementById('projectBoxDataladEnableBtn');
        const saveButton = document.getElementById('projectBoxDataladSaveBtn');
        const progressWrap = document.getElementById('projectBoxDataladProgressWrap');
        const progressBar = document.getElementById('projectBoxDataladProgressBar');
        const progressLabel = document.getElementById('projectBoxDataladProgressLabel');
        if (!status || !hint || !stateBadge || !enableButton || !saveButton || !progressWrap || !progressBar || !progressLabel) {
            return;
        }

        const state = normalizeDataladState(dataladState, fallbackPath);
        status.textContent = state.message;
        stateBadge.className = 'badge rounded-pill';
        enableButton.classList.remove('d-none');
        enableButton.innerHTML = '<i class="fas fa-plus me-1"></i>Enable DataLad';

        if (state.enabled && state.subdatasetsTotalCount > 0) {
            progressWrap.classList.remove('d-none');
            progressBar.style.width = `${state.subdatasetsProgressPercent}%`;
            progressBar.setAttribute('aria-valuenow', String(state.subdatasetsProgressPercent));
            progressBar.textContent = `${state.subdatasetsProgressPercent}%`;
            progressLabel.textContent = state.subdatasetsRemainingCount > 0
                ? `Nested datasets: ${state.subdatasetsRegisteredCount}/${state.subdatasetsTotalCount} registered. Next: ${state.nextMissingSubdataset || 'pending'}.`
                : `Nested datasets complete: ${state.subdatasetsRegisteredCount}/${state.subdatasetsTotalCount} registered.`;
        } else {
            progressWrap.classList.add('d-none');
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', '0');
            progressBar.textContent = '';
            progressLabel.textContent = '';
        }

        if (state.enabled && state.available) {
            stateBadge.classList.add('bg-success', 'text-white');
            stateBadge.textContent = 'Tracked';
            hint.textContent = 'This project is already DataLad-tracked. Use Repair DataLad Structure to backfill one missing nested dataset per click, or Save DataLad Snapshot for an explicit checkpoint.';
            enableButton.innerHTML = '<i class="fas fa-screwdriver-wrench me-1"></i>Repair DataLad Structure';
            enableButton.disabled = false;
            enableButton.title = 'Repair or complete DataLad setup for the current project';
        } else if (state.enabled) {
            stateBadge.classList.add('bg-warning', 'text-dark');
            stateBadge.textContent = 'Tracked';
            hint.textContent = 'This project is DataLad-tracked, but DataLad is not currently available in this environment.';
            enableButton.disabled = true;
            enableButton.innerHTML = '<i class="fas fa-screwdriver-wrench me-1"></i>Repair DataLad Structure';
            enableButton.title = 'DataLad executable not available';
        } else {
            stateBadge.classList.add('bg-light', 'text-muted', 'border');
            stateBadge.textContent = 'Not tracked';
            hint.textContent = state.canEnable
                ? 'Enable DataLad version control here for the current project.'
                : (state.available && !state.annexAvailable
                    ? 'git-annex is missing, so PRISM cannot initialize a new DataLad dataset here.'
                    : 'DataLad is not available in this environment.');
            enableButton.disabled = !state.canEnable;
            enableButton.title = state.canEnable
                ? 'Initialize DataLad for the current project'
                : (state.available && !state.annexAvailable
                    ? 'git-annex not available'
                    : 'DataLad executable not available');
        }

        saveButton.disabled = !state.canSave;
        saveButton.title = state.canSave
            ? 'Create a DataLad snapshot for the current project'
            : (state.enabled
                ? 'DataLad executable not available'
                : 'Current project is not a DataLad dataset');
    }

    function applyProjectDataladResponse(data) {
        const currentState = getCurrentProjectState();
        const nextProjectState = data.current_project && typeof data.current_project === 'object'
            ? { ...data.current_project, datalad: data.datalad || data.current_project.datalad }
            : { ...currentState, datalad: data.datalad };

        applyCurrentProject(nextProjectState);
        renderProjectBoxDataladState(nextProjectState.datalad, nextProjectState.path);
        return nextProjectState;
    }

    function confirmEnableDatalad(currentPath) {
        return window.confirm(
            'Enable DataLad version control for this project?\n\n'
            + 'This will modify the project in place by creating or repairing DataLad/Git metadata, backfilling one missing nested dataset for this click, and saving a snapshot.\n\n'
            + 'Only continue if you explicitly want DataLad for this dataset.\n\n'
            + `Project: ${currentPath}`
        );
    }

    async function pollCurrentProjectDataladStateWhileBusy({
        currentPath,
        actionState,
        busyMarkup,
        fallbackTarget,
    }) {
        const normalizedPath = String(currentPath || '').trim();
        if (!normalizedPath) {
            return;
        }

        while (actionState.active) {
            await new Promise((resolve) => window.setTimeout(resolve, 1500));
            if (!actionState.active) {
                return;
            }

            try {
                const response = await fetchWithApiFallback('/api/projects/current', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                });
                const current = await response.json().catch(() => null);
                if (!actionState.active || !response.ok || !current || typeof current !== 'object') {
                    continue;
                }

                const responsePath = String(current.path || '').trim();
                if (responsePath !== normalizedPath) {
                    continue;
                }

                applyCurrentProject(current);
                renderProjectBoxDataladState(current.datalad, normalizedPath);

                const liveDataladState = normalizeDataladState(current.datalad, normalizedPath);
                const liveTarget = liveDataladState.nextMissingSubdataset || fallbackTarget || 'the next nested dataset';
                const liveMessage = `Repairing ${liveTarget}. Large tracked folders can take a while. Watch the backend terminal for progress.`;
                setProjectBoxDataladFeedback(liveMessage, 'muted');
                window.setNavbarDataladFeedback?.(liveMessage, 'muted', 'Running');

                const enableButton = document.getElementById('projectBoxDataladEnableBtn');
                if (enableButton && actionState.active) {
                    enableButton.disabled = true;
                    enableButton.innerHTML = busyMarkup;
                }
            } catch (_error) {
                if (!actionState.active) {
                    return;
                }
            }
        }
    }

    function bindProjectBoxDataladActions() {
        const enableButton = document.getElementById('projectBoxDataladEnableBtn');
        if (enableButton && enableButton.dataset.bound !== '1') {
            enableButton.dataset.bound = '1';
            enableButton.addEventListener('click', async function() {
                const currentPath = String(getCurrentProjectState().path || '').trim();
                if (!currentPath) {
                    setProjectBoxDataladFeedback('Load a project first.', 'danger');
                    window.setNavbarDataladFeedback?.('Load a project first.', 'danger', 'Error');
                    return;
                }

                if (!confirmEnableDatalad(currentPath)) {
                    setProjectBoxDataladFeedback('DataLad enable cancelled.', 'muted');
                    window.setNavbarDataladFeedback?.('DataLad enable cancelled.', 'muted', 'Cancelled');
                    return;
                }

                const originalText = enableButton.innerHTML;
                const currentDataladState = normalizeDataladState(getCurrentProjectState().datalad, currentPath);
                const busyLabel = currentDataladState.enabled ? 'Repairing...' : 'Enabling...';
                const busyMarkup = `<i class="fas fa-spinner fa-spin me-1"></i>${busyLabel}`;
                enableButton.disabled = true;
                enableButton.innerHTML = busyMarkup;
                const repairTarget = currentDataladState.nextMissingSubdataset || 'the next nested dataset';
                const pendingMessage = `Repairing ${repairTarget}. Large tracked folders can take a while. Watch the backend terminal for progress.`;
                setProjectBoxDataladFeedback(pendingMessage, 'muted');
                window.setNavbarDataladFeedback?.(pendingMessage, 'muted', 'Running');
                const actionState = { active: true };
                const pollingPromise = pollCurrentProjectDataladStateWhileBusy({
                    currentPath,
                    actionState,
                    busyMarkup,
                    fallbackTarget: repairTarget,
                });

                try {
                    const response = await fetchWithApiFallback('/api/projects/datalad/enable', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ confirmed: true })
                    });
                    const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
                    if (!response.ok || !data.success) {
                        throw new Error(data.error || data.message || 'Could not enable DataLad.');
                    }

                    applyProjectDataladResponse(data);
                    const successMessage = data.message || (data.datalad && data.datalad.message) || 'DataLad enabled.';
                    setProjectBoxDataladFeedback(successMessage, 'success');
                    window.setNavbarDataladFeedback?.(successMessage, 'success', 'Enabled');
                } catch (error) {
                    const errorMessage = error.message || 'Could not enable DataLad.';
                    setProjectBoxDataladFeedback(errorMessage, 'danger');
                    window.setNavbarDataladFeedback?.(errorMessage, 'danger', 'Error');
                } finally {
                    actionState.active = false;
                    await pollingPromise.catch(() => {});
                    enableButton.innerHTML = originalText;
                    renderProjectBoxDataladState(getCurrentProjectState().datalad, currentPath);
                }
            });
        }

        const saveButton = document.getElementById('projectBoxDataladSaveBtn');
        if (saveButton && saveButton.dataset.bound !== '1') {
            saveButton.dataset.bound = '1';
            saveButton.addEventListener('click', async function() {
                const currentPath = String(getCurrentProjectState().path || '').trim();
                if (!currentPath) {
                    setProjectBoxDataladFeedback('Load a project first.', 'danger');
                    window.setNavbarDataladFeedback?.('Load a project first.', 'danger', 'Error');
                    return;
                }

                const requestedMessage = window.prompt('Commit message for this checkpoint', 'Checkpoint PRISM project changes');
                if (requestedMessage === null) {
                    return;
                }

                const saveMessage = String(requestedMessage || '').trim() || 'Checkpoint PRISM project changes';
                const originalText = saveButton.innerHTML;
                saveButton.disabled = true;
                saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
                setProjectBoxDataladFeedback('', 'muted');

                try {
                    const response = await fetchWithApiFallback('/api/projects/datalad/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: saveMessage })
                    });
                    const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
                    if (!response.ok || !data.success) {
                        throw new Error(data.error || data.message || 'Could not save DataLad changes.');
                    }

                    applyProjectDataladResponse(data);
                    const successMessage = data.message || (data.datalad && data.datalad.message) || 'DataLad save completed.';
                    setProjectBoxDataladFeedback(successMessage, 'success');
                    window.setNavbarDataladFeedback?.(successMessage, 'success', 'Saved');
                } catch (error) {
                    const errorMessage = error.message || 'Could not save DataLad changes.';
                    setProjectBoxDataladFeedback(errorMessage, 'danger');
                    window.setNavbarDataladFeedback?.(errorMessage, 'danger', 'Error');
                } finally {
                    saveButton.innerHTML = originalText;
                    renderProjectBoxDataladState(getCurrentProjectState().datalad, currentPath);
                }
            });
        }
    }

    function renderProjectQuickSummary(summary) {
        if (!summary || typeof summary !== 'object' || Array.isArray(summary)) {
            return '<p class="mb-0 text-muted"><i class="fas fa-info-circle me-1"></i>Quick summary unavailable for this project.</p>';
        }

        const subjects = normalizeProjectSummaryCount(summary.subjects);
        const sessions = normalizeProjectSummaryCount(summary.sessions);
        const modalities = normalizeProjectSummaryCount(summary.modalities);
        const hasDatasetDescription = Boolean(summary.has_dataset_description);
        const hasParticipantsTsv = Boolean(summary.has_participants_tsv);

        const sessionLabels = normalizeProjectSummaryLabels(summary.session_labels);
        const modalityLabels = normalizeProjectSummaryLabels(summary.modality_labels);
        const shownSessionLabels = sessionLabels.slice(0, 6);
        const shownModalityLabels = modalityLabels.slice(0, 6);
        const hiddenSessionCount = Math.max(0, sessionLabels.length - shownSessionLabels.length);
        const hiddenModalityCount = Math.max(0, modalityLabels.length - shownModalityLabels.length);

        const sessionText = shownSessionLabels.map(label => escapeHtml(label)).join(', ');
        const modalityText = shownModalityLabels.map(label => escapeHtml(label)).join(', ');

        return `
            <div class="small text-muted mb-2"><i class="fas fa-database me-1"></i>Snapshot from folders currently found on disk.</div>
            <div class="stats-grid mt-2">
                <div class="stat-item">
                    <div class="stat-value">${subjects}</div>
                    <div class="stat-label">Subjects</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${sessions}</div>
                    <div class="stat-label">Sessions</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${modalities}</div>
                    <div class="stat-label">Modalities</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value ${hasDatasetDescription ? 'text-success' : 'text-danger'}">${hasDatasetDescription ? '✓' : '✗'}</div>
                    <div class="stat-label">dataset_description</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value ${hasParticipantsTsv ? 'text-success' : 'text-danger'}">${hasParticipantsTsv ? '✓' : '✗'}</div>
                    <div class="stat-label">participants.tsv</div>
                </div>
            </div>
            ${modalityText ? `
                <div class="small text-muted mt-2"><strong>Modalities:</strong> ${modalityText}${hiddenModalityCount > 0 ? ` (+${hiddenModalityCount} more)` : ''}</div>
            ` : ''}
            ${sessionText ? `
                <div class="small text-muted mt-1"><strong>Sessions:</strong> ${sessionText}${hiddenSessionCount > 0 ? ` (+${hiddenSessionCount} more)` : ''}</div>
            ` : ''}
        `;
    }

    function renderLoadedProjectState(loadedName, loadedPath, summary) {
        const quickSummaryHtml = renderProjectQuickSummary(summary);
        const projectIconClass = escapeHtml(resolveProjectIconClass(getCurrentProjectState().icon));
        setProjectValidationResult(`
            <div class="validation-result pending project-loaded-state">
                <h5><i class="fas fa-folder-open me-2"></i>Project Loaded</h5>
                <p class="mb-1"><strong><span class="me-1" aria-hidden="true">${projectIconClass}</span>${escapeHtml(loadedName || 'Current project')}:</strong> <code>${escapeHtml(loadedPath)}</code></p>
                ${quickSummaryHtml}
                <div class="alert alert-info mt-2 mb-0" role="status">
                    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
                        <div>
                            <strong>Need a full dataset check?</strong>
                            <span class="ms-1">Open the Validator to run the canonical PRISM/BIDS validation flow for the current project.</span>
                        </div>
                        <a href="/validate" class="btn btn-sm btn-outline-primary">
                            <i class="fas fa-shield-check me-1"></i>Open Validator
                        </a>
                    </div>
                </div>
                <div class="alert alert-light border mt-3 mb-0" role="status">
                    <div class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-start gap-3">
                        <div>
                            <div class="d-flex align-items-center gap-2 flex-wrap">
                                <strong><i class="fas fa-code-branch me-1"></i>DataLad Version Control</strong>
                                <span class="badge rounded-pill bg-light text-muted border" id="projectBoxDataladStateBadge">Not tracked</span>
                            </div>
                            <div class="small text-muted mt-2" id="projectBoxDataladStatus">Checking DataLad status...</div>
                            <div class="small text-muted mt-1" id="projectBoxDataladHint">Project-scoped DataLad setup and manual saves live here.</div>
                            <div class="mt-2 d-none" id="projectBoxDataladProgressWrap">
                                <div class="small text-muted mb-1" id="projectBoxDataladProgressLabel"></div>
                                <div class="progress" style="height: 0.7rem;">
                                    <div class="progress-bar bg-success" id="projectBoxDataladProgressBar" role="progressbar" style="width: 0%;" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
                                </div>
                            </div>
                            <div class="small mt-2 d-none" id="projectBoxDataladFeedback" aria-live="polite"></div>
                        </div>
                        <div class="d-flex gap-2 flex-wrap justify-content-lg-end">
                            <button type="button" class="btn btn-sm btn-outline-primary" id="projectBoxDataladEnableBtn">
                                <i class="fas fa-plus me-1"></i>Enable DataLad
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-success" id="projectBoxDataladSaveBtn">
                                <i class="fas fa-floppy-disk me-1"></i>Save DataLad Snapshot
                            </button>
                        </div>
                    </div>
                </div>
                <div class="d-flex flex-column align-items-end mt-2">
                    <div class="d-flex gap-2 flex-wrap justify-content-end">
                        <button type="button" class="btn btn-outline-warning" id="projectBoxPreliminarySaveBtn">
                            <i class="fas fa-save me-2"></i>Save Preliminary Project State
                        </button>
                        <button type="button" class="btn btn-info" id="projectBoxSaveBtn">
                            <i class="fas fa-save me-2"></i>Save Changes to Project
                        </button>
                    </div>
                    <small class="text-muted mt-1" id="projectBoxSaveStatus" aria-live="polite"></small>
                </div>
            </div>
        `);
    }

    function getOpenProjectActionPath() {
        const existingPathInput = document.getElementById('existingPath');
        const enteredPath = existingPathInput ? String(existingPathInput.value || '').trim() : '';
        if (enteredPath) {
            return enteredPath;
        }
        return String(getCurrentProjectState().path || '').trim();
    }

    async function loadProjectWithoutValidation(path, triggerButton = null, options = {}) {
        const normalizedPath = String(path || '').trim();
        const skipContextGuard = Boolean(options.skipContextGuard);
        if (!normalizedPath) {
            showOpenProjectError('Please provide a project folder or a project.json path.', 'Selection Error');
            return false;
        }

        if (!skipContextGuard && !confirmProjectContextChange('load another project', normalizedPath)) {
            return false;
        }

        const originalText = triggerButton ? setButtonLoading(triggerButton, true, 'Loading...') : null;

        try {
            const response = await fetchWithApiFallback('/api/projects/current', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: normalizedPath })
            });
            const result = await response.json().catch(() => ({
                success: false,
                error: 'Server returned an invalid response while loading the project.'
            }));

            if (!response.ok || !result.success || !result.current || !result.current.path) {
                showOpenProjectError(result.error || `Project load failed (${response.status})`);
                return false;
            }

            applyCurrentProject(result.current);

            const currentState = getCurrentProjectState();
            const loadedPath = String(result.current.path || '').trim();
            const loadedName = String(result.current.name || currentState.name || '').trim();
            const projectSummary = result.project_summary && typeof result.project_summary === 'object' && !Array.isArray(result.project_summary)
                ? result.project_summary
                : null;
            addRecentProject(loadedName, loadedPath, currentState.icon);
            showStudyMetadataCard();
            updateCreateProjectButton();
            showExportCard();
            showMethodsCard();

            renderLoadedProjectState(loadedName, loadedPath, projectSummary);
            renderProjectBoxDataladState(currentState.datalad, loadedPath);
            bindProjectBoxActionButtons();
            bindProjectBoxDataladActions();
            updateCreateProjectButton();

            return true;
        } catch (error) {
            showOpenProjectError(error.message || 'Could not load the selected project.');
            return false;
        } finally {
            if (triggerButton) {
                setButtonLoading(triggerButton, false, null, originalText);
            }
        }
    }

    const openProjectForm = document.getElementById('openProjectForm');
    if (openProjectForm) {
        openProjectForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const btn = this.querySelector('button[type="submit"]');
            await loadProjectWithoutValidation(getOpenProjectActionPath(), btn);
        });
    }

    return {
        getOpenProjectActionPath,
        loadProjectWithoutValidation,
    };
}