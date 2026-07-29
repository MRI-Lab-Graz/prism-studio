import { appendConverterLogBatch, appendConverterLogLine } from '../converter/log-renderer.js';

export function initProjectInitOnBidsController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    showMethodsCard,
}) {
    const initBidsSubmitBtn = document.getElementById('initBidsSubmitBtn');
    if (!initBidsSubmitBtn) {
        return;
    }

    let remoteStatusRequestToken = 0;
    let remoteStatusDebounceTimer = null;
    let remoteStatusState = null;

    const initBidsProgressContainer = document.getElementById('initBidsProgressContainer');
    const initBidsProgressBar = document.getElementById('initBidsProgressBar');
    const initBidsProgressLabel = document.getElementById('initBidsProgressLabel');
    const initBidsProgressPercent = document.getElementById('initBidsProgressPercent');
    const initBidsLogContainer = document.getElementById('initBidsLogContainer');
    const initBidsLogBody = document.getElementById('initBidsLogBody');
    const initBidsLog = document.getElementById('initBidsLog');
    const initBidsToggleLogBtn = document.getElementById('initBidsToggleLogBtn');

    let progressTimer = null;
    let progressPercent = 0;
    let progressLabel = '';

    if (initBidsToggleLogBtn && initBidsLogBody) {
        initBidsToggleLogBtn.addEventListener('click', function() {
            initBidsLogBody.classList.toggle('d-none');
            const icon = initBidsToggleLogBtn.querySelector('i');
            if (initBidsLogBody.classList.contains('d-none')) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            } else {
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-down');
            }
        });
    }

    function stopProgressTimer() {
        if (progressTimer !== null) {
            window.clearInterval(progressTimer);
            progressTimer = null;
        }
    }

    function renderProgress(variant, animated) {
        if (!initBidsProgressContainer || !initBidsProgressBar) {
            return;
        }
        initBidsProgressContainer.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-danger');
        initBidsProgressContainer.classList.add(`alert-${variant}`);
        initBidsProgressBar.classList.remove('bg-info', 'bg-success', 'bg-danger', 'progress-bar-striped', 'progress-bar-animated');
        initBidsProgressBar.classList.add(`bg-${variant}`);
        if (animated) {
            initBidsProgressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
        }
        const rounded = Math.max(0, Math.min(100, Math.round(progressPercent)));
        initBidsProgressBar.style.width = `${rounded}%`;
        initBidsProgressBar.setAttribute('aria-valuenow', String(rounded));
        if (initBidsProgressPercent) {
            initBidsProgressPercent.textContent = `${rounded}%`;
        }
        if (initBidsProgressLabel) {
            initBidsProgressLabel.textContent = progressLabel;
        }
    }

    function setProgress(percent, label, variant = 'info', animated = true) {
        progressPercent = Math.max(progressPercent, Math.min(100, percent));
        if (label) {
            progressLabel = label;
        }
        renderProgress(variant, animated);
    }

    function startProgress(label) {
        stopProgressTimer();
        progressPercent = 8;
        progressLabel = label;
        renderProgress('info', true);
        progressTimer = window.setInterval(() => {
            const increment = progressPercent < 30 ? 6 : (progressPercent < 60 ? 3 : 1);
            progressPercent = Math.min(90, progressPercent + increment);
            renderProgress('info', true);
        }, 700);
    }

    function hideProgress() {
        stopProgressTimer();
        progressPercent = 0;
        progressLabel = '';
        if (initBidsProgressContainer) {
            initBidsProgressContainer.classList.add('d-none');
        }
    }

    function appendLog(message, level = 'info') {
        appendConverterLogLine(message, level, initBidsLog);
    }

    function resetLog() {
        if (initBidsLog) {
            initBidsLog.innerHTML = '';
        }
        if (initBidsLogContainer) {
            initBidsLogContainer.classList.remove('d-none');
        }
        if (initBidsLogBody) {
            initBidsLogBody.classList.remove('d-none');
        }
    }

    function syncDataladToggleVisibility() {
        const remoteUrl = (document.getElementById('initBidsRemoteUrl')?.value || '').trim();
        const hasRemote = remoteUrl.length > 0;
        const dataladToggle = document.getElementById('initBidsUseDatalad');
        const dataladToggleContainer = dataladToggle?.closest('.form-check');

        if (dataladToggle && dataladToggleContainer) {
            if (hasRemote) {
                dataladToggle.checked = false;
                dataladToggle.disabled = true;
                dataladToggleContainer.classList.add('d-none');
            } else {
                dataladToggle.disabled = false;
                dataladToggleContainer.classList.remove('d-none');
            }
        }

        ['Derivatives', 'Sourcedata', 'Rawdata'].forEach(function(suffix) {
            const toggle = document.getElementById(`initBidsFetch${suffix}`);
            const container = document.getElementById(`initBidsFetch${suffix}Container`);
            if (!toggle || !container) {
                return;
            }
            if (hasRemote) {
                toggle.disabled = false;
                container.classList.remove('d-none');
            } else {
                toggle.checked = false;
                toggle.disabled = true;
                container.classList.add('d-none');
            }
        });
    }

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
        syncDataladToggleVisibility();
        scheduleRemoteStatusRefresh();
    });

    syncDataladToggleVisibility();
    renderRemoteStatus(null);

    initBidsSubmitBtn.addEventListener('click', async function() {
        const bidsPath = (document.getElementById('initBidsPath')?.value || '').trim();
        const clonePath = (document.getElementById('initBidsClonePath')?.value || '').trim();
        const remoteUrl = (document.getElementById('initBidsRemoteUrl')?.value || '').trim();
        const displayName = (document.getElementById('initBidsName')?.value || '').trim();
        const useDatalad = document.getElementById('initBidsUseDatalad')?.checked !== false;
        const autoEnvironmentEnrichment = document.getElementById('initBidsAutoEnvironmentEnrichment')?.checked !== false;
        const fetchRemoteDerivatives = document.getElementById('initBidsFetchDerivatives')?.checked === true;
        const fetchRemoteSourcedata = document.getElementById('initBidsFetchSourcedata')?.checked === true;
        const fetchRemoteRawdata = document.getElementById('initBidsFetchRawdata')?.checked === true;
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
            alert('Please provide either a BIDS dataset root or a Git/DataLad URL with clone destination.');
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
        resultDiv.style.display = 'none';
        resultDiv.innerHTML = '';

        resetLog();
        appendLog(`Starting initialization for: ${targetPath}`, 'info');
        appendLog(hasRemote ? `Source: remote (${remoteUrl})` : 'Source: local BIDS root', 'step');
        appendLog(hasRemote ? 'DataLad: managed automatically for remote sources' : `DataLad version control: ${useDatalad ? 'enabled' : 'disabled'}`, 'step');
        if (hasRemote) {
            appendLog('Subject (sub-*/) folders at the dataset root: always downloaded in full', 'step');
            [
                ['derivatives/', fetchRemoteDerivatives],
                ['sourcedata/', fetchRemoteSourcedata],
                ['rawdata/ wrapper folder (if present)', fetchRemoteRawdata]
            ].forEach(function([label, opted]) {
                appendLog(
                    opted
                        ? `${label} content: will be downloaded (opted in)`
                        : `${label} content: skipped by default (structure only) - enable the toggle to download it`,
                    'step'
                );
            });
        }
        startProgress(hasRemote ? 'Cloning remote dataset...' : 'Validating BIDS dataset...');

        const originalText = setButtonLoading(initBidsSubmitBtn, true, 'Initialising…');
        initBidsSubmitBtn.disabled = true;

        // The init-on-bids request can block for a long time on real remote
        // datasets (multi-GB content fetches). It streams progress into a
        // server-side job log as it goes; poll that concurrently so the log
        // panel updates live instead of going silent until the request
        // finally resolves.
        const jobId = (window.crypto && typeof window.crypto.randomUUID === 'function')
            ? window.crypto.randomUUID()
            : `init-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        let jobLogCursor = 0;
        let keepPollingJobLog = true;

        async function drainInitBidsJobLog() {
            try {
                const pollResponse = await fetchWithApiFallback(
                    `/api/projects/init-on-bids-log/${encodeURIComponent(jobId)}?cursor=${jobLogCursor}`
                );
                if (!pollResponse.ok) {
                    return;
                }
                const payload = await pollResponse.json().catch(() => null);
                if (!payload) {
                    return;
                }
                if (Array.isArray(payload.logs) && payload.logs.length > 0) {
                    appendConverterLogBatch(payload.logs, 'info', initBidsLog);
                }
                if (Number.isInteger(payload.next_cursor)) {
                    jobLogCursor = payload.next_cursor;
                }
            } catch (_pollError) {
                // Transient poll failures are non-fatal - the final result
                // still arrives via the main request below.
            }
        }

        (async function pollInitBidsJobLog() {
            while (keepPollingJobLog) {
                await drainInitBidsJobLog();
                await new Promise((resolve) => window.setTimeout(resolve, 1000));
            }
        })();

        try {
            const response = await fetchWithApiFallback('/api/projects/init-on-bids', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: targetPath || undefined,
                    bids_path: bidsPath || undefined,
                    clone_path: clonePath || undefined,
                    name: displayName || undefined,
                    use_datalad: useDatalad,
                    remote_url: hasRemote ? remoteUrl : undefined,
                    source_type: hasRemote ? 'remote' : 'local',
                    auto_environment_enrichment: autoEnvironmentEnrichment,
                    fetch_remote_derivatives: fetchRemoteDerivatives,
                    fetch_remote_sourcedata: fetchRemoteSourcedata,
                    fetch_remote_rawdata: fetchRemoteRawdata,
                    job_id: jobId
                })
            });
            setProgress(70, 'Server response received. Applying changes...', 'info', true);
            const result = await response.json();

            keepPollingJobLog = false;
            await drainInitBidsJobLog(); // flush any lines emitted since the last poll tick

            resultDiv.style.display = 'block';

            if (result.success) {
                stopProgressTimer();
                setProgress(100, 'Initialization complete.', 'success', false);
                window.setTimeout(hideProgress, 1800);
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
                const environmentEnrichmentNotice = result.environment_enrichment_job_id
                    ? `
                        <div class="alert alert-info mt-3 mb-0">
                            <i class="fas fa-globe me-2"></i>Scanning MRI acquisitions for environmental enrichment in the background. Check the Environment converter tab for progress.
                        </div>
                    `
                    : '';
                const phenotypeImport = result.phenotype_import || null;
                const phenotypeNotice = (phenotypeImport && phenotypeImport.imported_task_count)
                    ? `
                        <div class="alert alert-warning mt-3 mb-0">
                            <i class="fas fa-triangle-exclamation me-2"></i>
                            Detected a BIDS <code>phenotype/</code> directory and imported
                            ${phenotypeImport.imported_task_count} task(s) into PRISM's native
                            <code>survey/</code> layout as a one-way compatibility bridge.
                            ${(phenotypeImport.flagged_columns && phenotypeImport.flagged_columns.length)
                                ? `Column(s) that may belong in <code>participants.tsv</code> instead: ${escapeHtml(phenotypeImport.flagged_columns.join(', '))}.`
                                : ''}
                            Review the generated sidecars &mdash; instrument metadata (scale
                            definitions, reverse-coding) could not be recovered from
                            <code>phenotype/</code> and was left minimal.
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
                        ${environmentEnrichmentNotice}
                        ${phenotypeNotice}
                    </div>
                `;
                applyCurrentProject(result.current_project);
                addRecentProject(
                    result.current_project?.name || displayName || targetPath.split(/[\\/]/).pop(),
                    result.path,
                    result.current_project?.icon
                );
                showStudyMetadataCard();
                showMethodsCard();
            } else {
                stopProgressTimer();
                setProgress(100, 'Initialization failed.', 'danger', false);
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${escapeHtml(result.error)}</p>
                    </div>
                `;
            }
        } catch (error) {
            stopProgressTimer();
            setProgress(100, 'Initialization failed.', 'danger', false);
            appendLog(error.message, 'error');
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${escapeHtml(error.message)}</p>
                </div>
            `;
        } finally {
            keepPollingJobLog = false;
            setButtonLoading(initBidsSubmitBtn, false, null, originalText);
            initBidsSubmitBtn.disabled = false;
        }
    });
}
