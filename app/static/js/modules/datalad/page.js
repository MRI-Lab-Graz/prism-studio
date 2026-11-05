/**
 * The DataLad page. It only triggers: every button calls a route that runs the same function as a
 * `prism_tools datalad ...` command, and what to offer next is the backend's `next_step` (render-state.js).
 */

import { renderState, sendAnywayLabel } from './render-state.js';
import { openFromServer, runJob as runJobRoute } from './job.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { escapeHtml, getById } from '../../shared/dom.js';
import { saveDataladSnapshot } from '../../shared/datalad-save.js';
import { getLatestFromServer } from '../../shared/datalad-update.js';
import { enableDatalad } from '../../shared/datalad-enable.js';
import { browseFolderWithFallback } from '../../shared/path-picker.js';
import { askGitIdentity } from '../projects/git-identity-dialog.js';
import { runDataladCheck } from '../projects/datalad_setup_check.js';
import { openRemoteFolderPicker } from '../projects/remote_folder_picker.js';
import { readContentScope, renderScopeLists, syncScopeFilterChange } from '../projects/export.js';

// The page's own state reads also count nested datasets not registered yet (`datalad status --check-nested`, about a
// second); the navbar's count does not ask for that.
const STATE_AFTER_ACTION = '?check_server=1&check_nested=1';
const STATE_FULL = '?check_server=1&check_nested=1&validate=1';

const latestRequestedFor = new Set();  // projects already asked for their latest changes during this page load
let projectPath = '';
let currentState = null;
let busy = false;
let locationKind = '';  // 'put' | 'open'
let putAllowInvalid = false;

const askIdentity = () => askGitIdentity({ fetchWithApiFallback });

function setResult(html) {
    getById('dataladJobResult').innerHTML = html;
}

function alertHtml(kind, text) {
    return `<div class="alert alert-${kind} mb-0" role="status">${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
}

function setBusy(value) {
    busy = value;
    document.querySelectorAll('#dataladStepCard [data-action], #dataladMore [data-action]').forEach((btn) => {
        btn.disabled = value || btn.dataset.unavailable === '1';
    });
}

function actionButton(action, tone) {
    if (action.id === 'settings') {
        const link = document.createElement('a');
        link.className = `btn ${tone}`;
        link.href = getById('dataladRoot').dataset.settingsUrl;
        link.textContent = action.label;
        return link;
    }
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `btn ${tone}`;
    btn.textContent = action.label;
    btn.dataset.action = action.id;
    if (action.sibling) btn.dataset.sibling = action.sibling;
    if (action.disabled) btn.dataset.unavailable = '1';  // e.g. Get data with no project open
    btn.disabled = busy || Boolean(action.disabled);
    btn.addEventListener('click', () => runAction(action, btn));
    return btn;
}

function render(state) {
    currentState = state;
    const view = renderState(state);
    getById('dataladStepTitle').textContent = view.title;
    getById('dataladStepText').textContent = view.text;
    const notice = getById('dataladNotice');
    notice.className = view.notice ? `alert alert-${view.notice.kind}` : 'alert d-none';
    notice.textContent = view.notice ? view.notice.text : '';
    getById('dataladPrimary').replaceChildren(...(view.primary ? [actionButton(view.primary, 'btn-primary')] : []));
    getById('dataladSecondary').replaceChildren(...view.secondary.map((a) => actionButton(a, 'btn-outline-primary')));
    getById('dataladMore').replaceChildren(...view.more.map((a) => actionButton(a, 'btn-outline-secondary')));
}

async function loadState(query = '') {
    if (!projectPath) {
        render(null);
        return;
    }
    try {
        const response = await fetchWithApiFallback(`/api/projects/datalad/state${query}`);
        render(response.ok ? await response.json() : null);
        if (query) window.refreshNavbarDataladCount?.(projectPath);  // after an action: the navbar count too
    } catch {
        render(null);
    }
}

// Get the latest from the server once per project and page load, without holding up the page.
function getLatestOnce(path) {
    if (!path || latestRequestedFor.has(path) || !currentState?.enabled) return;
    latestRequestedFor.add(path);
    getLatestFromServer(fetchWithApiFallback)
        .then(({ notice }) => {
            if (notice && !busy) setResult(alertHtml(notice.kind, notice.text));
        })
        .catch(() => {})
        .finally(() => loadState(STATE_FULL));
}

// The job stopped on validation errors: list them; "Send anyway" repeats that same job, acknowledged.
function showErrors(result, repeatAcknowledged) {
    const errors = result.errors || [];
    const list = errors.slice(0, 50).map((e) => `<li>${escapeHtml(e)}</li>`).join('');
    setResult(`<div class="alert alert-warning mb-0">
        <p class="mb-2">${escapeHtml(result.message || `${errors.length} validation error(s).`)}</p>
        <ul class="small mb-3">${list}</ul>
        <button type="button" class="btn btn-outline-danger btn-sm" id="dataladSendAnywayBtn">${escapeHtml(sendAnywayLabel(errors.length))}</button>
    </div>`);
    getById('dataladSendAnywayBtn').addEventListener('click', repeatAcknowledged);
}

// How a job looks on this page (job.js runs it).
const jobUi = {
    start(cancel) {
        setResult('');
        jobUi.progress(0, 'Starting...');
        getById('dataladJobProgress').classList.remove('d-none');
        getById('dataladJobCancelBtn').onclick = cancel;
        setBusy(true);
    },
    progress(percent, message) {
        const bar = getById('dataladJobProgressBar');
        bar.style.width = `${percent}%`;
        bar.textContent = `${percent}%`;
        bar.setAttribute('aria-valuenow', String(percent));
        getById('dataladJobStatusText').textContent = message;
    },
    result(kind, text) {
        setResult(alertHtml(kind, text));
    },
    errors: showErrors,
    end() {
        getById('dataladJobCancelBtn').onclick = null;
        getById('dataladJobProgress').classList.add('d-none');
        setBusy(false);
        loadState(STATE_AFTER_ACTION);
    },
};

function runJob(route, body) {
    return runJobRoute(fetchWithApiFallback, route, body, { ui: jobUi, askIdentity });
}

// "Send anyway" offered by the state (?validate=1 found errors): the step the page leads with, acknowledged.
function sendAnyway() {
    if (currentState?.next_step === 'put_on_server') {
        showLocationForm('put', { allowInvalid: true });
    } else {
        runJob('/api/projects/datalad-server/sync/start', { project_path: projectPath, allow_invalid: true });
    }
}

function showLocationForm(kind, { allowInvalid = false } = {}) {
    locationKind = kind;
    putAllowInvalid = allowInvalid;
    getById('dataladTargetWrap').classList.toggle('d-none', kind !== 'open');
    getById('dataladLocationStartBtn').textContent = kind === 'open' ? 'Open from server' : 'Put on server';
    getById('dataladLocationForm').classList.remove('d-none');
    getById('dataladLocation').focus();
}

async function onLocationSubmit(event) {
    event.preventDefault();
    const location = getById('dataladLocation').value.trim();
    getById('dataladLocationForm').classList.add('d-none');
    if (locationKind === 'open') {
        await openFromServer(fetchWithApiFallback, location, getById('dataladTarget').value.trim(), {
            ui: jobUi, askIdentity, reload: () => window.location.reload(),
        });
    } else {
        await runJob('/api/projects/datalad/put-on-server', { project_path: projectPath, location, allow_invalid: putAllowInvalid });
    }
}

async function showGetData() {
    getById('dataladGetDataForm').classList.remove('d-none');
    try {
        const response = await fetchWithApiFallback('/api/projects/export/structure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_path: projectPath }),
        });
        const data = await response.json();
        if (data.success) renderScopeLists(data);
    } catch {
        // the lists keep their "Load a project" text; Get data then fetches everything
    }
}

async function runAction(action, btn) {
    if (busy) return;
    switch (action.id) {
    case 'open-from-server':
        showLocationForm('open');
        break;
    case 'put-on-server':
        showLocationForm('put');
        break;
    case 'enable': {
        if (!window.confirm(`${action.label} for this project?\n\nThis creates or completes the DataLad/Git metadata in the project folder and saves a snapshot.\n\nProject: ${projectPath}`)) return;
        setBusy(true);
        setResult(alertHtml('info', `${action.label}...`));
        try {
            const data = await enableDatalad(fetchWithApiFallback, {
                askIdentity,
                onProgress: (text) => setResult(alertHtml('info', text)),
            });
            setResult(alertHtml('success', data.message || data.datalad?.message || 'DataLad is on.'));
        } catch (error) {
            setResult(alertHtml('danger', error.message));
        } finally {
            setBusy(false);
            await loadState(STATE_AFTER_ACTION);
        }
        break;
    }
    case 'save': {
        // An empty description is fine: the backend uses its default message, as `datalad save` does.
        const message = window.prompt('Describe this snapshot (leave empty for the default)', '');
        if (message === null) return;
        setBusy(true);
        setResult(alertHtml('info', 'Saving...'));
        try {
            const { response, data } = await saveDataladSnapshot(fetchWithApiFallback, message.trim());
            setResult(response.ok && data.success
                ? alertHtml('success', data.message || 'Saved.')
                : alertHtml('danger', data.error || data.message || 'Could not save.'));
        } catch (error) {
            setResult(alertHtml('danger', error.message || 'Could not save.'));
        } finally {
            setBusy(false);
            await loadState(STATE_AFTER_ACTION);
        }
        break;
    }
    case 'sync':
        await runJob('/api/projects/datalad-server/sync/start', { project_path: projectPath, sibling_name: action.sibling || null });
        break;
    case 'send-anyway':
        sendAnyway();
        break;
    case 'get-latest': {
        setBusy(true);
        try {
            const { notice } = await getLatestFromServer(fetchWithApiFallback);
            setResult(alertHtml(notice ? notice.kind : 'secondary', notice ? notice.text : 'Nothing new on the server.'));
        } finally {
            setBusy(false);
            await loadState(STATE_AFTER_ACTION);
        }
        break;
    }
    case 'get-data':
        await showGetData();
        break;
    case 'doctor':
        btn.dataset.result = 'dataladDoctorResult';
        btn.dataset.urlInput = 'dataladLocation';
        await runDataladCheck(btn);
        break;
    default:
        break;
    }
}

export async function initializeDataladPage() {
    projectPath = String(getById('dataladRoot').dataset.currentProjectPath || '').trim();

    getById('dataladLocationForm').addEventListener('submit', onLocationSubmit);
    getById('dataladLocationCancelBtn').addEventListener('click', () => getById('dataladLocationForm').classList.add('d-none'));
    getById('dataladLocationBrowseBtn').addEventListener('click', async () => {
        const input = getById('dataladLocation');
        const picked = await openRemoteFolderPicker(input.value);
        if (picked) input.value = picked;
    });
    getById('dataladTargetBrowseBtn').addEventListener('click', async () => {
        const input = getById('dataladTarget');
        const picked = await browseFolderWithFallback(fetchWithApiFallback, { title: 'Choose a folder for the project', startPath: input.value });
        if (picked) input.value = picked;
    });
    const getDataForm = getById('dataladGetDataForm');
    getDataForm.addEventListener('change', (event) => syncScopeFilterChange(event.target));
    getDataForm.addEventListener('submit', (event) => {
        event.preventDefault();
        runJob('/api/projects/datalad/get-data', { project_path: projectPath, ...readContentScope() });
    });
    getById('dataladGetDataCancelBtn').addEventListener('click', () => getDataForm.classList.add('d-none'));

    window.addEventListener('prism-project-opened', (event) => {
        const path = String(event.detail?.path || '').trim();
        if (!path) return;
        projectPath = path;
        loadState().then(() => getLatestOnce(path));
    });

    await loadState();
    getLatestOnce(projectPath);  // then reloads the state with the server, nested and validation checks
}
