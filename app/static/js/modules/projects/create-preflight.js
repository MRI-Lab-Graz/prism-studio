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

    function getCreateDataladToggleState() {
        return document.getElementById('projectUseDatalad')?.checked !== false;
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

    return {
        resetCreateTargetStatusChecks,
        checkCreateTargetStatus,
        scheduleCreateTargetStatusCheck,
        submitOpenProjectPath,
    };
}