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
            bindProjectBoxActionButtons();
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