import { isSameProjectPath } from '../../shared/project-state.js';
import { createDataladCard, DATALAD_DOCS_URL, DATALAD_INSTALL_COMMAND } from './datalad-card.js';

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
    showMethodsCard,
    bindProjectBoxActionButtons,
}) {
    const DATALAD_PREFERENCES_NAMESPACE = 'datalad';
    let dataladOptInPromptToken = 0;
    const {
        buildMissingDataladToolsMessage,
        normalizeDataladAskOnOpen,
        normalizeDataladSetupIntent,
        normalizeDataladState,
        normalizeProjectSummaryCount,
        normalizeProjectSummaryLabels,
        renderProjectBoxDataladState,
        runProjectBoxEnableDatalad,
        setProjectBoxDataladFeedback,
    } = createDataladCard({ fetchWithApiFallback, getCurrentProjectState, applyCurrentProject });

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
            'In this dialog: OK = Yes, Cancel = No.',
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
                ? `DataLad setup blocked: git-annex is missing. Install tools with "${latestDataladState.installCommand || DATALAD_INSTALL_COMMAND}" and try again.`
                : `DataLad setup blocked: DataLad and git-annex are missing. Install tools with "${latestDataladState.installCommand || DATALAD_INSTALL_COMMAND}" and try again.`;
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
            'In this dialog: OK = Yes, Cancel = No.',
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

        // A shallow summary answers from project.json and one directory read,
        // so subjects and the root-file checks are exact but sessions and
        // modalities are only what the project declares. Show those two as
        // still-counting rather than as disk facts.
        const isCounting = summary.scan === 'shallow';
        const countingMark = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span><span class="visually-hidden">counting</span>';
        const sessionsValue = isCounting ? countingMark : String(sessions);
        const modalitiesValue = isCounting ? countingMark : String(modalities);

        // No subjects means no real data has been imported yet -- the 5-tile
        // grid is mostly padding around zeroes at that point, so collapse it
        // to one line until there's something to actually show.
        const isEmptyProject = subjects === 0;

        const datasetDescriptionMark = hasDatasetDescription
            ? '<span class="text-success">&check;</span>' : '<span class="text-danger">&#10007;</span>';
        const participantsTsvMark = hasParticipantsTsv
            ? '<span class="text-success">&check;</span>' : '<span class="text-danger">&#10007;</span>';

        const statsHtml = isEmptyProject ? `
            <div class="small text-muted mt-1">
                0 subjects &middot; 0 sessions &middot; 0 modalities &middot;
                dataset_description ${datasetDescriptionMark} &middot;
                participants.tsv ${participantsTsvMark}
            </div>
        ` : `
            <div class="stats-grid mt-2">
                <div class="stat-item">
                    <div class="stat-value">${subjects}</div>
                    <div class="stat-label">Subjects</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${sessionsValue}</div>
                    <div class="stat-label">Sessions</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${modalitiesValue}</div>
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
        `;

        let caption = '<i class="fas fa-database me-1"></i>Snapshot from folders currently found on disk.';
        if (isCounting) {
            caption = '<i class="fas fa-bolt me-1"></i>Read from project.json. Counting folders on disk&hellip;';
        } else if (summary.scan === 'declared') {
            caption = '<i class="fas fa-file-lines me-1"></i>Declared in project.json &ndash; could not count folders on disk.';
        }

        return `
            <div class="small text-muted mb-2">${caption}</div>
            ${statsHtml}
            ${modalityText ? `
                <div class="small text-muted mt-2"><strong>Modalities:</strong> ${modalityText}${hiddenModalityCount > 0 ? ` (+${hiddenModalityCount} more)` : ''}</div>
            ` : ''}
            ${sessionText ? `
                <div class="small text-muted mt-1"><strong>Sessions:</strong> ${sessionText}${hiddenSessionCount > 0 ? ` (+${hiddenSessionCount} more)` : ''}</div>
            ` : ''}
        `;
    }

    let lastShallowProjectSummary = null;

    async function refreshProjectQuickSummary() {
        const container = document.getElementById('projectQuickSummary');
        if (!container) return;
        try {
            const response = await fetchWithApiFallback('/api/projects/summary');
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success || !data.project_summary) {
                throw new Error(data.error || 'Summary unavailable');
            }
            container.innerHTML = renderProjectQuickSummary(data.project_summary);
        } catch (error) {
            // Keep the declared numbers rather than an endless spinner.
            const fallback = lastShallowProjectSummary
                ? { ...lastShallowProjectSummary, scan: 'declared' }
                : null;
            container.innerHTML = renderProjectQuickSummary(fallback);
        }
    }

    function renderLoadedProjectState(loadedName, loadedPath, summary) {
        const quickSummaryHtml = renderProjectQuickSummary(summary);
        const projectIconClass = escapeHtml(resolveProjectIconClass(getCurrentProjectState().icon));
        setProjectValidationResult(`
            <div class="validation-result pending project-loaded-state">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                    <h5 class="mb-0"><i class="fas fa-folder-open me-2"></i>Project Loaded</h5>
                    <div class="d-flex align-items-center gap-2 flex-wrap" id="projectLoadedMetadataReminder">
                        <span class="small text-muted">Study Metadata:</span>
                        <span class="badge bg-danger" id="projectLoadedRequiredBadge" title="Required to create the project">Required &hellip;/&hellip;</span>
                        <span class="badge badge-tier-core" id="projectLoadedCoreBadge" title="Drives the Methods Readiness / FAIR score">Core &hellip;/&hellip;</span>
                        <span class="badge bg-warning text-dark" id="projectLoadedFairBadge" title="Optional fields that also count toward FAIR readiness">FAIR &hellip;/&hellip;</span>
                    </div>
                </div>
                <p class="mb-1 mt-2"><strong><span class="me-1" aria-hidden="true">${projectIconClass}</span>${escapeHtml(loadedName || 'Current project')}:</strong> <code>${escapeHtml(loadedPath)}</code></p>
                <div id="projectQuickSummary">${quickSummaryHtml}</div>
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
                <div class="alert alert-light border mt-3 mb-0 d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2" role="status">
                    <div>
                        <strong><i class="fas fa-code-branch me-1"></i>Version control</strong>
                        <span class="ms-1" id="projectLoadedDataladSummary"></span>
                    </div>
                    <a href="/settings#dataladSection" class="btn btn-sm btn-outline-secondary" id="projectLoadedManageDataladLink">
                        <i class="fas fa-gear me-1"></i>Manage DataLad
                    </a>
                </div>
                <div class="d-flex flex-column align-items-end mt-2">
                    <div class="d-flex gap-2 flex-wrap justify-content-end">
                        <button type="button" class="btn btn-outline-danger" id="projectBoxDeleteBtn"
                                data-project-path="${escapeHtml(loadedPath)}" data-project-name="${escapeHtml(loadedName || '')}">
                            <i class="fas fa-trash me-2"></i>Delete Project
                        </button>
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

    function updateLoadProjectButtonState() {
        const input = document.getElementById('existingPath');
        const button = document.getElementById('loadProjectBtn');
        if (!input || !button) return;

        const selectedPath = String(input.value || '').trim().replace(/[\\/]+$/, '');
        const currentPath = String(getCurrentProjectState().path || '').trim().replace(/[\\/]+$/, '');
        const isCurrentProject = Boolean(selectedPath && currentPath && isSameProjectPath(selectedPath, currentPath));
        button.disabled = isCurrentProject;
        button.title = isCurrentProject ? 'This project is already loaded' : '';
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

        setProjectValidationResult(`
            <div class="validation-result pending project-loaded-state" role="status" aria-live="polite">
                <h5 class="mb-2"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Loading project details...</h5>
                <p class="mb-0">Reading project metadata and folder summary.</p>
            </div>
        `);
        const originalText = triggerButton ? setButtonLoading(triggerButton, true, 'Loading...') : null;

        try {
            const response = await fetchWithApiFallback('/api/projects/current', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // metadata_only: answer from project.json + one directory read so the
                // card paints immediately; the counted summary follows below.
                body: JSON.stringify({
                    path: normalizedPath,
                    defer_datalad_status: true,
                    metadata_only: true
                })
            });
            const result = await response.json().catch(() => ({
                success: false,
                error: 'Server returned an invalid response while loading the project.'
            }));

            if (!response.ok || !result.success || !result.current || !result.current.path) {
                showOpenProjectError(result.error || `Project load failed (${response.status})`);
                return false;
            }

            const projectSummary = result.project_summary && typeof result.project_summary === 'object' && !Array.isArray(result.project_summary)
                ? result.project_summary
                : null;

            applyCurrentProject({
                ...result.current,
                hasData: Boolean(projectSummary && Number(projectSummary.subjects) > 0)
            });

            const currentState = getCurrentProjectState();
            const loadedPath = String(result.current.path || '').trim();
            const loadedName = String(result.current.name || currentState.name || '').trim();
            addRecentProject(loadedName, loadedPath, currentState.icon);
            showStudyMetadataCard();
            updateCreateProjectButton();
            showMethodsCard();

            lastShallowProjectSummary = projectSummary;
            renderLoadedProjectState(loadedName, loadedPath, projectSummary);
            renderProjectBoxDataladState(currentState.datalad, loadedPath);
            bindProjectBoxActionButtons();
            updateCreateProjectButton();
            updateLoadProjectButtonState();
            showAutosaveFailureFeedback(result.autosave_previous);

            // Let the card paint before the folder walk and DataLad status work.
            window.setTimeout(() => {
                refreshProjectQuickSummary();
            }, 0);

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

    document.getElementById('existingPath')?.addEventListener('input', updateLoadProjectButtonState);
    updateLoadProjectButtonState();

    return {
        getOpenProjectActionPath,
        loadProjectWithoutValidation,
    };
}