import { isSameProjectPath } from '../../shared/project-state.js';

export const DATALAD_DOCS_URL = 'https://www.datalad.org/';
export const DATALAD_INSTALL_COMMAND = 'uv tool install datalad --with-executables-from git-annex';

// The DataLad card (state, enable/repair, snapshot) for the loaded project. It lives on the
// Settings page; the open-project flow shares this code for the opt-in prompt and the summary row.
export function createDataladCard({
    fetchWithApiFallback,
    getCurrentProjectState,
    applyCurrentProject,
}) {
    const DATALAD_DEFAULT_COMMIT_MESSAGE = 'Checkpoint PRISM project changes';
    const DATALAD_SAVE_PROGRESS_STEPS = [
        { afterSeconds: 0, percent: 8, label: 'Starting DataLad snapshot...' },
        { afterSeconds: 8, percent: 22, label: 'Applying text-file tracking policy...' },
        { afterSeconds: 25, percent: 40, label: 'Scanning nested datasets...' },
        { afterSeconds: 60, percent: 58, label: 'Saving changed datasets recursively...' },
        { afterSeconds: 120, percent: 72, label: 'Collecting remaining metadata updates...' },
        { afterSeconds: 240, percent: 86, label: 'Large dataset save in progress (this can take several minutes)...' },
        { afterSeconds: 420, percent: 94, label: 'Almost done. Waiting for DataLad to finish...' },
    ];
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
                installCommand: '',
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
            installCommand: String(dataladState.install_command ?? '').trim(),
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
        const summaryState = normalizeDataladState(dataladState, fallbackPath);
        const loadedSummary = document.getElementById('projectLoadedDataladSummary');
        if (loadedSummary) {
            loadedSummary.textContent = summaryState.enabled
                ? (summaryState.available
                    ? 'This project is DataLad-tracked.'
                    : 'This project is DataLad-tracked, but DataLad isn\'t available here.')
                : 'DataLad version control isn\'t set up for this project yet.';
        }

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
                hint.textContent = `This project is already DataLad-tracked. ${state.subdatasetsRemainingCount} nested dataset(s) still need to be registered — click Register Nested Dataset to register one per click, or Save DataLad Snapshot for an explicit checkpoint.`;
                enableButton.innerHTML = '<i class="fas fa-link me-1"></i>Register Nested Dataset';
                enableButton.disabled = false;
                enableButton.title = 'Register the next missing nested dataset for the current project';
            } else {
                hint.textContent = 'DataLad structure is complete for this project. Use Save DataLad Snapshot for an explicit checkpoint.';
                enableButton.innerHTML = '<i class="fas fa-check me-1"></i>DataLad Structure Complete';
                enableButton.disabled = true;
                enableButton.title = 'No missing nested datasets to register';
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
                ? 'DataLad adds Git-based version control to your project, useful for tracking changes over time. Click Enable DataLad to get started.'
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
            hint.textContent = 'DataLad version control is not enabled for this project. Use Enable DataLad any time to opt in.';
        }

        const operationState = getDataladOperationState();
        if (operationState.active) {
            enableButton.disabled = true;
            saveButton.disabled = true;
        }
    }

    function refreshDataladStatusDeep(expectedPath) {
        // The fast project-load path skips the per-subdataset `git annex find`
        // scan (slow on datasets with many nested subdatasets). Fetch the full
        // scan afterwards, non-blocking, so the DataLad card fills in without
        // delaying the initial page render.
        fetchWithApiFallback('/api/projects/datalad/status-deep')
            .then((response) => response.json().catch(() => null))
            .then((data) => {
                if (!data || !data.success) {
                    return;
                }
                const currentState = getCurrentProjectState();
                if (String(currentState.path || '').trim() !== String(expectedPath || '').trim()) {
                    // The user already switched projects; discard this stale result.
                    return;
                }
                applyCurrentProject({ ...currentState, datalad: data.datalad });
                renderProjectBoxDataladState(data.datalad, expectedPath);
            })
            .catch(() => {
                // Best-effort enhancement only; the fast status already rendered.
            });
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

    function confirmEnableDatalad(currentPath, { isRepair = false } = {}) {
        if (isRepair) {
            return window.confirm(
                'Register the next missing nested dataset for this project?\n\n'
                + 'This project is already DataLad-tracked. This step only backfills one missing nested dataset registration and saves a snapshot; it does not change your existing DataLad setup.\n\n'
                + 'Answer Yes (OK) to continue, or No (Cancel) to skip this click.\n\n'
                + `Learn more: ${DATALAD_DOCS_URL}\n\n`
                + `Project: ${currentPath}`
            );
        }

        return window.confirm(
            'Are you absolutely sure that you want DataLad conversion/tracking for this project?\n\n'
            + 'This will modify the project in place by creating DataLad/Git metadata and saving a snapshot.\n\n'
            + 'Answer Yes (OK) to continue, or No (Cancel) to keep the current setup.\n\n'
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
            `Suggested install command: ${state.installCommand || DATALAD_INSTALL_COMMAND}`,
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
                if (!isSameProjectPath(responsePath, normalizedPath)) {
                    continue;
                }

                applyCurrentProject(current);
                renderProjectBoxDataladState(current.datalad, normalizedPath);

                const liveDataladState = normalizeDataladState(current.datalad, normalizedPath);
                const liveTarget = liveDataladState.nextMissingSubdataset || fallbackTarget || 'the next nested dataset';
                const liveMessage = `Working on ${liveTarget}. Large tracked folders can take a while. Watch the backend terminal for progress.`;
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

        const currentDataladState = normalizeDataladState(getCurrentProjectState().datalad, normalizedPath);
        const isRepair = currentDataladState.enabled;

        if (!skipConfirmation && !confirmEnableDatalad(normalizedPath, { isRepair })) {
            const cancelMessage = isRepair ? 'DataLad repair cancelled.' : 'DataLad enable cancelled.';
            setProjectBoxDataladFeedback(cancelMessage, 'muted');
            window.setNavbarDataladFeedback?.(cancelMessage, 'muted', 'Cancelled');
            return false;
        }

        const enableButton = document.getElementById('projectBoxDataladEnableBtn');
        const saveButton = document.getElementById('projectBoxDataladSaveBtn');
        const originalEnableMarkup = enableButton?.innerHTML || '';
        const originalSaveDisabled = Boolean(saveButton?.disabled);

        const busyLabel = currentDataladState.enabled ? 'Working on...' : 'Enabling...';
        const busyMarkup = `<i class="fas fa-spinner fa-spin me-1"></i>${busyLabel}`;
        if (enableButton) {
            enableButton.disabled = true;
            enableButton.innerHTML = busyMarkup;
        }
        if (saveButton) {
            saveButton.disabled = true;
        }

        const repairTarget = currentDataladState.nextMissingSubdataset || 'the next nested dataset';
        const pendingMessage = `Working on ${repairTarget}. Large tracked folders can take a while. Watch the backend terminal for progress.`;
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
            // Each backend call converts as many nested subdatasets as fit in its
            // own time budget (see NESTED_SUBDATASET_ENABLE_CLICK_MAX_SECONDS) and
            // reports how many are still missing. Loop here instead of requiring
            // one manual click per subject -- a dataset with 100+ subjects would
            // otherwise need 100+ clicks to finish.
            let data = null;
            let iterations = 0;
            const MAX_ITERATIONS = 500;
            // A call that reports a real failure (not just "ran out of time
            // budget mid-fetch") and converted nothing is a stall, not
            // progress. A single stall can be transient (e.g. a one-off lock
            // collision that outlasted the backend's own retries) and is
            // worth another attempt, but repeated stalls on the same item
            // mean a genuine, non-transient error -- stop and surface it
            // instead of silently grinding through up to MAX_ITERATIONS
            // (500 x up to 90s each = ~12.5 hours) with no visible progress.
            const MAX_CONSECUTIVE_STALLS = 3;
            let consecutiveStalls = 0;
            for (;;) {
                iterations += 1;
                const response = await fetchWithApiFallback('/api/projects/datalad/enable', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirmed: true }),
                });
                data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
                if (!response.ok || !data.success) {
                    throw new Error(data.error || data.message || 'Could not enable DataLad.');
                }

                applyProjectDataladResponse(data);

                const remaining = Number.parseInt(String(data.datalad?.subdatasets_remaining_count ?? 0), 10) || 0;
                if (remaining <= 0 || iterations >= MAX_ITERATIONS) {
                    break;
                }

                const createdThisCall = data.datalad?.subdatasets_created?.length ?? 0;
                const failuresThisCall = data.datalad?.subdataset_failures ?? [];
                if (createdThisCall === 0 && failuresThisCall.length > 0) {
                    consecutiveStalls += 1;
                    if (consecutiveStalls >= MAX_CONSECUTIVE_STALLS) {
                        throw new Error(
                            `Registration is stuck on the same nested dataset after ${consecutiveStalls} ` +
                            `attempts and made no further progress: ${failuresThisCall[0]}`
                        );
                    }
                } else {
                    consecutiveStalls = 0;
                }

                const nextTarget = data.datalad?.next_missing_subdataset || 'the next nested dataset';
                const continueMessage = `${remaining} nested dataset(s) remaining. Continuing with ${nextTarget}...`;
                setProjectBoxDataladFeedback(continueMessage, 'muted');
                window.setNavbarDataladFeedback?.(continueMessage, 'muted', 'Running');
            }

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

    function showDataladCard() {
        const card = document.getElementById('dataladSectionCard');
        if (!card) return;
        const path = String(getCurrentProjectState().path || '').trim();
        card.style.display = path ? 'block' : 'none';
        if (!path) return;

        bindProjectBoxDataladActions();
        renderProjectBoxDataladState(getCurrentProjectState().datalad, path);

        fetchWithApiFallback('/api/projects/current')
            .then((response) => response.json().catch(() => null))
            .then((current) => {
                if (!current || typeof current !== 'object') return;
                const currentPath = String(current.path || '').trim();
                if (!isSameProjectPath(currentPath, path)) return; // user navigated to a different project meanwhile
                applyCurrentProject(current);
                renderProjectBoxDataladState(current.datalad, currentPath);
                if (current.datalad && current.datalad.enabled) {
                    refreshDataladStatusDeep(currentPath);
                }
            })
            .catch(() => {
                // Best-effort enhancement only; the state from getCurrentProjectState() already rendered.
            });
    }

    return {
        normalizeDataladSetupIntent,
        normalizeDataladAskOnOpen,
        normalizeProjectSummaryCount,
        normalizeProjectSummaryLabels,
        normalizeDataladState,
        setProjectBoxDataladFeedback,
        renderProjectBoxDataladState,
        buildMissingDataladToolsMessage,
        runProjectBoxEnableDatalad,
        showDataladCard,
    };
}
