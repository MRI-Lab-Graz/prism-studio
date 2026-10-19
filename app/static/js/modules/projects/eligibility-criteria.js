/** Structured eligibility criteria (Study Metadata > Eligibility).
 *
 * Stored in project.json as Eligibility.Criteria; the validator checks
 * participants.tsv against them (warnings only). Term list: NeuroBagel terms
 * plus "Other measure" for anything without a standard (IQ, VO2max, ...).
 */
import { escapeHtml } from '../../shared/dom.js';
import { mountChipArea } from './chip-list.js';
import { criterionSummary } from './chip-summaries.js';
import { rowActionsHtml, rowActionsModel, syncAcceptButton } from './row-state.js';

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
    const rows = (criteria || []).map((c) => ({
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
    }));
    // What is in project.json and complete is accepted (a chip); an incomplete one comes back
    // as a draft so it can be fixed instead of being dropped.
    return rows.map((row) => (isComplete(row) ? { ...row, accepted: true } : { ...row, accepted: false, loaded: true }));
}

const slug = (text) => String(text).trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'criterion';

const parseNumber = (text) => {
    const trimmed = String(text ?? '').trim().replace(',', '.');
    const value = trimmed === '' ? NaN : Number(trimmed);
    return Number.isNaN(value) ? undefined : value;
};

/** Something the user typed or chose (defaults such as Age's unit do not count). */
export function hasContent(row) {
    return Boolean(row.loaded // an incomplete criterion from project.json: the user has not seen it fixed yet
        || String(row.min ?? '').trim() || String(row.max ?? '').trim()
        || (row.values || []).some((v) => String(v).trim())
        || (!row.term && String(row.label || '').trim()));
}

/** A row the validator can use; incomplete rows are not saved. */
export function isComplete(row) {
    if (!String(row.label || '').trim()) return false;
    if (row.type === 'numeric') {
        const [lo, hi] = [parseNumber(row.min), parseNumber(row.max)];
        return (lo !== undefined || hi !== undefined) && !(lo > hi); // min above max flags everyone
    }
    return (row.values || []).some((v) => String(v).trim());
}

/** What makes two criteria "the same" when one is removed and another added: term and name. */
export const criterionKey = (row) => `${row.term ?? ''}|${String(row.label || '').trim().toLowerCase()}`;

/** Remember the ids of removed criteria, so adding the same criterion again gets its id back
 *  (a participants.json link points at the id, which may be hand-written). */
export function rememberRemoved(removedRows, remembered) {
    removedRows.filter((row) => row.id).forEach((row) => {
        const key = criterionKey(row);
        remembered.set(key, [...(remembered.get(key) || []), row.id]);
    });
}

/** Rows -> Eligibility.Criteria; incomplete rows are dropped, ids stay stable.
 *  `remembered` (see rememberRemoved) hands removed ids back to the same criterion. */
export function criteriaFromRows(rows, remembered = new Map()) {
    const used = new Set(rows.map((r) => r.id).filter(Boolean));
    const out = [];
    for (const row of rows) {
        if (!row.accepted || !isComplete(row)) continue;
        const { id: _id, label: _label, term: _term, type: _type, mode: _mode, min: _min, max: _max, unit: _unit, values: _values, accepted: _accepted, loaded: _loaded, ...extra } = row;
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
            const stack = remembered.get(criterionKey(row)) || [];
            const back = stack.find((candidate) => !used.has(candidate));
            if (back) {
                stack.splice(stack.indexOf(back), 1);
                id = back;
            } else {
                const base = slug(label);
                id = base;
                for (let n = 2; used.has(id); n += 1) id = `${base}-${n}`;
            }
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

const removedIds = new Map(); // per loaded project: criterion key -> ids of removed criteria

export const getEligibilityCriteria = () => criteriaFromRows(rows, removedIds);

/** Accepted criteria of one mode ("include"/"exclude"); counts towards the Core fields. */
export const checkedCriteriaCount = (mode) => getEligibilityCriteria().filter((c) => c.mode === mode).length;

export function setEligibilityCriteria(criteria) {
    removedIds.clear(); // a different project: its removed criteria are not ours
    rows = rowsFromCriteria(criteria);
    render();
}

const hintText = (row) => (isComplete(row)
    ? 'click the check mark to add this criterion'
    : `${row.accepted ? 'not saved' : 'to add it'}: ${row.type === 'numeric' ? 'enter a min or max (min must not exceed max)' : 'choose at least one value'}${row.label ? '' : ' and a name'}`);
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
        ${rowActionsHtml(rowActionsModel({ state: row.accepted ? 'defined' : 'draft', complete: isComplete(row) }), 'criterion')}</div>`;
}

let notify = () => {};

function render() {
    if (!listEl) return;
    // Entry rows (drafts) first, accepted criteria as green chips below them.
    listEl.innerHTML = rows.map((row, i) => (row.accepted ? '' : rowHtml(row, i))).join('')
        + '<div class="criteria-chips"></div>';
    const accepted = getEligibilityCriteria(); // also gives every accepted row its stable id
    // Chips are keyed by position, not by id: an id may hold spaces, differ only by case, ...
    const area = mountChipArea(listEl.querySelector('.criteria-chips'), {
        chipText: (key) => criterionSummary(accepted[Number(key)]),
        onChange: (keys) => {
            const keep = new Set(keys.map(Number));
            let position = -1;
            const dropped = [];
            rows = rows.filter((row) => {
                if (!row.accepted) return true;
                position += 1;
                if (keep.has(position)) return true;
                dropped.push(row);
                return false;
            });
            rememberRemoved(dropped, removedIds);
            render(); // the draft rows are addressed by index
            notify();
        },
    });
    area.setValues(accepted.map((_, position) => String(position)));
    // Row contract of row-state.js: the save guard asks each draft whether it holds content.
    listEl.querySelectorAll('[data-i]').forEach((el) => {
        const row = rows[Number(el.dataset.i)];
        el.dataset.rowState = 'draft';
        el._row = {
            hasContent: () => hasContent(row),
            discard: () => { rows.splice(rows.indexOf(row), 1); render(); notify(); },
        };
    });
}

export function initEligibilityCriteria({ list, select, addButton, onChange = () => {} }) {
    if (!list || !select || !addButton) return; // page without the Eligibility form
    listEl = list;
    notify = onChange;
    // "other" stands for the term-less "Other measure"; '' is the placeholder.
    select.innerHTML = '<option value="">Add variable…</option>'
        + TERMS.map((t) => `<option value="${t.term ?? 'other'}">${escapeHtml(t.label)}</option>`).join('');
    const syncAddButton = () => { addButton.disabled = !select.value; };
    select.addEventListener('change', syncAddButton);
    syncAddButton();
    addButton.addEventListener('click', () => {
        if (!select.value) return;
        rows.push(newRow(select.value === 'other' ? null : select.value));
        select.value = ''; // back to the placeholder: the last choice must not look like a default
        syncAddButton();
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
        syncAcceptButton(accept, isComplete(row));
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
