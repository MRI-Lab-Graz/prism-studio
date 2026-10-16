/** Structured eligibility criteria (Study Metadata > Eligibility).
 *
 * Stored in project.json as Eligibility.Criteria; the validator checks
 * participants.tsv against them (warnings only). Term list: NeuroBagel terms
 * plus "Other measure" for anything without a standard (IQ, VO2max, ...).
 */
import { escapeHtml } from '../../shared/dom.js';

export const TERMS = [
    { term: 'nb:Age', label: 'Age', type: 'numeric', unit: 'years' },
    { term: 'nb:Sex', label: 'Sex', type: 'categorical', values: ['Male', 'Female', 'Other'] },
    { term: 'nb:Handedness', label: 'Handedness', type: 'categorical', values: ['Left', 'Right', 'Ambidextrous'] },
    { term: 'nb:Group', label: 'Group', type: 'categorical' },
    { term: 'nb:Diagnosis', label: 'Diagnosis', type: 'categorical' },
    { term: 'nb:EducationLevel', label: 'Education level', type: 'categorical' },
    { term: null, label: 'Other measure', type: 'numeric' },
];

const termInfo = (term) => TERMS.find((t) => t.term === term) || TERMS[TERMS.length - 1];

export function newRow(term) {
    const info = termInfo(term);
    return {
        term: info.term,
        label: info.term ? info.label : '',
        type: info.type,
        mode: 'include',
        min: '',
        max: '',
        unit: info.unit || '',
        values: [],
        accepted: false, // a draft until the user clicks the check mark
    };
}

export function rowsFromCriteria(criteria) {
    return (criteria || []).map((c) => ({
        ...c, // keys the form does not know about survive a save
        id: c.id,
        term: c.term ?? null,
        label: c.label || (c.term ? termInfo(c.term).label : '') || c.id || '',
        type: c.type,
        mode: c.mode,
        min: c.min === undefined ? '' : String(c.min),
        max: c.max === undefined ? '' : String(c.max),
        unit: c.unit || '',
        values: c.values || [],
        accepted: true, // what is in project.json is already defined
    }));
}

const slug = (text) => String(text).trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'criterion';

const parseNumber = (text) => {
    const trimmed = String(text ?? '').trim().replace(',', '.');
    const value = trimmed === '' ? NaN : Number(trimmed);
    return Number.isNaN(value) ? undefined : value;
};

/** A row the validator can use; incomplete rows are not saved. */
export function isComplete(row) {
    if (!String(row.label || '').trim()) return false;
    if (row.type === 'numeric') return parseNumber(row.min) !== undefined || parseNumber(row.max) !== undefined;
    return (row.values || []).some((v) => String(v).trim());
}

/** Rows -> Eligibility.Criteria; incomplete rows are dropped, ids stay stable. */
export function criteriaFromRows(rows) {
    const used = new Set(rows.map((r) => r.id).filter(Boolean));
    const out = [];
    for (const row of rows) {
        if (!row.accepted || !isComplete(row)) continue;
        const { id: _id, label: _label, term: _term, type: _type, mode: _mode, min: _min, max: _max, unit: _unit, values: _values, accepted: _accepted, ...extra } = row;
        const label = String(row.label).trim();
        const criterion = { ...extra, label, term: row.term ?? null, type: row.type, mode: row.mode };
        if (row.type === 'numeric') {
            const min = parseNumber(row.min);
            const max = parseNumber(row.max);
            if (min !== undefined) criterion.min = min;
            if (max !== undefined) criterion.max = max;
            if (String(row.unit || '').trim()) criterion.unit = String(row.unit).trim();
        } else {
            criterion.values = (row.values || []).map((v) => String(v).trim()).filter(Boolean);
        }
        let id = row.id;
        if (!id) {
            const base = slug(label);
            id = base;
            for (let n = 2; used.has(id); n += 1) id = `${base}-${n}`;
            used.add(id);
            row.id = id; // stays with the row: a later rename must not change the id links point at
        }
        out.push({ id, ...criterion });
    }
    return out;
}

// ---- DOM (thin): keeps the rows in memory, renders them, reads them back ----
let rows = [];
let listEl = null;

export const getEligibilityCriteria = () => criteriaFromRows(rows);

/** Accepted criteria of one mode ("include"/"exclude"); counts towards the Core fields. */
export const checkedCriteriaCount = (mode) => getEligibilityCriteria().filter((c) => c.mode === mode).length;

export function setEligibilityCriteria(criteria) {
    rows = rowsFromCriteria(criteria);
    render();
}

const hintText = (row) => (isComplete(row)
    ? 'click the check mark to add this criterion'
    : `${row.accepted ? 'not saved' : 'to add it'}: ${row.type === 'numeric' ? 'enter a min or max' : 'choose at least one value'}${row.label ? '' : ' and a name'}`);
// An accepted, complete row needs no hint; a draft always says what it still needs.
const hintHidden = (row) => row.accepted && isComplete(row);

function rowHtml(row, i) {
    const info = termInfo(row.term);
    const name = row.term
        ? `<strong>${escapeHtml(row.label)}</strong>`
        : `<input class="form-control form-control-sm w-auto" data-f="label" placeholder="Name (e.g. IQ)" value="${escapeHtml(row.label)}">`;
    const mode = ['include', 'exclude'].map((m) => `<option value="${m}"${row.mode === m ? ' selected' : ''}>${m}</option>`).join('');
    let limits;
    if (row.type === 'numeric') {
        limits = `<input class="form-control form-control-sm w-auto" style="width: 6.5rem !important" data-f="min" placeholder="min" value="${escapeHtml(row.min)}">
            <input class="form-control form-control-sm w-auto" style="width: 6.5rem !important" data-f="max" placeholder="max" value="${escapeHtml(row.max)}">
            <input class="form-control form-control-sm w-auto" style="width: 6.5rem !important" data-f="unit" placeholder="unit" value="${escapeHtml(row.unit)}">`;
    } else if (info.values) {
        limits = info.values.map((v) => `<label class="form-check-label small me-2"><input type="checkbox" class="form-check-input" data-f="value" value="${escapeHtml(v)}"${row.values.includes(v) ? ' checked' : ''}> ${escapeHtml(v)}</label>`).join('');
    } else {
        limits = `<input class="form-control form-control-sm w-auto" data-f="values" placeholder="labels, comma separated" value="${escapeHtml(row.values.join(', '))}">`;
    }
    return `<div class="d-flex flex-wrap gap-2 align-items-center" data-i="${i}">${name}
        <select class="form-select form-select-sm w-auto" data-f="mode">${mode}</select>${limits}
        <small class="text-warning" data-f="hint"${hintHidden(row) ? ' hidden' : ''}>${hintText(row)}</small>
        ${row.accepted
        ? '<button type="button" class="btn btn-outline-danger btn-sm" data-f="remove" aria-label="Delete criterion" title="Delete criterion"><i class="fas fa-times"></i></button>'
        : `<button type="button" class="btn btn-outline-success btn-sm" data-f="accept" aria-label="Accept criterion" title="Accept criterion"${isComplete(row) ? '' : ' disabled'}><i class="fas fa-check"></i></button>
        <button type="button" class="btn btn-outline-secondary btn-sm" data-f="cancel" title="Discard this draft">Cancel</button>`}</div>`;
}

function render() {
    if (listEl) listEl.innerHTML = rows.map(rowHtml).join('');
}

export function initEligibilityCriteria({ list, select, addButton, onChange = () => {} }) {
    if (!list || !select || !addButton) return; // page without the Eligibility form
    listEl = list;
    select.innerHTML = TERMS.map((t) => `<option value="${t.term ?? ''}">${escapeHtml(t.label)}</option>`).join('');
    addButton.addEventListener('click', () => {
        rows.push(newRow(select.value || null));
        render();
        onChange();
    });
    const rowOf = (el) => rows[Number(el.closest('[data-i]').dataset.i)];
    list.addEventListener('input', (event) => {
        const f = event.target.dataset.f;
        const row = rowOf(event.target);
        if (f === 'value') row.values = [...list.querySelectorAll(`[data-i="${rows.indexOf(row)}"] [data-f="value"]:checked`)].map((c) => c.value);
        else if (f === 'values') row.values = event.target.value.split(',');
        else if (f) row[f] = event.target.value;
        const rowEl = event.target.closest('[data-i]');
        const hint = rowEl.querySelector('[data-f="hint"]');
        if (hint) {
            hint.hidden = hintHidden(row);
            hint.textContent = hintText(row);
        }
        const accept = rowEl.querySelector('[data-f="accept"]');
        if (accept) accept.disabled = !isComplete(row);
        onChange();
    });
    list.addEventListener('click', (event) => {
        const button = event.target.closest('[data-f="remove"], [data-f="cancel"], [data-f="accept"]');
        if (!button) return;
        const i = Number(button.closest('[data-i]').dataset.i);
        if (button.dataset.f === 'accept') rows[i].accepted = true;
        else rows.splice(i, 1);
        render();
        onChange();
    });
    render();
}
