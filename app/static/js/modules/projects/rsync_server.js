/**
 * Projects Module - Push to Remote Server (rsync)
 *
 * Plain-copy fallback for users not using DataLad: a single "Sync now"
 * action that copies the project to an SSH target or local/mounted path
 * with `rsync -a`. There is no sibling/connection state to disconnect —
 * each sync is additive, optionally followed by a checksum verification.
 */

import { setButtonLoading } from './helpers.js';
import { getById, setHtml, hide, show, escapeHtml } from '../../shared/dom.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

let rsyncServerModuleInitialized = false;
let activeJobId = null;
let activeJobCancelled = false;

function getProgressEls() {
    return {
        progressDiv: getById('rsyncServerProgress'),
        progressBar: getById('rsyncServerProgressBar'),
        progressText: getById('rsyncServerProgressText'),
        statusText: getById('rsyncServerStatusText'),
        resultDiv: getById('rsyncServerResult'),
        cancelBtn: getById('rsyncServerCancelBtn'),
    };
}

function setStatusBadge(text, tone = 'secondary') {
    const badge = getById('rsyncServerStatusBadge');
    if (!badge) return;
    badge.className = `badge bg-${tone}`;
    badge.textContent = text;
}

/**
 * Show/hide the "Push to Remote Server" card and refresh its availability status.
 */
export function showRsyncServerCard() {
    const card = getById('rsyncServerCard');
    if (!card) return;

    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        hide(card);
        return;
    }

    show(card);
    refreshRsyncServerStatus(projectPath);
}

async function refreshRsyncServerStatus(projectPath) {
    const detail = getById('rsyncServerStatusDetail');
    setStatusBadge('Checking...', 'secondary');
    if (detail) detail.textContent = 'Checking rsync availability...';

    try {
        const resp = await fetchWithApiFallback(
            `/api/projects/rsync-server/status?project_path=${encodeURIComponent(projectPath)}`
        );
        if (!resp.ok) throw new Error('Could not load status');
        const status = await resp.json();

        const targetInput = getById('rsyncServerTarget');
        const labelInput = getById('rsyncServerLabel');
        if (targetInput && !targetInput.value) targetInput.value = status.remote_target || '';
        if (labelInput && !labelInput.value) labelInput.value = status.remote_label || '';

        if (!status.rsync_available) {
            setStatusBadge('rsync not found', 'secondary');
            if (detail) detail.textContent = 'rsync is not available in this environment, so this project cannot be copied to a server.';
        } else if (status.configured) {
            setStatusBadge('Configured', 'info');
            if (detail) detail.textContent = `Destination "${status.remote_label || status.remote_target}" is saved. Sync now to back up.`;
        } else {
            setStatusBadge('Not configured', 'secondary');
            if (detail) detail.textContent = 'No destination saved yet. Enter one above and click "Sync now".';
        }
    } catch (error) {
        setStatusBadge('Unknown', 'secondary');
        if (detail) detail.textContent = error.message || 'Could not load rsync status.';
    }
}

function getRsyncRequestData(projectPath) {
    return {
        project_path: projectPath,
        remote_target: (getById('rsyncServerTarget')?.value || '').trim() || null,
        remote_label: (getById('rsyncServerLabel')?.value || '').trim() || null,
    };
}

async function requestCancelForActiveJob() {
    if (!activeJobId) return;
    try {
        await fetchWithApiFallback(`/api/projects/rsync-server/sync/${encodeURIComponent(activeJobId)}/cancel`, { method: 'DELETE' });
    } catch {
        // Ignore cancellation network failures; the UI already reflects the local cancel state.
    }
}

async function onSyncClick() {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        alert('No project is currently loaded');
        return;
    }
    const btn = getById('rsyncServerSyncBtn');
    const originalText = setButtonLoading(btn, true, 'Syncing...');
    const requestData = getRsyncRequestData(projectPath);
    if (!requestData.remote_target) {
        alert('Enter a destination first');
        setButtonLoading(btn, false, null, originalText);
        return;
    }
    requestData.verify = !!getById('rsyncServerVerify')?.checked;

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
        void requestCancelForActiveJob();
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Cancelled.</div>`);
        }
        setButtonLoading(btn, false, null, originalText);
    }
    if (cancelBtn) cancelBtn.onclick = onCancelClick;

    try {
        const startResp = await fetchWithApiFallback('/api/projects/rsync-server/sync/start', {
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
            await requestCancelForActiveJob();
            return;
        }

        const MAX_POLLS = 2250; // ~30 minutes at 800ms/poll
        for (let i = 0; i < MAX_POLLS; i++) {
            if (activeJobCancelled) break;
            await new Promise((r) => setTimeout(r, 800));
            if (activeJobCancelled) break;

            const statusResp = await fetchWithApiFallback(
                `/api/projects/rsync-server/sync/${encodeURIComponent(activeJobId)}/status`
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
                            <h5><i class="fas fa-check-circle me-2"></i>Synced to server</h5>
                            <p class="mb-0">${escapeHtml((status.result && status.result.message) || status.message || '')}</p>
                        </div>
                    `);
                }
                refreshRsyncServerStatus(requestData.project_path);
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
            setButtonLoading(btn, false, null, originalText);
        }
    }
}

async function onSaveConfigSubmit(e) {
    e.preventDefault();
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        alert('No project is currently loaded');
        return;
    }
    const btn = getById('rsyncServerSaveConfigBtn');
    const originalText = setButtonLoading(btn, true, 'Saving...');
    try {
        const resp = await fetchWithApiFallback('/api/projects/rsync-server/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getRsyncRequestData(projectPath)),
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'Failed to save server settings');
        }
        await refreshRsyncServerStatus(projectPath);
    } catch (error) {
        alert(error.message || 'Failed to save server settings');
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

export function initRsyncServerSection() {
    if (rsyncServerModuleInitialized) {
        showRsyncServerCard();
        return;
    }
    rsyncServerModuleInitialized = true;

    const syncBtn = getById('rsyncServerSyncBtn');
    if (syncBtn) syncBtn.addEventListener('click', onSyncClick);

    const configForm = getById('rsyncServerConfigForm');
    if (configForm) configForm.addEventListener('submit', onSaveConfigSubmit);

    showRsyncServerCard();
}
