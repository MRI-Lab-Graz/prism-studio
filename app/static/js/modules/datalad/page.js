/**
 * The DataLad page: enable and save. It only triggers: every button calls a route that runs the same function as a
 * `prism_tools datalad ...` command, and what to offer next is the backend's `next_step` (render-state.js).
 * Sending, getting the latest and getting data are Worldline Desktop's job.
 */

import { renderState } from './render-state.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { escapeHtml, getById } from '../../shared/dom.js';
import { saveDataladSnapshot } from '../../shared/datalad-save.js';
import { enableDatalad } from '../../shared/datalad-enable.js';
import { askGitIdentity } from '../projects/git-identity-dialog.js';
import { runDataladCheck } from '../projects/datalad_setup_check.js';

// The page's own state reads also count nested datasets not registered yet (`datalad status --check-nested`, about a
// second); the navbar's count does not ask for that.
const STATE_AFTER_ACTION = '?check_nested=1';

let projectPath = '';
let busy = false;

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
        btn.disabled = value;
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
    btn.disabled = busy;
    btn.addEventListener('click', () => runAction(action, btn));
    return btn;
}

function render(state) {
    const view = renderState(state);
    getById('dataladStepTitle').textContent = view.title;
    getById('dataladStepText').textContent = view.text;
    const notice = getById('dataladNotice');
    notice.className = view.notice ? `alert alert-${view.notice.kind}` : 'alert d-none';
    notice.textContent = view.notice ? view.notice.text : '';
    getById('dataladPrimary').replaceChildren(...(view.primary ? [actionButton(view.primary, 'btn-primary')] : []));
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

async function runAction(action, btn) {
    if (busy) return;
    switch (action.id) {
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
    case 'doctor':
        btn.dataset.result = 'dataladDoctorResult';
        await runDataladCheck(btn);
        break;
    default:
        break;
    }
}

export async function initializeDataladPage() {
    projectPath = String(getById('dataladRoot').dataset.currentProjectPath || '').trim();

    window.addEventListener('prism-project-opened', (event) => {
        const path = String(event.detail?.path || '').trim();
        if (!path) return;
        projectPath = path;
        loadState();
    });

    await loadState(STATE_AFTER_ACTION);
}
