import { fetchWithApiFallback } from '../../shared/api.js';

/** Review request body: the uploaded file, or the path picked with Browse. Null until both inputs exist. */
export function reviewFormData({ file, serverPath, idColumn, skipExisting = false }) {
    if (!idColumn || !(file || serverPath)) return null;
    const formData = new FormData();
    if (file) formData.append('file', file);
    else formData.append('source_file_path', serverPath);
    formData.append('id_column', idColumn);
    if (skipExisting) formData.append('skip_existing', 'true');
    return formData;
}

/** Manual overrides are highlighted (they mark a session-mapping problem); left-out rows are muted. */
export function rowClass(row) {
    if (row.reason === 'override') return 'table-warning';
    return row.session === null ? 'text-muted' : '';
}

/** Rows arrive grouped by participant; flip the shade whenever the participant changes. */
export function subjectStripes(rows) {
    let shade = false;
    return rows.map((r, i) => {
        if (i && r.participant !== rows[i - 1].participant) shade = !shade;
        return shade;
    });
}

export function clearReviewTable(body, toggleBtn) {
    toggleBtn?.setAttribute('aria-expanded', 'false');
    body?.replaceChildren();
}

export function createSurveySessionAssignmentsController({ getConvertServerFilePath = () => '' } = {}) {
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
            + '<th>Session</th><th>Skip</th><th>Session override</th></tr></thead><tbody>';
        const stripes = subjectStripes(rows);
        rows.forEach((r, i) => {
            const left = r.session === null;
            html += `<tr data-response-id="${esc(r.response_id)}" data-completed="${r.completed ? 'true' : 'false'}" data-reason="${esc(r.reason)}" class="${rowClass(r)}${stripes[i] ? ' subject-alt' : ''}">`
                + `<td>${esc(r.participant)}</td><td>${esc(r.response_id)}</td>`
                + `<td>${esc(String(r.date).slice(0, 16))}</td><td>${r.completed ? 'yes' : 'no'}</td>`
                + `<td>${esc(r.lastpage)}</td>`
                + `<td class="session-cell">${left ? `left out (${esc(r.reason)})` : esc(r.session)}</td>`
                + `<td><input type="checkbox" data-role="skip" ${left ? 'checked' : ''}></td>`
                + `<td><input type="text" data-role="label" class="form-control form-control-sm" size="14"`
                + ` value="${r.reason === 'override' ? esc(r.session) : ''}" placeholder="auto (by date)"></td></tr>`;
        });
        html += '</tbody></table>';
        (data.warnings || []).forEach((w) => { html += `<div class="text-muted">${esc(w)}</div>`; });
        body.innerHTML = html;
    }

    let surveyId = 'default';
    let loadSeq = 0;

    async function save(body, responseId, payload) {
        try {
            const response = await fetchWithApiFallback('/api/session-assignments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ response_id: responseId, survey_id: surveyId, ...payload }),
            });
            const data = await response.json();
            if (response.ok) return true;
            await load(data.error || 'Save failed');
        } catch (error) {
            await load(`Save failed: ${error.message || error}`);
        }
        return false;
    }

    // `notice` (a failed save) is shown above the freshly loaded table so the controls reflect the saved state.
    async function load(notice = '') {
        const body = document.getElementById('sessionAssignmentsBody');
        const formData = reviewFormData({
            file: document.getElementById('convertSurveyFile')?.files?.[0],
            serverPath: getConvertServerFilePath(),
            idColumn: document.getElementById('convertIdColumn')?.value || '',
            skipExisting: Boolean(document.getElementById('convertSkipExisting')?.checked),
        });
        if (!formData) {
            body.textContent = 'Choose the survey file and the participant ID column first.';
            return;
        }
        const seq = ++loadSeq;
        try {
            const response = await fetchWithApiFallback('/api/session-assignments/review', { method: 'POST', body: formData });
            const data = await response.json();
            if (seq !== loadSeq) return; // a newer load is in flight
            if (!response.ok) {
                body.textContent = data.error || 'Could not build the review table.';
                return;
            }
            surveyId = data.survey_id || 'default';
            render(body, data);
        } catch (error) {
            if (seq === loadSeq) body.textContent = `Could not build the review table: ${error.message || error}`;
            return;
        }
        if (notice) body.insertAdjacentHTML('afterbegin', `<div class="text-danger">${esc(notice)}</div>`);
    }

    // The survey file was removed: drop the table and any load still in flight so it cannot re-open it.
    function reset() {
        loadSeq += 1;
        clearReviewTable(document.getElementById('sessionAssignmentsBody'), document.getElementById('sessionAssignmentsBtn'));
    }

    function initialize() {
        document.getElementById('convertDuplicateHandling')?.addEventListener('change', applyMode);
        const body = document.getElementById('sessionAssignmentsBody');
        const toggleBtn = document.getElementById('sessionAssignmentsBtn');
        toggleBtn?.addEventListener('click', () => {
            const expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
            toggleBtn.setAttribute('aria-expanded', String(!expanded));
            if (!expanded) return load();
            reset();
        });
        // An open table follows the checkbox: imported responses appear or disappear.
        document.getElementById('convertSkipExisting')?.addEventListener('change', () => {
            if (toggleBtn?.getAttribute('aria-expanded') === 'true') load();
        });
        body?.addEventListener('change', async (event) => {
            const row = event.target.closest('tr[data-response-id]');
            if (!row) return;
            const responseId = row.dataset.responseId;
            const role = event.target.dataset.role;
            const hasDecision = ['override', 'skipped', 'included'].includes(row.dataset.reason);
            let payload = null;
            if (role === 'skip') {
                // checked = the row gets no session (incomplete rows start that way)
                const completed = row.dataset.completed === 'true';
                if (completed) payload = event.target.checked ? { skip: true } : { clear: true };
                else payload = event.target.checked ? { clear: true } : { include: true };
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

    return { initialize, applyMode, reset };
}
