export function initProjectInitOnBidsController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    showExportCard,
    showMethodsCard,
}) {
    const initBidsSubmitBtn = document.getElementById('initBidsSubmitBtn');
    if (!initBidsSubmitBtn) {
        return;
    }

    let remoteStatusRequestToken = 0;
    let remoteStatusDebounceTimer = null;
    let remoteStatusState = null;

    function renderRemoteStatus(status, options = {}) {
        const container = document.getElementById('initBidsRemoteStatus');
        if (!container) {
            return;
        }

        const loadFailed = options.loadFailed === true;
        const remoteSource = status?.remote_source || null;
        let alertClass = 'alert-secondary';
        let iconClass = 'fa-circle-info text-muted';
        let title = 'Remote Source Check';
        let message = 'OpenNeuro-style URLs are checked for DataLad requirements before PRISM starts the clone.';
        let detail = '';
        let shouldDisableSubmit = false;

        if (remoteSource?.active) {
            if (remoteSource.valid === false) {
                alertClass = 'alert-warning';
                iconClass = 'fa-triangle-exclamation text-warning';
                title = 'Remote URL Invalid';
                message = remoteSource.message || 'Provide a full Git or DataLad URL.';
                shouldDisableSubmit = true;
            } else if (remoteSource.requires_datalad) {
                const canEnable = remoteSource.datalad_preflight?.can_enable === true;
                alertClass = canEnable ? 'alert-info' : 'alert-danger';
                iconClass = canEnable ? 'fa-circle-check text-info' : 'fa-ban text-danger';
                title = canEnable ? 'OpenNeuro Remote Ready' : 'DataLad Required';
                message = remoteSource.message || 'This remote dataset will be installed with DataLad.';
                detail = canEnable
                    ? 'DataLad and git-annex are available on this machine.'
                    : (remoteSource.datalad_preflight?.message || 'DataLad and git-annex are required on this machine.');
                shouldDisableSubmit = !canEnable;
            } else {
                alertClass = 'alert-secondary';
                iconClass = 'fa-code-branch text-muted';
                title = 'Git Clone Remote';
                message = remoteSource.message || 'This remote dataset can be cloned with Git.';
                detail = 'PRISM will clone the repository into the destination folder you choose.';
            }
        } else if (loadFailed) {
            alertClass = 'alert-warning';
            iconClass = 'fa-triangle-exclamation text-warning';
            message = 'Could not check remote source requirements right now.';
        }

        container.className = `alert ${alertClass} py-2 px-3 mt-3 mb-0 small`;
        container.innerHTML = `
            <div class="d-flex align-items-start gap-2">
                <i class="fas ${iconClass} mt-1" aria-hidden="true"></i>
                <div>
                    <div class="fw-semibold">${escapeHtml(title)}</div>
                    <div>${escapeHtml(message)}</div>
                    ${detail ? `<div class="mt-1">${escapeHtml(detail)}</div>` : ''}
                </div>
            </div>
        `;

        initBidsSubmitBtn.disabled = shouldDisableSubmit;
    }

    async function refreshRemoteStatus() {
        const remoteUrl = (document.getElementById('initBidsRemoteUrl')?.value || '').trim();
        const requestToken = ++remoteStatusRequestToken;

        if (!remoteUrl) {
            remoteStatusState = null;
            renderRemoteStatus(null);
            return null;
        }

        try {
            const response = await fetchWithApiFallback('/api/projects/remote-source-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ remote_url: remoteUrl })
            });
            const status = await response.json().catch(() => null);
            if (requestToken !== remoteStatusRequestToken) {
                return null;
            }
            remoteStatusState = status;
            renderRemoteStatus(status);
            return status;
        } catch (_error) {
            if (requestToken !== remoteStatusRequestToken) {
                return null;
            }
            remoteStatusState = null;
            renderRemoteStatus(null, { loadFailed: true });
            return null;
        }
    }

    function scheduleRemoteStatusRefresh() {
        if (remoteStatusDebounceTimer) {
            window.clearTimeout(remoteStatusDebounceTimer);
        }
        remoteStatusDebounceTimer = window.setTimeout(() => {
            refreshRemoteStatus().catch(() => {});
        }, 200);
    }

    document.getElementById('initBidsRemoteUrl')?.addEventListener('input', function() {
        scheduleRemoteStatusRefresh();
    });

    renderRemoteStatus(null);

    initBidsSubmitBtn.addEventListener('click', async function() {
        const bidsPath = (document.getElementById('initBidsPath')?.value || '').trim();
        const clonePath = (document.getElementById('initBidsClonePath')?.value || '').trim();
        const remoteUrl = (document.getElementById('initBidsRemoteUrl')?.value || '').trim();
        const displayName = (document.getElementById('initBidsName')?.value || '').trim();
        const useDatalad = document.getElementById('initBidsUseDatalad')?.checked !== false;
        const hasRemote = remoteUrl.length > 0;
        const targetPath = hasRemote ? clonePath : bidsPath;

        if (hasRemote && !clonePath) {
            alert('Please select or enter the local clone destination folder.');
            document.getElementById('initBidsClonePath')?.focus();
            return;
        }

        if (hasRemote) {
            const remoteStatus = remoteStatusState || await refreshRemoteStatus();
            if (remoteStatus?.remote_source?.disabled) {
                alert(remoteStatus.remote_source.message || 'This remote dataset cannot be initialised on this machine right now.');
                document.getElementById('initBidsRemoteUrl')?.focus();
                return;
            }
            if (remoteStatus?.remote_source?.valid === false) {
                alert(remoteStatus.remote_source.message || 'Please enter a valid Git/DataLad URL.');
                document.getElementById('initBidsRemoteUrl')?.focus();
                return;
            }
        }

        if (!hasRemote && !bidsPath) {
            alert('Please select or enter the BIDS dataset root folder.');
            document.getElementById('initBidsPath')?.focus();
            return;
        }

        if (!confirmProjectContextChange(
            hasRemote
                ? 'clone and initialise a PRISM project from a remote BIDS dataset'
                : 'initialise a PRISM project on another dataset',
            targetPath
        )) {
            return;
        }

        const resultDiv = document.getElementById('initBidsResult');
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = '<div class="alert alert-secondary"><i class="fas fa-spinner fa-spin me-2"></i>Initialising…</div>';

        const originalText = setButtonLoading(initBidsSubmitBtn, true, 'Initialising…');
        initBidsSubmitBtn.disabled = true;

        try {
            const response = await fetchWithApiFallback('/api/projects/init-on-bids', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: targetPath,
                    name: displayName || undefined,
                    use_datalad: useDatalad,
                    remote_url: hasRemote ? remoteUrl : undefined,
                    source_type: hasRemote ? 'remote' : 'local'
                })
            });
            const result = await response.json();

            if (result.success) {
                const fileList = (result.created_files || [])
                    .map(filePath => `<li><code>${escapeHtml(filePath)}</code></li>`)
                    .join('');
                const noneAdded = !result.created_files || result.created_files.length === 0;
                const dataladNotice = result.datalad?.message
                    ? `
                        <div class="alert alert-${result.datalad.saved ? 'info' : (result.datalad.requested ? 'warning' : 'secondary')} mt-3 mb-0">
                            <i class="fas fa-code-branch me-2"></i>${escapeHtml(result.datalad.message)}
                        </div>
                    `
                    : '';
                const sourceNotice = result.source?.message
                    ? `
                        <div class="alert alert-${result.source.clone_method === 'datalad_install' ? 'info' : 'secondary'} mt-3 mb-0">
                            <i class="fas fa-cloud-download-alt me-2"></i>${escapeHtml(result.source.message)}
                        </div>
                    `
                    : '';
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>PRISM Initialised Successfully!</h5>
                        <p class="mb-2">${escapeHtml(result.message)}</p>
                        <p class="mb-2"><strong>Location:</strong> <code>${escapeHtml(result.path)}</code></p>
                        <p class="mb-0 text-success"><i class="fas fa-folder-open me-1"></i>This dataset is now your current working project.</p>
                        ${noneAdded ? '' : `<hr><p class="mb-1"><strong>Added files:</strong></p><ul class="mb-0">${fileList}</ul>`}
                        <div class="mt-3 pt-3 border-top">
                            <h6 class="text-muted mb-2">Next Steps:</h6>
                            <div class="btn-group" role="group">
                                <a href="/validate" class="btn btn-sm btn-outline-primary">
                                    <i class="fas fa-check-double me-1"></i>Validate Dataset
                                </a>
                                <a href="/converter" class="btn btn-sm btn-outline-success">
                                    <i class="fas fa-magic me-1"></i>Open Converter
                                </a>
                            </div>
                        </div>
                        ${sourceNotice}
                        ${dataladNotice}
                    </div>
                `;
                applyCurrentProject(result.current_project);
                addRecentProject(
                    result.current_project?.name || displayName || targetPath.split(/[\\/]/).pop(),
                    result.path,
                    result.current_project?.icon
                );
                showStudyMetadataCard();
                showExportCard();
                showMethodsCard();
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${escapeHtml(result.error)}</p>
                    </div>
                `;
            }
        } catch (error) {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${escapeHtml(error.message)}</p>
                </div>
            `;
        } finally {
            setButtonLoading(initBidsSubmitBtn, false, null, originalText);
            initBidsSubmitBtn.disabled = false;
        }
    });
}
