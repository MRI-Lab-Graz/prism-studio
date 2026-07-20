/**
 * Remote SSH folder picker -- shared modal for the rsync Destination field
 * and the plain-SSH-sibling case of the DataLad Server URL field. Both
 * write to the same server-resolvable `[user@]host:/path` format, so one
 * modal instance (and one backend endpoint) serves both.
 *
 * `[user@]host:/path` parsing happens entirely server-side on the first
 * call (see projects_remote_browse_blueprint.py) -- this module only ever
 * sends the raw field value once, then tracks the `host` the backend
 * resolved for every subsequent navigation/mkdir call.
 */

import { getById, escapeHtml } from '../../shared/dom.js';
import { fetchWithApiFallback } from '../../shared/api.js';

let pickerInitialized = false;
let currentHost = '';
let currentPath = '';
let currentParent = null;
let resolvePromise = null;

function els() {
    return {
        modalEl: getById('remoteFolderBrowserModal'),
        hostLabel: getById('remoteBrowserHostLabel'),
        listEl: getById('remoteBrowserList'),
        currentPathEl: getById('remoteBrowserCurrentPath'),
        upBtn: getById('remoteBrowserUp'),
        selectBtn: getById('remoteBrowserSelectBtn'),
        newFolderBtn: getById('remoteBrowserNewFolderBtn'),
        newFolderRow: getById('remoteBrowserNewFolderRow'),
        newFolderInput: getById('remoteBrowserNewFolderInput'),
        newFolderCreateBtn: getById('remoteBrowserNewFolderCreateBtn'),
        newFolderCancelBtn: getById('remoteBrowserNewFolderCancelBtn'),
        errorEl: getById('remoteBrowserError'),
    };
}

function showError(message) {
    const { errorEl } = els();
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.style.display = '';
}

function clearError() {
    const { errorEl } = els();
    if (!errorEl) return;
    errorEl.textContent = '';
    errorEl.style.display = 'none';
}

async function load(query) {
    const { listEl, currentPathEl, upBtn, selectBtn } = els();
    listEl.innerHTML = '<div class="d-flex justify-content-center align-items-center py-5 text-muted"><span><i class="fas fa-spinner fa-spin me-2"></i>Loading…</span></div>';
    clearError();
    selectBtn.disabled = true;

    try {
        const params = new URLSearchParams(query);
        const res = await fetchWithApiFallback(`/api/projects/remote-browse/list?${params.toString()}`);
        const data = await res.json();
        if (!res.ok) {
            listEl.innerHTML = '';
            showError(data.error || 'Could not list remote directory.');
            return;
        }

        currentHost = data.host;
        currentPath = data.path;
        currentParent = data.parent;
        currentPathEl.textContent = data.path;
        upBtn.disabled = !data.parent;
        selectBtn.disabled = false;

        let html = '';
        (data.dirs || []).forEach((dir) => {
            html += `<button type="button" class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom rfb-dir text-start bg-white" style="cursor:pointer;" data-path="${escapeHtml(dir.path)}" aria-label="Open folder ${escapeHtml(dir.name)}">
                <i class="fas fa-folder text-warning me-2"></i>
                <span>${escapeHtml(dir.name)}</span>
                <i class="fas fa-chevron-right ms-auto text-muted small"></i>
            </button>`;
        });
        if (!html) {
            html = '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>No subfolders</div>';
        }
        listEl.innerHTML = html;

        listEl.querySelectorAll('.rfb-dir').forEach((el) => {
            el.addEventListener('click', () => load({ host: currentHost, path: el.dataset.path }));
        });
    } catch (error) {
        listEl.innerHTML = '';
        showError(error.message || 'Could not list remote directory.');
    }
}

function finish(result) {
    const { modalEl } = els();
    if (resolvePromise) {
        const resolve = resolvePromise;
        resolvePromise = null;
        resolve(result);
    }
    bootstrap.Modal.getInstance(modalEl)?.hide();
}

function ensureInitialized() {
    if (pickerInitialized) return;
    pickerInitialized = true;

    const {
        modalEl, upBtn, selectBtn, newFolderBtn, newFolderRow,
        newFolderInput, newFolderCreateBtn, newFolderCancelBtn,
    } = els();

    upBtn.addEventListener('click', () => {
        if (!currentParent) return;
        load({ host: currentHost, path: currentParent });
    });

    selectBtn.addEventListener('click', () => finish(`${currentHost}:${currentPath}`));

    newFolderBtn.addEventListener('click', () => {
        newFolderRow.style.display = '';
        newFolderInput.value = '';
        newFolderInput.focus();
    });

    newFolderCancelBtn.addEventListener('click', () => {
        newFolderRow.style.display = 'none';
    });

    newFolderCreateBtn.addEventListener('click', async () => {
        const name = (newFolderInput.value || '').trim();
        if (!name || name.includes('/') || name.includes('\\')) {
            showError('Enter a valid folder name (no "/").');
            return;
        }
        clearError();
        try {
            const res = await fetchWithApiFallback('/api/projects/remote-browse/mkdir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host: currentHost, path: `${currentPath.replace(/\/$/, '')}/${name}` }),
            });
            const data = await res.json();
            if (!res.ok) {
                showError(data.error || 'Could not create folder.');
                return;
            }
            newFolderRow.style.display = 'none';
            await load({ host: currentHost, path: data.path });
        } catch (error) {
            showError(error.message || 'Could not create folder.');
        }
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
        if (resolvePromise) {
            const resolve = resolvePromise;
            resolvePromise = null;
            resolve(null);
        }
    });
}

/**
 * Open the picker. `initialTarget` is the raw current field value (e.g.
 * "user@host:/srv/backups" or just "user@host:" / "user@host") -- parsed
 * server-side. Resolves with the picked "host:/path" string, or null if
 * cancelled/closed.
 */
export function openRemoteFolderPicker(initialTarget) {
    ensureInitialized();
    const { modalEl, hostLabel, newFolderRow } = els();
    if (newFolderRow) newFolderRow.style.display = 'none';
    if (hostLabel) hostLabel.textContent = '…';

    return new Promise((resolve) => {
        resolvePromise = resolve;
        load({ target: initialTarget || '' }).then(() => {
            if (hostLabel && currentHost) hostLabel.textContent = currentHost;
        });
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    });
}
