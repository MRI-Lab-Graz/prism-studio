import { fetchWithApiFallback } from '../../shared/api.js';

export function createSurveySessionAssignmentsController() {
    const DERIVED_HINT = 'Sessions are numbered 1, 2, … by startdate (completed responses only).';
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));

    function applyMode() {
        const derived = document.getElementById('convertDuplicateHandling')?.value === 'sessions';
        const group = document.getElementById('convertSessionGroup');
        const select = document.getElementById('convertSessionSelect');
        const custom = document.getElementById('convertSessionCustom');
        const hint = document.getElementById('convertSessionHint');
        const badge = document.getElementById('convertSessionBadge');
        if (!group) return;
        group.classList.toggle('session-derived', derived);
        [select, custom].forEach((el) => {
            if (!el) return;
            el.disabled = derived;
            if (derived) el.value = '';
        });
        if (hint) {
            if (hint.dataset.original === undefined) hint.dataset.original = hint.firstChild?.textContent || '';
            if (hint.firstChild) hint.firstChild.textContent = derived ? DERIVED_HINT : hint.dataset.original;
        }
        if (badge) badge.textContent = derived ? 'FROM DATES' : 'REQUIRED';
        document.getElementById('sessionAssignmentsCard')?.classList.toggle('d-none', !derived);
    }

    function render(body, data) {
        const rows = Array.isArray(data.rows) ? data.rows : [];
        let html = '<table class="table table-sm table-bordered mb-2"><thead><tr>'
            + '<th>Participant</th><th>Response</th><th>Date</th><th>Done</th><th>Last page</th>'
            + '<th>Session</th><th>Skip</th><th>Set label</th></tr></thead><tbody>';
        rows.forEach((r) => {
            const left = r.session === null;
            html += `<tr data-response-id="${esc(r.response_id)}" data-reason="${esc(r.reason)}" class="${left ? 'text-muted' : ''}">`
                + `<td>${esc(r.participant)}</td><td>${esc(r.response_id)}</td>`
                + `<td>${esc(String(r.date).slice(0, 16))}</td><td>${r.completed ? 'yes' : 'no'}</td>`
                + `<td>${esc(r.lastpage)}</td>`
                + `<td class="session-cell">${left ? `left out (${esc(r.reason)})` : esc(r.session)}</td>`
                + `<td><input type="checkbox" data-role="skip" ${r.reason === 'skipped' ? 'checked' : ''}></td>`
                + `<td><input type="text" data-role="label" class="form-control form-control-sm" size="8"`
                + ` value="${r.reason === 'override' ? esc(r.session) : ''}" placeholder="auto"></td></tr>`;
        });
        html += '</tbody></table>';
        (data.warnings || []).forEach((w) => { html += `<div class="text-muted">${esc(w)}</div>`; });
        body.innerHTML = html;
    }

    async function save(body, responseId, payload) {
        const response = await fetchWithApiFallback('/api/session-assignments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response_id: responseId, ...payload }),
        });
        const data = await response.json();
        if (!response.ok) {
            body.insertAdjacentHTML('afterbegin', `<div class="text-danger">${esc(data.error || 'Save failed')}</div>`);
            return false;
        }
        return true;
    }

    async function load() {
        const body = document.getElementById('sessionAssignmentsBody');
        const file = document.getElementById('convertSurveyFile')?.files?.[0];
        const idColumn = document.getElementById('convertIdColumn')?.value || '';
        if (!file || !idColumn) {
            body.textContent = 'Choose the survey file (from your computer) and the participant ID column first.';
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('id_column', idColumn);
        const response = await fetchWithApiFallback('/api/session-assignments/review', { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok) {
            body.textContent = data.error || 'Could not build the review table.';
            return;
        }
        render(body, data);
    }

    function initialize() {
        document.getElementById('convertDuplicateHandling')?.addEventListener('change', applyMode);
        document.getElementById('sessionAssignmentsBtn')?.addEventListener('click', load);
        const body = document.getElementById('sessionAssignmentsBody');
        body?.addEventListener('change', async (event) => {
            const row = event.target.closest('tr[data-response-id]');
            if (!row) return;
            const responseId = row.dataset.responseId;
            const role = event.target.dataset.role;
            const hasDecision = ['override', 'skipped'].includes(row.dataset.reason);
            let payload = null;
            if (role === 'skip') {
                payload = event.target.checked ? { skip: true } : { clear: true };
            } else if (role === 'label') {
                const label = event.target.value.trim();
                payload = label ? { session: label } : { clear: true };
            }
            // nothing saved for this response: clearing is a no-op, so no request (the endpoint answers 400)
            if (payload?.clear && !hasDecision) return;
            if (payload && await save(body, responseId, payload)) await load();
        });
        applyMode();
    }

    return { initialize, applyMode };
}
