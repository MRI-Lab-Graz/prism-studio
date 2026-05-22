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
    const DATALAD_PREFERENCES_NAMESPACE = 'datalad';
    const DATALAD_DEFAULT_COMMIT_MESSAGE = 'Checkpoint PRISM project changes';
    const DATALAD_DOCS_URL = 'https://www.datalad.org/';
    const DATALAD_INSTALL_COMMAND = 'uv tool install datalad git-annex';
    const DATALAD_SAVE_PROGRESS_STEPS = [
        { afterSeconds: 0, percent: 8, label: 'Starting DataLad snapshot...' },
        { afterSeconds: 8, percent: 22, label: 'Applying text-file tracking policy...' },
        { afterSeconds: 25, percent: 40, label: 'Scanning nested datasets...' },
        { afterSeconds: 60, percent: 58, label: 'Saving changed datasets recursively...' },
        { afterSeconds: 120, percent: 72, label: 'Collecting remaining metadata updates...' },
        { afterSeconds: 240, percent: 86, label: 'Large dataset save in progress (this can take several minutes)...' },
        { afterSeconds: 420, percent: 94, label: 'Almost done. Waiting for DataLad to finish...' },
    ];
    let dataladOptInPromptToken = 0;
    let dataladSaveProgressIntervalId = null;
    let dataladSaveProgressStartedAt = 0;

    function formatElapsedDuration(totalSeconds) {
        const seconds = Math.max(0, Number.parseInt(String(totalSeconds ?? ''), 10) || 0);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainder = seconds % 60;

        if (hours > 0) {
            return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
        }
        return `${minutes}:${String(remainder).padStart(2, '0')}`;
    }

    function getSaveProgressElements() {
        return {
            wrap: document.getElementById('projectBoxDataladSaveProgressWrap'),
            bar: document.getElementById('projectBoxDataladSaveProgressBar'),
            label: document.getElementById('projectBoxDataladSaveProgressLabel'),
        };
    }

    function stopProjectBoxDataladSaveProgress() {
        if (dataladSaveProgressIntervalId !== null) {
            window.clearInterval(dataladSaveProgressIntervalId);
            dataladSaveProgressIntervalId = null;
        }
        dataladSaveProgressStartedAt = 0;
    }

    function updateProjectBoxDataladSaveProgress(percent, message) {
        const { wrap, bar, label } = getSaveProgressElements();
        if (!wrap || !bar || !label) {
            return;
        }

        const normalizedPercent = Math.max(0, Math.min(100, Number.parseInt(String(percent ?? ''), 10) || 0));
        wrap.classList.remove('d-none');
        bar.style.width = `${normalizedPercent}%`;
        bar.setAttribute('aria-valuenow', String(normalizedPercent));
        bar.textContent = normalizedPercent >= 12 ? `${normalizedPercent}%` : '';
        label.textContent = String(message || '').trim();
    }

    function startProjectBoxDataladSaveProgress() {
        stopProjectBoxDataladSaveProgress();
        dataladSaveProgressStartedAt = Date.now();

        const { wrap, bar } = getSaveProgressElements();
        if (!wrap || !bar) {
            return;
        }

        bar.classList.remove('bg-success', 'bg-danger');
        bar.classList.add('bg-primary', 'progress-bar-striped', 'progress-bar-animated');

        const tick = () => {
            const elapsedSeconds = Math.floor((Date.now() - dataladSaveProgressStartedAt) / 1000);
            let activeStep = DATALAD_SAVE_PROGRESS_STEPS[0];

            for (const step of DATALAD_SAVE_PROGRESS_STEPS) {
                if (elapsedSeconds >= step.afterSeconds) {
                    activeStep = step;
                }
            }

            const elapsedText = formatElapsedDuration(elapsedSeconds);
            updateProjectBoxDataladSaveProgress(
                activeStep.percent,
                `${activeStep.label} Elapsed ${elapsedText}.`
            );
        };

        tick();
        dataladSaveProgressIntervalId = window.setInterval(tick, 1000);
    }

    function finishProjectBoxDataladSaveProgress(success = true, message = '') {
        const { wrap, bar, label } = getSaveProgressElements();
        if (!wrap || !bar || !label) {
            stopProjectBoxDataladSaveProgress();
            return;
        }

        const elapsedSeconds = dataladSaveProgressStartedAt > 0
            ? Math.floor((Date.now() - dataladSaveProgressStartedAt) / 1000)
            : 0;
        const elapsedText = formatElapsedDuration(elapsedSeconds);
        stopProjectBoxDataladSaveProgress();

        wrap.classList.remove('d-none');
        bar.classList.remove('bg-primary', 'progress-bar-striped', 'progress-bar-animated', 'bg-success', 'bg-danger');
        bar.classList.add(success ? 'bg-success' : 'bg-danger');
        bar.style.width = '100%';
        bar.setAttribute('aria-valuenow', '100');
        bar.textContent = '100%';

        const normalizedMessage = String(message || '').trim();
        label.textContent = normalizedMessage
            ? `${normalizedMessage} (${elapsedText})`
            : (success
                ? `DataLad snapshot complete in ${elapsedText}.`
                : `DataLad snapshot failed after ${elapsedText}.`);
    }

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

    function buildAutosaveFailureMessage(autosaveResult) {
        if (!autosaveResult || typeof autosaveResult !== 'object') {
            return '';
        }

        const attempted = Boolean(autosaveResult.attempted);
        const success = Boolean(autosaveResult.success);
        if (!attempted || success) {
            return '';
        }

        const baseMessage = String(
            autosaveResult.error
            || autosaveResult.message
            || 'Previous project DataLad auto-save failed.'
        ).trim();
        const reason = String(autosaveResult.reason || '').trim();
        if (!reason) {
            return baseMessage;
        }
        return `${baseMessage} (reason: ${reason})`;
    }

    function showAutosaveFailureFeedback(autosaveResult) {
        const message = buildAutosaveFailureMessage(autosaveResult);
        if (!message) {
            return;
        }

        setProjectBoxDataladFeedback(message, 'danger');
        window.setNavbarDataladFeedback?.(message, 'danger', 'Auto-save failed');
    }

    function normalizeDataladBoolean(value, defaultValue = false) {
        if (typeof value === 'boolean') {
            return value;
        }
        const normalized = String(value || '').trim().toLowerCase();
        if (normalized === 'true' || normalized === '1' || normalized === 'yes' || normalized === 'on') {
            return true;
        }
        if (normalized === 'false' || normalized === '0' || normalized === 'no' || normalized === 'off') {
            return false;
        }
        return Boolean(defaultValue);
    }

    function normalizeDataladSetupIntent(value) {
        const normalized = String(value || '').trim().toLowerCase();
        if (normalized === 'enabled' || normalized === 'declined') {
            return normalized;
        }
        return 'unknown';
    }

    function normalizeDataladAskOnOpen(value, defaultValue = true) {
        return normalizeDataladBoolean(value, defaultValue);
    }

    function getDataladOperationState() {
        const state = window.prismDataladOperationState;
        if (!state || typeof state !== 'object' || Array.isArray(state)) {
            return { active: false, source: '' };
        }
        return {
            active: Boolean(state.active),
            source: String(state.source || '').trim(),
        };
    }

    function setDataladOperationState(active, source = '') {
        window.prismDataladOperationState = {
            active: Boolean(active),
            source: String(source || '').trim(),
        };
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
                setupIntent: 'unknown',
                askOnOpen: true,
                subdatasetsTotalCount: 0,
                subdatasetsRegisteredCount: 0,
                subdatasetsRemainingCount: 0,
                subdatasetsProgressPercent: 0,
                nextMissingSubdataset: '',
                textPolicyMissingCount: 0,
            };
        }

        const message = typeof dataladState.message === 'string' && dataladState.message.trim()
            ? dataladState.message.trim()
            : defaultMessage;
        const setupIntent = normalizeDataladSetupIntent(dataladState.setup_intent ?? dataladState.setupIntent);

        return {
            enabled: normalizeDataladBoolean(dataladState.enabled),
            available: normalizeDataladBoolean(dataladState.available),
            annexAvailable: normalizeDataladBoolean(dataladState.annex_available ?? dataladState.annexAvailable),
            canSave: normalizeDataladBoolean(dataladState.can_save ?? dataladState.canSave),
            canEnable: normalizeDataladBoolean(dataladState.can_enable ?? dataladState.canEnable),
            message,
            path: resolvedPath,
            setupIntent,
            askOnOpen: normalizeDataladAskOnOpen(
                dataladState.ask_on_open ?? dataladState.askOnOpen,
                setupIntent !== 'enabled'
            ),
            subdatasetsTotalCount: normalizeCount(dataladState.subdatasets_total_count ?? dataladState.subdatasetsTotalCount),
            subdatasetsRegisteredCount: normalizeCount(dataladState.subdatasets_registered_count ?? dataladState.subdatasetsRegisteredCount),
            subdatasetsRemainingCount: normalizeCount(dataladState.subdatasets_remaining_count ?? dataladState.subdatasetsRemainingCount),
            subdatasetsProgressPercent: normalizeCount(dataladState.subdatasets_progress_percent ?? dataladState.subdatasetsProgressPercent),
            nextMissingSubdataset: typeof (dataladState.next_missing_subdataset ?? dataladState.nextMissingSubdataset) === 'string'
                ? String(dataladState.next_missing_subdataset ?? dataladState.nextMissingSubdataset).trim()
                : '',
            textPolicyMissingCount: normalizeCount(dataladState.text_policy_missing_count ?? dataladState.textPolicyMissingCount),
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
            const hasNestedRepairsRemaining = state.subdatasetsRemainingCount > 0;
            if (hasNestedRepairsRemaining) {
                hint.textContent = 'This project is already DataLad-tracked. Use Repair DataLad Structure to backfill one missing nested dataset per click, or Save DataLad Snapshot for an explicit checkpoint.';
                enableButton.innerHTML = '<i class="fas fa-screwdriver-wrench me-1"></i>Repair DataLad Structure';
                enableButton.disabled = false;
                enableButton.title = 'Repair or complete DataLad setup for the current project';
            } else {
                if (state.textPolicyMissingCount > 0) {
                    hint.textContent = `DataLad structure is complete, but text-file Git tracking policy is missing in ${state.textPolicyMissingCount} dataset(s). Use Save DataLad Snapshot to apply policy and create a checkpoint.`;
                } else {
                    hint.textContent = 'DataLad structure is complete for this project. Use Save DataLad Snapshot for an explicit checkpoint.';
                }
                enableButton.innerHTML = '<i class="fas fa-check me-1"></i>DataLad Structure Complete';
                enableButton.disabled = true;
                enableButton.title = state.textPolicyMissingCount > 0
                    ? 'Use Save DataLad Snapshot to apply text-file policy'
                    : 'No missing nested datasets to repair';
            }
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

        if (!state.enabled && state.setupIntent === 'declined' && !state.askOnOpen) {
            hint.textContent = 'DataLad setup is currently skipped for this project. Use Enable DataLad any time to opt in.';
        }

        const operationState = getDataladOperationState();
        if (operationState.active) {
            enableButton.disabled = true;
            saveButton.disabled = true;
        }
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

    function normalizeDataladPreferences(preferences, fallbackState = null) {
        const fallback = fallbackState || {};
        const setupIntent = normalizeDataladSetupIntent(
            preferences?.setup_intent
            ?? preferences?.setupIntent
            ?? fallback.setupIntent
            ?? fallback.setup_intent
        );
        return {
            setup_intent: setupIntent,
            ask_on_open: normalizeDataladAskOnOpen(
                preferences?.ask_on_open ?? preferences?.askOnOpen,
                setupIntent !== 'enabled'
            ),
        };
    }

    function applyDataladPreferencePatchToState(preferencesPatch = {}) {
        const currentState = getCurrentProjectState();
        const currentPath = String(currentState.path || '').trim();
        if (!currentPath) {
            return;
        }

        const currentDatalad = normalizeDataladState(currentState.datalad, currentPath);
        const nextSetupIntent = normalizeDataladSetupIntent(
            preferencesPatch.setup_intent
            ?? preferencesPatch.setupIntent
            ?? currentDatalad.setupIntent
        );
        const nextAskOnOpen = normalizeDataladAskOnOpen(
            preferencesPatch.ask_on_open ?? preferencesPatch.askOnOpen,
            nextSetupIntent !== 'enabled'
        );
        const nextDatalad = {
            ...currentDatalad,
            setupIntent: nextSetupIntent,
            askOnOpen: nextAskOnOpen,
        };

        applyCurrentProject({
            ...currentState,
            path: currentPath,
            datalad: nextDatalad,
        });
        renderProjectBoxDataladState(nextDatalad, currentPath);
    }

    async function loadDataladPreferences(projectPath) {
        const normalizedPath = String(projectPath || '').trim();
        const fallbackState = normalizeDataladState(getCurrentProjectState().datalad, normalizedPath);
        if (!normalizedPath) {
            return normalizeDataladPreferences({}, fallbackState);
        }

        try {
            const query = encodeURIComponent(normalizedPath);
            const response = await fetchWithApiFallback(`/api/projects/preferences/${DATALAD_PREFERENCES_NAMESPACE}?project_path=${query}`);
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Could not load DataLad preferences.');
            }

            const normalized = normalizeDataladPreferences(data.preferences, fallbackState);
            applyDataladPreferencePatchToState(normalized);
            return normalized;
        } catch (error) {
            console.warn('Could not load DataLad preferences:', error);
            return normalizeDataladPreferences({}, fallbackState);
        }
    }

    async function saveDataladPreferences(projectPath, preferencesPatch) {
        const normalizedPath = String(projectPath || '').trim();
        if (!normalizedPath) {
            return null;
        }

        const fallbackState = normalizeDataladState(getCurrentProjectState().datalad, normalizedPath);
        const normalizedPatch = normalizeDataladPreferences(preferencesPatch, fallbackState);
        const response = await fetchWithApiFallback(`/api/projects/preferences/${DATALAD_PREFERENCES_NAMESPACE}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_path: normalizedPath,
                preferences: normalizedPatch,
            }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Could not save DataLad preferences.');
        }

        const normalizedResponse = normalizeDataladPreferences(data.preferences, fallbackState);
        applyDataladPreferencePatchToState(normalizedResponse);
        return normalizedResponse;
    }

    function getDataladLockMessage(operationState) {
        if (operationState?.source === 'navbar_save') {
            return 'A DataLad save is already running from the navbar. Please wait for it to finish.';
        }
        if (operationState?.source === 'project_box_enable') {
            return 'A DataLad enable/repair action is already running. Please wait for it to finish.';
        }
        if (operationState?.source === 'project_box_save') {
            return 'A DataLad save is already running. Please wait for it to finish.';
        }
        return 'Another DataLad action is already running. Please wait for it to finish.';
    }

    function confirmEnableDatalad(currentPath) {
        return window.confirm(
            'Are you absolutely sure that you want DataLad conversion/tracking for this project?\n\n'
            + 'This will modify the project in place by creating or repairing DataLad/Git metadata, backfilling one missing nested dataset for this click, and saving a snapshot.\n\n'
            + `Learn more: ${DATALAD_DOCS_URL}\n\n`
            + 'Only continue if you explicitly want DataLad for this dataset.\n\n'
            + `Project: ${currentPath}`
        );
    }

    function buildMissingDataladToolsMessage(dataladState) {
        const state = normalizeDataladState(dataladState);
        const missingTools = [];
        if (!state.available) {
            missingTools.push('DataLad');
        }
        if (!state.annexAvailable) {
            missingTools.push('git-annex');
        }

        const missingToolsLabel = missingTools.length > 1
            ? `${missingTools.slice(0, -1).join(', ')} and ${missingTools[missingTools.length - 1]}`
            : (missingTools[0] || 'Required DataLad tools');
        const singularTool = missingTools.length === 1;

        return [
            `${missingToolsLabel} ${singularTool ? 'is' : 'are'} not available in this environment.`,
            '',
            'Install the missing tools before enabling DataLad tracking for this project.',
            `Suggested install command: ${DATALAD_INSTALL_COMMAND}`,
            `Learn more: ${DATALAD_DOCS_URL}`,
        ].join('\n');
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

    async function runProjectBoxEnableDatalad(currentPath, { skipConfirmation = false } = {}) {
        const normalizedPath = String(currentPath || '').trim();
        if (!normalizedPath) {
            setProjectBoxDataladFeedback('Load a project first.', 'danger');
            window.setNavbarDataladFeedback?.('Load a project first.', 'danger', 'Error');
            return false;
        }

        const operationState = getDataladOperationState();
        if (operationState.active) {
            const lockMessage = getDataladLockMessage(operationState);
            setProjectBoxDataladFeedback(lockMessage, 'danger');
            window.setNavbarDataladFeedback?.(lockMessage, 'danger', 'Busy');
            return false;
        }

        if (!skipConfirmation && !confirmEnableDatalad(normalizedPath)) {
            setProjectBoxDataladFeedback('DataLad enable cancelled.', 'muted');
            window.setNavbarDataladFeedback?.('DataLad enable cancelled.', 'muted', 'Cancelled');
            return false;
        }

        const enableButton = document.getElementById('projectBoxDataladEnableBtn');
        const saveButton = document.getElementById('projectBoxDataladSaveBtn');
        const originalEnableMarkup = enableButton?.innerHTML || '';
        const originalSaveDisabled = Boolean(saveButton?.disabled);

        const currentDataladState = normalizeDataladState(getCurrentProjectState().datalad, normalizedPath);
        const busyLabel = currentDataladState.enabled ? 'Repairing...' : 'Enabling...';
        const busyMarkup = `<i class="fas fa-spinner fa-spin me-1"></i>${busyLabel}`;
        if (enableButton) {
            enableButton.disabled = true;
            enableButton.innerHTML = busyMarkup;
        }
        if (saveButton) {
            saveButton.disabled = true;
        }

        const repairTarget = currentDataladState.nextMissingSubdataset || 'the next nested dataset';
        const pendingMessage = `Repairing ${repairTarget}. Large tracked folders can take a while. Watch the backend terminal for progress.`;
        setProjectBoxDataladFeedback(pendingMessage, 'muted');
        window.setNavbarDataladFeedback?.(pendingMessage, 'muted', 'Running');

        const actionState = { active: true };
        setDataladOperationState(true, 'project_box_enable');
        const pollingPromise = pollCurrentProjectDataladStateWhileBusy({
            currentPath: normalizedPath,
            actionState,
            busyMarkup,
            fallbackTarget: repairTarget,
        });

        try {
            const response = await fetchWithApiFallback('/api/projects/datalad/enable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirmed: true }),
            });
            const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
            if (!response.ok || !data.success) {
                throw new Error(data.error || data.message || 'Could not enable DataLad.');
            }

            applyProjectDataladResponse(data);
            const successMessage = data.message || (data.datalad && data.datalad.message) || 'DataLad enabled.';
            setProjectBoxDataladFeedback(successMessage, 'success');
            window.setNavbarDataladFeedback?.(successMessage, 'success', 'Enabled');
            return true;
        } catch (error) {
            const errorMessage = error.message || 'Could not enable DataLad.';
            setProjectBoxDataladFeedback(errorMessage, 'danger');
            window.setNavbarDataladFeedback?.(errorMessage, 'danger', 'Error');
            return false;
        } finally {
            actionState.active = false;
            await pollingPromise.catch(() => {});
            setDataladOperationState(false);
            if (enableButton) {
                enableButton.innerHTML = originalEnableMarkup;
            }
            if (saveButton) {
                saveButton.disabled = originalSaveDisabled;
            }
            renderProjectBoxDataladState(getCurrentProjectState().datalad, normalizedPath);
        }
    }

    async function maybePromptDataladOptIn(projectPath) {
        const normalizedPath = String(projectPath || '').trim();
        if (!normalizedPath) {
            return;
        }

        const promptToken = ++dataladOptInPromptToken;
        const currentDataladState = normalizeDataladState(getCurrentProjectState().datalad, normalizedPath);
        if (currentDataladState.enabled) {
            return;
        }

        const preferences = await loadDataladPreferences(normalizedPath);
        if (promptToken !== dataladOptInPromptToken) {
            return;
        }

        if (!preferences.ask_on_open || preferences.setup_intent === 'enabled') {
            return;
        }

        const persistDeclinedChoice = async (skipPromptMessage = '') => {
            const askAgain = window.confirm(
                skipPromptMessage ||
                'DataLad setup skipped for now.\n\nClick OK to ask again next time this project opens.\nClick Cancel to stop asking for this project.'
            );
            const declinedPreferences = {
                setup_intent: 'declined',
                ask_on_open: Boolean(askAgain),
            };
            try {
                await saveDataladPreferences(normalizedPath, declinedPreferences);
            } catch (error) {
                console.warn('Could not persist declined DataLad setup preference:', error);
                applyDataladPreferencePatchToState(declinedPreferences);
            }

            const declinedMessage = askAgain
                ? 'DataLad setup skipped. PRISM will ask again next time you open this project.'
                : 'DataLad setup skipped. PRISM will stop asking for this project unless you enable DataLad manually.';
            setProjectBoxDataladFeedback(declinedMessage, 'muted');
            window.setNavbarDataladFeedback?.(declinedMessage, 'muted', askAgain ? 'Later' : 'Skipped');
        };

        const confirmMessage = [
            'Enable DataLad conversion/tracking for this project?',
            '',
            'Choose Yes to enable DataLad now. Choose No to keep this project untracked for now.',
            '',
            'PRISM can work without DataLad. Enabling DataLad modifies the project in place by creating or repairing DataLad/Git metadata and writing a snapshot.',
            '',
            `Learn more: ${DATALAD_DOCS_URL}`,
            '',
            `Project: ${normalizedPath}`,
        ].join('\n');
        const shouldEnable = window.confirm(confirmMessage);
        if (promptToken !== dataladOptInPromptToken) {
            return;
        }

        if (!shouldEnable) {
            await persistDeclinedChoice();
            return;
        }

        const latestDataladState = normalizeDataladState(getCurrentProjectState().datalad, normalizedPath);
        if (!latestDataladState.canEnable) {
            const unavailableToolsMessage = buildMissingDataladToolsMessage(latestDataladState);
            window.alert(unavailableToolsMessage);

            const shortUnavailableMessage = latestDataladState.available && !latestDataladState.annexAvailable
                ? `DataLad setup blocked: git-annex is missing. Install tools with "${DATALAD_INSTALL_COMMAND}" and try again.`
                : `DataLad setup blocked: DataLad and git-annex are missing. Install tools with "${DATALAD_INSTALL_COMMAND}" and try again.`;
            setProjectBoxDataladFeedback(shortUnavailableMessage, 'danger');
            window.setNavbarDataladFeedback?.(shortUnavailableMessage, 'danger', 'Missing tools');
            await persistDeclinedChoice(
                'DataLad tools are missing on this machine.\n\nClick OK to ask again next time this project opens after you install the tools.\nClick Cancel to stop asking for this project.'
            );
            return;
        }

        const absolutelySureMessage = [
            'Are you absolutely sure that you want a DataLad conversion/tracking setup for this project?',
            '',
            'This action modifies the project in place by creating or repairing DataLad/Git metadata and writing a snapshot.',
            '',
            `Learn more: ${DATALAD_DOCS_URL}`,
            '',
            `Project: ${normalizedPath}`,
        ].join('\n');
        const absolutelySure = window.confirm(absolutelySureMessage);
        if (promptToken !== dataladOptInPromptToken) {
            return;
        }
        if (!absolutelySure) {
            await persistDeclinedChoice(
                'DataLad setup cancelled before enable.\n\nClick OK to ask again next time this project opens.\nClick Cancel to stop asking for this project.'
            );
            return;
        }

        const optimisticEnabledPreferences = {
            setup_intent: 'enabled',
            ask_on_open: false,
        };
        try {
            await saveDataladPreferences(normalizedPath, optimisticEnabledPreferences);
        } catch (error) {
            console.warn('Could not persist pre-enable DataLad preference:', error);
            applyDataladPreferencePatchToState(optimisticEnabledPreferences);
        }

        const enabled = await runProjectBoxEnableDatalad(normalizedPath, { skipConfirmation: true });
        if (enabled) {
            return;
        }

        const retryPreferences = {
            setup_intent: 'unknown',
            ask_on_open: true,
        };
        try {
            await saveDataladPreferences(normalizedPath, retryPreferences);
        } catch (error) {
            console.warn('Could not persist retry DataLad preference state:', error);
            applyDataladPreferencePatchToState(retryPreferences);
        }
    }

    function bindProjectBoxDataladActions() {
        const enableButton = document.getElementById('projectBoxDataladEnableBtn');
        if (enableButton && enableButton.dataset.bound !== '1') {
            enableButton.dataset.bound = '1';
            enableButton.addEventListener('click', async function() {
                const currentPath = String(getCurrentProjectState().path || '').trim();
                await runProjectBoxEnableDatalad(currentPath);
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

                const operationState = getDataladOperationState();
                if (operationState.active) {
                    const lockMessage = getDataladLockMessage(operationState);
                    setProjectBoxDataladFeedback(lockMessage, 'danger');
                    window.setNavbarDataladFeedback?.(lockMessage, 'danger', 'Busy');
                    return;
                }

                const requestedMessage = window.prompt('Commit message for this checkpoint', DATALAD_DEFAULT_COMMIT_MESSAGE);
                if (requestedMessage === null) {
                    return;
                }

                const saveMessage = String(requestedMessage || '').trim() || DATALAD_DEFAULT_COMMIT_MESSAGE;
                const originalText = saveButton.innerHTML;
                const enableButton = document.getElementById('projectBoxDataladEnableBtn');
                const originalEnableDisabled = Boolean(enableButton?.disabled);
                saveButton.disabled = true;
                if (enableButton) {
                    enableButton.disabled = true;
                }
                saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
                setProjectBoxDataladFeedback('', 'muted');
                setDataladOperationState(true, 'project_box_save');
                startProjectBoxDataladSaveProgress();

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
                    finishProjectBoxDataladSaveProgress(true, successMessage);
                } catch (error) {
                    const errorMessage = error.message || 'Could not save DataLad changes.';
                    setProjectBoxDataladFeedback(errorMessage, 'danger');
                    window.setNavbarDataladFeedback?.(errorMessage, 'danger', 'Error');
                    finishProjectBoxDataladSaveProgress(false, errorMessage);
                } finally {
                    setDataladOperationState(false);
                    saveButton.innerHTML = originalText;
                    if (enableButton) {
                        enableButton.disabled = originalEnableDisabled;
                    }
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
                            <div class="mt-2 d-none" id="projectBoxDataladSaveProgressWrap">
                                <div class="small text-muted mb-1" id="projectBoxDataladSaveProgressLabel"></div>
                                <div class="progress" style="height: 0.85rem;">
                                    <div class="progress-bar bg-primary progress-bar-striped progress-bar-animated" id="projectBoxDataladSaveProgressBar" role="progressbar" style="width: 0%;" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
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
            showAutosaveFailureFeedback(result.autosave_previous);
            await maybePromptDataladOptIn(loadedPath);

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