/**
 * Projects Module - Push to DataLad Server
 *
 * Two distinct, repeatable-vs-terminal actions against a central DataLad
 * sibling -- a RIA store (`ria+...` URL) or a plain SSH/local sibling (any
 * other URL), see `run_datalad_create_sibling` in datalad_execution.py:
 * - "Sync now": connect (idempotent) + push. Safe to click any number of
 *   times while a study is ongoing; the sibling stays registered.
 * - "Finalize & disconnect": one last push, verification, then removes the
 *   local sibling registration. Local files are always kept.
 */

import { setButtonLoading } from './helpers.js';
import { getById, setHtml, hide, show, escapeHtml } from '../../shared/dom.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { openRemoteFolderPicker } from './remote_folder_picker.js';
import { isRiaUrl } from '../../shared/ssh-target.js';

let dataladServerModuleInitialized = false;
let activeJobId = null;
let activeJobCancelled = false;

function getProgressEls() {
    return {
        progressDiv: getById('dataladServerProgress'),
        progressBar: getById('dataladServerProgressBar'),
        progressText: getById('dataladServerProgressText'),
        statusText: getById('dataladServerStatusText'),
        resultDiv: getById('dataladServerResult'),
        cancelBtn: getById('dataladServerCancelBtn'),
    };
}

function setStatusBadge(text, tone = 'secondary') {
    const badge = getById('dataladServerStatusBadge');
    if (!badge) return;
    badge.className = `badge bg-${tone}`;
    badge.textContent = text;
}

/**
 * Show/hide the "Push to DataLad Server" card and refresh its connection status.
 */
export function showDataladServerCard() {
    const card = getById('dataladServerCard');
    if (!card) return;

    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        hide(card);
        return;
    }

    show(card);
    refreshDataladServerStatus(projectPath);
}

async function refreshDataladServerStatus(projectPath) {
    const detail = getById('dataladServerStatusDetail');
    setStatusBadge('Checking...', 'secondary');
    if (detail) detail.textContent = 'Checking connection status...';

    try {
        const resp = await fetchWithApiFallback(
            `/api/projects/datalad-server/status?project_path=${encodeURIComponent(projectPath)}`
        );
        if (!resp.ok) throw new Error('Could not load status');
        const status = await resp.json();

        const urlInput = getById('dataladServerUrl');
        const nameInput = getById('dataladServerSiblingName');
        const aliasInput = getById('dataladServerAlias');
        if (urlInput && !urlInput.value) urlInput.value = status.ria_url || '';
        if (nameInput && !nameInput.value) nameInput.value = status.sibling_name || 'ria-store';
        if (aliasInput && !aliasInput.value) aliasInput.value = status.sibling_alias || '';

        if (!status.datalad_dataset) {
            setStatusBadge('Not a DataLad dataset', 'secondary');
            if (detail) detail.textContent = 'This project is not tracked with DataLad, so it cannot be pushed to a server.';
        } else if (status.connected) {
            setStatusBadge('Connected', 'info');
            if (detail) detail.textContent = `Sibling "${status.sibling_name}" is registered. Sync now to back up, or finalize when done.`;
        } else {
            setStatusBadge('Not connected', 'secondary');
            if (detail) detail.textContent = 'No sibling registered yet. Click "Sync now" to connect and push.';
        }
    } catch (error) {
        setStatusBadge('Unknown', 'secondary');
        if (detail) detail.textContent = error.message || 'Could not load connection status.';
    }
}

function getRiaRequestData(projectPath) {
    return {
        project_path: projectPath,
        ria_url: (getById('dataladServerUrl')?.value || '').trim() || null,
        sibling_name: (getById('dataladServerSiblingName')?.value || '').trim() || null,
        alias: (getById('dataladServerAlias')?.value || '').trim() || null,
    };
}

async function requestCancelForActiveJob(endpoint) {
    if (!activeJobId) return;
    try {
        await fetchWithApiFallback(`${endpoint}/${encodeURIComponent(activeJobId)}/cancel`, { method: 'DELETE' });
    } catch {
        // Ignore cancellation network failures; the UI already reflects the local cancel state.
    }
}

async function runRiaJob({ startEndpoint, statusEndpointBase, button, originalText, requestData, successHeading }) {
    const { progressDiv, progressBar, progressText, statusText, resultDiv, cancelBtn } = getProgressEls();

    activeJobCancelled = false;
    activeJobId = null;

    if (resultDiv) hide(resultDiv);
    if (progressDiv) show(progressDiv);
    if (progressBar) progressBar.style.width = '0%';
    if (progressText) progressText.textContent = '0%';
    if (statusText) statusText.textContent = 'Starting...';
    if (cancelBtn) cancelBtn.classList.remove('d-none');

    function onCancelClick() {
        activeJobCancelled = true;
        void requestCancelForActiveJob(statusEndpointBase);
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Cancelled.</div>`);
        }
        setButtonLoading(button, false, null, originalText);
    }
    if (cancelBtn) cancelBtn.onclick = onCancelClick;

    try {
        const startResp = await fetchWithApiFallback(startEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData),
        });
        if (!startResp.ok) {
            const err = await startResp.json();
            throw new Error(err.error || 'Failed to start');
        }
        const startData = await startResp.json();
        activeJobId = startData.job_id;
        if (activeJobCancelled) {
            await requestCancelForActiveJob(statusEndpointBase);
            return;
        }

        const MAX_POLLS = 2250; // ~30 minutes at 800ms/poll
        for (let i = 0; i < MAX_POLLS; i++) {
            if (activeJobCancelled) break;
            await new Promise((r) => setTimeout(r, 800));
            if (activeJobCancelled) break;

            const statusResp = await fetchWithApiFallback(
                `${statusEndpointBase}/${encodeURIComponent(activeJobId)}/status`
            );
            if (!statusResp.ok) break;
            const status = await statusResp.json();

            const pct = status.percent || 0;
            if (progressBar) progressBar.style.width = `${pct}%`;
            if (progressText) progressText.textContent = `${pct}%`;
            if (statusText) statusText.textContent = status.message || '';

            if (status.status === 'complete') {
                if (progressDiv) hide(progressDiv);
                if (resultDiv) {
                    show(resultDiv);
                    setHtml(resultDiv, `
                        <div class="alert alert-success">
                            <h5><i class="fas fa-check-circle me-2"></i>${escapeHtml(successHeading)}</h5>
                            <p class="mb-0">${escapeHtml((status.result && status.result.message) || status.message || '')}</p>
                        </div>
                    `);
                }
                refreshDataladServerStatus(requestData.project_path);
                return;
            }

            if (status.status === 'error') {
                throw new Error(status.error || 'Operation failed');
            }

            if (status.status === 'cancelled') {
                activeJobCancelled = true;
                break;
            }
        }

        if (!activeJobCancelled) {
            throw new Error('Operation timed out after 30 minutes.');
        }
    } catch (error) {
        if (activeJobCancelled) return;
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'Operation failed.')}</p>
                </div>
            `);
        }
    } finally {
        if (cancelBtn && cancelBtn.onclick === onCancelClick) {
            cancelBtn.onclick = null;
        }
        if (cancelBtn) cancelBtn.classList.add('d-none');
        if (!activeJobCancelled) {
            setButtonLoading(button, false, null, originalText);
        }
    }
}

async function onSyncClick() {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        alert('No project is currently loaded');
        return;
    }
    const btn = getById('dataladServerSyncBtn');
    const originalText = setButtonLoading(btn, true, 'Syncing...');
    const requestData = getRiaRequestData(projectPath);
    requestData.verify = !!getById('dataladServerSyncVerify')?.checked;
    await runRiaJob({
        startEndpoint: '/api/projects/datalad-server/sync/start',
        statusEndpointBase: '/api/projects/datalad-server/sync',
        button: btn,
        originalText,
        requestData,
        successHeading: 'Synced to server',
    });
}

async function onFinalizeClick() {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        alert('No project is currently loaded');
        return;
    }
    const confirmed = window.confirm(
        'This pushes one last time, verifies the archive is complete, then disconnects this ' +
        'computer from the server. Local files are kept. This cannot be undone from this computer. Continue?'
    );
    if (!confirmed) return;

    const btn = getById('dataladServerFinalizeBtn');
    const originalText = setButtonLoading(btn, true, 'Finalizing...');
    const requestData = getRiaRequestData(projectPath);
    requestData.verify_mode = getById('dataladServerFullVerify')?.checked ? 'full' : 'fast';
    await runRiaJob({
        startEndpoint: '/api/projects/datalad-server/finalize/start',
        statusEndpointBase: '/api/projects/datalad-server/finalize',
        button: btn,
        originalText,
        requestData,
        successHeading: 'Finalized and disconnected',
    });
}

async function onBrowseUrlClick() {
    const input = getById('dataladServerUrl');
    const raw = input?.value || '';
    if (isRiaUrl(raw)) {
        alert(
            'Browsing isn\'t available for RIA store URLs — a RIA store\'s path is created ' +
            'automatically, so it doesn\'t need to already exist. Browsing only applies to a ' +
            'plain SSH sibling (a destination not starting with "ria+").'
        );
        return;
    }
    const picked = await openRemoteFolderPicker(raw);
    if (picked && input) input.value = picked;
}

async function onSaveConfigSubmit(e) {
    e.preventDefault();
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        alert('No project is currently loaded');
        return;
    }
    const btn = getById('dataladServerSaveConfigBtn');
    const originalText = setButtonLoading(btn, true, 'Saving...');
    try {
        const resp = await fetchWithApiFallback('/api/projects/datalad-server/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getRiaRequestData(projectPath)),
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'Failed to save server settings');
        }
        await refreshDataladServerStatus(projectPath);
    } catch (error) {
        alert(error.message || 'Failed to save server settings');
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

async function onDeleteScansTsvClick() {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        alert('No project is currently loaded');
        return;
    }
    const confirmed = window.confirm(
        'This permanently deletes every *_scans.tsv file across the dataset (superdataset and ' +
        'nested subject/derivatives subdatasets), committing the removal in each. Continue?'
    );
    if (!confirmed) return;

    const btn = getById('dataladServerDeleteScansTsvBtn');
    const resultDiv = getById('dataladServerDeleteScansTsvResult');
    const originalText = setButtonLoading(btn, true, 'Deleting...');
    try {
        const resp = await fetchWithApiFallback('/api/projects/datalad/remove-scans-tsv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirmed: true }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
            throw new Error(data.error || data.message || 'Failed to delete scans.tsv files');
        }
        if (resultDiv) {
            setHtml(resultDiv, `<div class="alert alert-success py-2 px-3 mb-0"><small>${escapeHtml(data.message || 'Deleted.')}</small></div>`);
        }
    } catch (error) {
        if (resultDiv) {
            setHtml(resultDiv, `<div class="alert alert-danger py-2 px-3 mb-0"><small>${escapeHtml(error.message || 'Failed to delete scans.tsv files')}</small></div>`);
        } else {
            alert(error.message || 'Failed to delete scans.tsv files');
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

export function initDataladServerSection() {
    if (dataladServerModuleInitialized) {
        showDataladServerCard();
        return;
    }
    dataladServerModuleInitialized = true;

    const syncBtn = getById('dataladServerSyncBtn');
    if (syncBtn) syncBtn.addEventListener('click', onSyncClick);

    const finalizeBtn = getById('dataladServerFinalizeBtn');
    if (finalizeBtn) finalizeBtn.addEventListener('click', onFinalizeClick);

    const browseBtn = getById('dataladServerBrowseBtn');
    if (browseBtn) browseBtn.addEventListener('click', onBrowseUrlClick);

    const configForm = getById('dataladServerConfigForm');
    if (configForm) configForm.addEventListener('submit', onSaveConfigSubmit);

    const deleteScansTsvBtn = getById('dataladServerDeleteScansTsvBtn');
    if (deleteScansTsvBtn) deleteScansTsvBtn.addEventListener('click', onDeleteScansTsvClick);

    showDataladServerCard();
}
