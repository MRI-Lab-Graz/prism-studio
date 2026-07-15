/**
 * Projects Module - Push to Server (destination toggle)
 *
 * "Push to DataLad Server" and "Push to Remote Server (rsync)" now live in
 * one card (push_server_section.html) because picking a destination is an
 * either/or decision, not two independent features. This module only owns
 * the DataLad-vs-rsync toggle and the outer card's visibility/status badge;
 * each destination's own sync/finalize/config logic still lives in
 * datalad_server.js and rsync_server.js untouched.
 */

import { getById, show, hide } from '../../shared/dom.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

const STORAGE_KEY = 'prism_push_server_target';

function getSelectedTarget() {
    return getById('pushTargetRsync')?.checked ? 'rsync' : 'datalad';
}

function syncHeaderBadge() {
    const headerBadge = getById('pushServerStatusBadge');
    if (!headerBadge) return;

    const target = getSelectedTarget();
    const label = target === 'rsync' ? 'rsync' : 'DataLad';
    const sourceBadge = getById(target === 'rsync' ? 'rsyncServerStatusBadge' : 'dataladServerStatusBadge');

    if (!sourceBadge) {
        headerBadge.textContent = 'Not configured';
        headerBadge.className = 'badge bg-secondary ms-1';
        return;
    }
    headerBadge.textContent = `${label}: ${sourceBadge.textContent}`;
    headerBadge.className = `${sourceBadge.className} ms-1`;
}

function applyState() {
    const outerCard = getById('pushServerCard');
    const dataladPanel = getById('dataladServerCard');
    const rsyncPanel = getById('rsyncServerCard');
    const target = getSelectedTarget();

    if (resolveCurrentProjectPath()) {
        if (outerCard) show(outerCard);
        if (dataladPanel) dataladPanel.style.display = target === 'datalad' ? '' : 'none';
        if (rsyncPanel) rsyncPanel.style.display = target === 'rsync' ? '' : 'none';
    } else if (outerCard) {
        hide(outerCard);
    }
    syncHeaderBadge();
}

function observeBadge(id) {
    const badge = getById(id);
    if (!badge) return;
    new MutationObserver(syncHeaderBadge).observe(badge, { characterData: true, childList: true, subtree: true });
}

/**
 * Apply the toggle/visibility state. Call after initDataladServerSection()
 * and initRsyncServerSection() so this runs last and wins over their own
 * (project-loaded-only) show/hide calls.
 */
export function initPushServerToggle() {
    const dataladRadio = getById('pushTargetDatalad');
    const rsyncRadio = getById('pushTargetRsync');

    let stored = null;
    try {
        stored = window.localStorage?.getItem(STORAGE_KEY);
    } catch {
        // Storage may be unavailable (private browsing); fall back to the default.
    }

    if (stored === 'rsync' && rsyncRadio) {
        rsyncRadio.checked = true;
    } else if (dataladRadio) {
        dataladRadio.checked = true;
    }

    function onChange() {
        try {
            window.localStorage?.setItem(STORAGE_KEY, getSelectedTarget());
        } catch {
            // Ignore storage failures; the toggle still works for this page view.
        }
        applyState();
    }

    if (dataladRadio) dataladRadio.addEventListener('change', onChange);
    if (rsyncRadio) rsyncRadio.addEventListener('change', onChange);

    applyState();
    observeBadge('dataladServerStatusBadge');
    observeBadge('rsyncServerStatusBadge');
}
