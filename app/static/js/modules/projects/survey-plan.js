/**
 * Survey Version Plan — projects module
 *
 * Handles loading, rendering, and saving the survey_version_mapping
 * stored in project.json.
 *
 * API:
 *   GET  /api/projects/survey-plan          → { survey_version_mapping, available }
 *   POST /api/projects/survey-plan          → save mapping
 *   POST /api/projects/survey-plan/refresh  → re-discover + enrich
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/** @type {{ [taskName: string]: { default_version: string, by_session: object, by_run: object, by_session_run: object } }} */
let _mapping = {};

/** @type {{ [taskName: string]: { versions: string[], filename: string } }} */
let _available = {};

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);

function showAlert(container, msg, type = 'success') {
    container.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show py-2 small" role="alert">
            ${msg}
            <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
        </div>`;
}

// ---------------------------------------------------------------------------
// Public: init (called when a project is loaded)
// ---------------------------------------------------------------------------

export async function initSurveyPlan() {
    const card = $('surveyPlanCard');
    if (!card) return;

    // Show card when project is loaded
    card.style.display = '';

    // Attach button events once
    $('surveyPlanRefreshBtn')?.addEventListener('click', handleRefresh);
    $('surveyPlanSaveBtn')?.addEventListener('click', handleSave);

    // Initial load
    await loadAndRender();
}

export function hideSurveyPlan() {
    const card = $('surveyPlanCard');
    if (card) card.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Load & render
// ---------------------------------------------------------------------------

async function loadAndRender() {
    try {
        const data = await fetch('/api/projects/survey-plan').then(r => r.json());
        if (!data.success) {
            showAlert($('surveyPlanAlertArea'), `Could not load survey plan: ${data.error || 'unknown error'}`, 'danger');
            return;
        }
        _mapping = data.survey_version_mapping || {};
        _available = data.available || {};
        renderRows();
    } catch (err) {
        showAlert($('surveyPlanAlertArea'), `Network error loading survey plan: ${err.message}`, 'danger');
    }
}

function renderRows() {
    const container = $('surveyPlanRows');
    const empty = $('surveyPlanEmpty');
    if (!container) return;

    // Remove all existing survey rows (but keep the empty placeholder)
    container.querySelectorAll('.survey-plan-row').forEach(el => el.remove());

    const taskNames = Object.keys(_mapping);
    if (taskNames.length === 0) {
        if (empty) empty.style.display = '';
        return;
    }
    if (empty) empty.style.display = 'none';

    const rowTpl = $('surveyPlanRowTemplate');
    for (const taskName of taskNames.sort()) {
        const entry = _mapping[taskName] || {};
        const info = _available[taskName] || {};
        const versions = info.versions || [entry.default_version || 'default'];

        const row = rowTpl.content.cloneNode(true).querySelector('.survey-plan-row');
        row.dataset.taskName = taskName;
        row.querySelector('.survey-plan-task-label').textContent = taskName;
        row.querySelector('.survey-plan-filename').textContent = info.filename ? `(${info.filename})` : '';

        // Default version dropdown
        const sel = row.querySelector('.survey-plan-default-version');
        populateVersionSelect(sel, versions, entry.default_version);

        // Session overrides
        const sessionContainer = row.querySelector('.survey-plan-session-rows');
        renderOverrideRows(sessionContainer, entry.by_session || {}, versions);

        // Run overrides
        const runContainer = row.querySelector('.survey-plan-run-rows');
        renderOverrideRows(runContainer, entry.by_run || {}, versions);

        // Toggle overrides visibility
        const toggleBtn = row.querySelector('.survey-plan-toggle-overrides');
        const overridesDiv = row.querySelector('.survey-plan-overrides');
        toggleBtn.addEventListener('click', () => {
            const shown = overridesDiv.style.display !== 'none';
            overridesDiv.style.display = shown ? 'none' : '';
            toggleBtn.classList.toggle('active', !shown);
        });

        // Add session row button
        row.querySelector('.survey-plan-add-session').addEventListener('click', () => {
            addOverrideRow(sessionContainer, versions);
        });

        // Add run row button
        row.querySelector('.survey-plan-add-run').addEventListener('click', () => {
            addOverrideRow(runContainer, versions);
        });

        container.appendChild(row);
    }
}

function populateVersionSelect(selectEl, versions, selected) {
    selectEl.innerHTML = '';
    for (const v of versions) {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        if (v === selected) opt.selected = true;
        selectEl.appendChild(opt);
    }
}

function renderOverrideRows(container, overrideMap, versions) {
    container.innerHTML = '';
    for (const [key, val] of Object.entries(overrideMap)) {
        addOverrideRow(container, versions, key, val);
    }
}

function addOverrideRow(container, versions, key = '', val = '') {
    const tpl = $('surveyPlanOverrideRowTemplate');
    const row = tpl.content.cloneNode(true).querySelector('.survey-plan-override-row');

    row.querySelector('.override-key').value = key;
    populateVersionSelect(row.querySelector('.override-version'), versions, val);

    row.querySelector('.survey-plan-remove-override').addEventListener('click', () => {
        row.remove();
    });

    container.appendChild(row);
}

// ---------------------------------------------------------------------------
// Collect current UI state → mapping object
// ---------------------------------------------------------------------------

function collectMapping() {
    const result = {};
    document.querySelectorAll('.survey-plan-row').forEach(row => {
        const taskName = row.dataset.taskName;
        if (!taskName) return;

        const defaultVersion = row.querySelector('.survey-plan-default-version')?.value || '';

        const by_session = collectOverrideMap(row.querySelector('.survey-plan-session-rows'));
        const by_run = collectOverrideMap(row.querySelector('.survey-plan-run-rows'));

        // Preserve existing by_session_run (not editable in UI v1, keep as-is)
        const existing = _mapping[taskName] || {};

        result[taskName] = {
            default_version: defaultVersion,
            by_session,
            by_run,
            by_session_run: existing.by_session_run || {},
        };
    });
    return result;
}

function collectOverrideMap(container) {
    const map = {};
    if (!container) return map;
    container.querySelectorAll('.survey-plan-override-row').forEach(row => {
        const key = (row.querySelector('.override-key')?.value || '').trim();
        const val = row.querySelector('.override-version')?.value || '';
        if (key && val) {
            map[key] = val;
        }
    });
    return map;
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

async function handleSave() {
    const alertArea = $('surveyPlanAlertArea');
    const btn = $('surveyPlanSaveBtn');
    if (btn) btn.disabled = true;

    try {
        const mapping = collectMapping();
        const resp = await fetch('/api/projects/survey-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ survey_version_mapping: mapping }),
        }).then(r => r.json());

        if (resp.success) {
            _mapping = mapping;
            showAlert(alertArea, '<i class="fas fa-check me-1"></i>Survey plan saved.', 'success');
        } else {
            showAlert(alertArea, `Save failed: ${resp.error || 'unknown error'}`, 'danger');
        }
    } catch (err) {
        showAlert(alertArea, `Network error: ${err.message}`, 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------

async function handleRefresh() {
    const alertArea = $('surveyPlanAlertArea');
    const btn = $('surveyPlanRefreshBtn');
    if (btn) { btn.disabled = true; }

    try {
        const resp = await fetch('/api/projects/survey-plan/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        }).then(r => r.json());

        if (resp.success) {
            _mapping = resp.survey_version_mapping || {};
            _available = resp.available || {};
            renderRows();

            const added = resp.added || [];
            const msg = added.length > 0
                ? `<i class="fas fa-sync-alt me-1"></i>Detected surveys refreshed. New: <strong>${added.join(', ')}</strong>`
                : `<i class="fas fa-sync-alt me-1"></i>Survey plan refreshed. No new surveys found.`;
            showAlert(alertArea, msg, added.length > 0 ? 'info' : 'secondary');
        } else {
            showAlert(alertArea, `Refresh failed: ${resp.error || 'unknown error'}`, 'danger');
        }
    } catch (err) {
        showAlert(alertArea, `Network error: ${err.message}`, 'danger');
    } finally {
        if (btn) btn.disabled = false;
    }
}
