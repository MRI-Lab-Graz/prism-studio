export function initCreatePreflightController({
    fetchWithApiFallback,
    escapeHtml,
    clearCreateResult,
    setCreateResultHtml,
    joinProjectTargetPath,
    getSelectProjectType,
}) {
    let createTargetStatusRequestToken = 0;
    let createTargetStatusDebounceTimer = null;
    let createDataladPreflightStatus = null;

    function getCreateDataladToggleState() {
        return document.getElementById('projectUseDatalad')?.checked !== false;
    }

    function renderCreateDataladAvailability(status, options = {}) {
        const container = document.getElementById('createDataladAvailability');
        if (!container) {
            return;
        }

        const loadFailed = options.loadFailed === true;
        const dataladPreflight = status?.datalad_preflight || null;
        const dataladRequested = getCreateDataladToggleState();

        let alertClass = 'alert-secondary';
        let iconClass = 'fa-circle-info text-muted';
        let title = 'DataLad Status Unknown';
        let message = 'Could not check DataLad availability on this machine right now.';
        let detail = 'PRISM can still create the project without DataLad.';

        if (dataladPreflight) {
            const available = dataladPreflight.available === true;
            const annexAvailable = dataladPreflight.annex_available === true;
            const canEnable = dataladPreflight.can_enable === true;
            const baseMessage = String(dataladPreflight.message || '').trim();

            if (canEnable) {
                alertClass = dataladRequested ? 'alert-success' : 'alert-secondary';
                iconClass = dataladRequested ? 'fa-circle-check text-success' : 'fa-circle-info text-muted';
                title = 'DataLad Ready';
                message = baseMessage || 'DataLad and git-annex are available for project setup.';
                detail = dataladRequested
                    ? 'This project will be initialized with DataLad when you create it.'
                    : 'Turn the switch on if you want PRISM to initialize DataLad for this project.';
            } else if (available && !annexAvailable) {
                alertClass = dataladRequested ? 'alert-warning' : 'alert-secondary';
                iconClass = dataladRequested ? 'fa-triangle-exclamation text-warning' : 'fa-circle-info text-muted';
                title = 'git-annex Missing';
                message = baseMessage || 'git-annex is not installed, so DataLad project setup is unavailable.';
                detail = 'PRISM will still create the project, but without DataLad version control.';
            } else {
                alertClass = dataladRequested ? 'alert-warning' : 'alert-secondary';
                iconClass = dataladRequested ? 'fa-triangle-exclamation text-warning' : 'fa-circle-info text-muted';
                title = 'DataLad Missing';
                message = baseMessage || 'DataLad is not installed, so DataLad project setup is unavailable.';
                detail = 'PRISM will still create the project, but without DataLad version control.';
            }
        } else if (loadFailed) {
            alertClass = dataladRequested ? 'alert-warning' : 'alert-secondary';
            iconClass = dataladRequested ? 'fa-triangle-exclamation text-warning' : 'fa-circle-info text-muted';
        }

        container.className = `alert ${alertClass} py-2 px-3 mt-2 mb-0 small`;
        container.innerHTML = `
            <div class="d-flex align-items-start gap-2">
                <i class="fas ${iconClass} mt-1" aria-hidden="true"></i>
                <div>
                    <div class="fw-semibold">${escapeHtml(title)}</div>
                    <div>${escapeHtml(message)}</div>
                    <div class="mt-1">${escapeHtml(detail)}</div>
                </div>
            </div>
        `;
    }

    async function refreshCreateDataladAvailability() {
        try {
            const response = await fetchWithApiFallback('/api/projects/datalad/preflight');
            const status = await response.json().catch(() => null);
            createDataladPreflightStatus = status;
            renderCreateDataladAvailability(status);
            return status;
        } catch (_error) {
            createDataladPreflightStatus = null;
            renderCreateDataladAvailability(null, { loadFailed: true });
            return null;
        }
    }

    function buildDataladPreflightHtml(status, targetPath) {
        const dataladPreflight = status?.datalad_preflight;
        if (!getCreateDataladToggleState() || !dataladPreflight || dataladPreflight.can_enable) {
            return '';
        }

        const title = dataladPreflight.available ? 'git-annex Missing' : 'DataLad Missing';
        const targetHtml = targetPath
            ? `<p class="mb-2"><strong>Target:</strong> <code>${escapeHtml(targetPath)}</code></p>`
            : '';

        return `
            <div class="alert alert-warning mb-0">
                <h5><i class="fas fa-code-branch me-2"></i>${title}</h5>
                ${targetHtml}
                <p class="mb-0">${escapeHtml(dataladPreflight.message || 'DataLad tools are not available for project setup.')}</p>
            </div>
        `;
    }

    function resetCreateTargetStatusChecks() {
        if (createTargetStatusDebounceTimer) {
            window.clearTimeout(createTargetStatusDebounceTimer);
            createTargetStatusDebounceTimer = null;
        }
        createTargetStatusRequestToken += 1;
    }

    async function checkCreateTargetStatus() {
        const projectName = document.getElementById('projectName')?.value.trim() || '';
        const projectPath = document.getElementById('projectPath')?.value.trim() || '';
        const validProjectName = /^[a-zA-Z0-9_-]+$/.test(projectName);

        if (!projectName || !projectPath || !validProjectName) {
            clearCreateResult('preflight');
            return { conflict: false };
        }

        const targetPath = joinProjectTargetPath(projectPath, projectName);
        const requestToken = ++createTargetStatusRequestToken;

        try {
            const response = await fetchWithApiFallback('/api/projects/path-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: targetPath })
            });
            const status = await response.json().catch(() => null);

            if (requestToken !== createTargetStatusRequestToken) {
                return { conflict: false, stale: true };
            }

            createDataladPreflightStatus = status;
            renderCreateDataladAvailability(status);

            const dataladWarningHtml = buildDataladPreflightHtml(status, targetPath);

            if (!status || status.success !== true || status.exists !== true) {
                if (dataladWarningHtml) {
                    setCreateResultHtml(dataladWarningHtml, 'preflight');
                } else {
                    clearCreateResult('preflight');
                }
                return { conflict: false, targetPath };
            }

            if (status.is_dir && status.is_empty_dir) {
                if (dataladWarningHtml) {
                    setCreateResultHtml(dataladWarningHtml, 'preflight');
                } else {
                    clearCreateResult('preflight');
                }
                return { conflict: false, targetPath, status };
            }

            let title = 'Target Folder Already Exists';
            let message = `The target folder <code>${escapeHtml(targetPath)}</code> already exists and contains files. Project Location must be the parent folder where PRISM creates a new project folder.`;

            if (status.is_file) {
                title = 'Target Path Is A File';
                message = `The target path <code>${escapeHtml(targetPath)}</code> already exists as a file. Project Location must be the parent folder, not the final project path.`;
            } else if (status.available) {
                title = 'Project Already Exists';
                message = `The target folder <code>${escapeHtml(targetPath)}</code> already contains a <code>project.json</code>. Use Open Existing Project instead of Create New Project.`;
            }

            const actionHtml = status.available
                ? `
                    <div class="mt-3">
                        <button
                            type="button"
                            class="btn btn-sm btn-outline-primary"
                            data-action="open-existing-project"
                            data-path="${escapeHtml(status.project_json_path || targetPath)}"
                        >
                            <i class="fas fa-folder-open me-1"></i>Open Existing Project
                        </button>
                    </div>
                `
                : '';

            setCreateResultHtml(
                `
                    <div class="alert alert-warning">
                        <h5><i class="fas fa-exclamation-triangle me-2"></i>${title}</h5>
                        <p class="mb-0">${message}</p>
                        ${actionHtml}
                    </div>
                    ${dataladWarningHtml}
                `,
                'preflight'
            );

            return { conflict: true, targetPath, status };
        } catch (_error) {
            if (requestToken === createTargetStatusRequestToken) {
                clearCreateResult('preflight');
            }
            return { conflict: false, targetPath };
        }
    }

    function scheduleCreateTargetStatusCheck() {
        resetCreateTargetStatusChecks();
        createTargetStatusDebounceTimer = window.setTimeout(() => {
            checkCreateTargetStatus().catch(() => {});
        }, 200);
    }

    function submitOpenProjectPath(path) {
        const normalizedPath = String(path || '').trim();
        const existingPathInput = document.getElementById('existingPath');
        const openProjectForm = document.getElementById('openProjectForm');
        if (!normalizedPath || !existingPathInput || !openProjectForm) {
            return;
        }

        existingPathInput.value = normalizedPath;
        const selectProjectType = typeof getSelectProjectType === 'function'
            ? getSelectProjectType()
            : null;
        if (typeof selectProjectType === 'function') {
            selectProjectType('open');
        }

        if (typeof openProjectForm.requestSubmit === 'function') {
            openProjectForm.requestSubmit();
            return;
        }

        openProjectForm.dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );
    }

    const projectNameInput = document.getElementById('projectName');
    if (projectNameInput) {
        projectNameInput.addEventListener('input', function(event) {
            const value = event.target.value;
            const isValid = /^[a-zA-Z0-9_-]*$/.test(value);
            const errorDiv = document.getElementById('projectNameError');

            if (!isValid) {
                event.target.classList.add('is-invalid');
                errorDiv.textContent = 'Only letters, numbers, underscores (_) and hyphens (-) allowed. No spaces!';
            } else {
                event.target.classList.remove('is-invalid');
                errorDiv.textContent = '';
            }

            clearCreateResult();
            scheduleCreateTargetStatusCheck();
        });
    }

    const projectPathInput = document.getElementById('projectPath');
    if (projectPathInput) {
        projectPathInput.addEventListener('input', function() {
            this.classList.remove('is-invalid');
            clearCreateResult();
            scheduleCreateTargetStatusCheck();
        });
        projectPathInput.addEventListener('change', function() {
            this.classList.remove('is-invalid');
            clearCreateResult();
            scheduleCreateTargetStatusCheck();
        });
    }

    const projectUseDataladInput = document.getElementById('projectUseDatalad');
    if (projectUseDataladInput) {
        projectUseDataladInput.addEventListener('change', function() {
            renderCreateDataladAvailability(createDataladPreflightStatus);
            scheduleCreateTargetStatusCheck();
        });
    }

    const createResultDiv = document.getElementById('createResult');
    if (createResultDiv) {
        createResultDiv.addEventListener('click', (event) => {
            const openExistingBtn = event.target.closest('[data-action="open-existing-project"]');
            if (!openExistingBtn) return;
            const path = openExistingBtn.getAttribute('data-path');
            if (!path) return;
            submitOpenProjectPath(path);
        });
    }

    refreshCreateDataladAvailability().catch(() => {});

    return {
        resetCreateTargetStatusChecks,
        checkCreateTargetStatus,
        refreshCreateDataladAvailability,
        scheduleCreateTargetStatusCheck,
        submitOpenProjectPath,
    };
}