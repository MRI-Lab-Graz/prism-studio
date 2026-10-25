/** One behaviour for add-a-row controls on the Projects page.
 *
 * A new row is a draft (green check, Cancel); accepting it makes it defined (red
 * cross = delete). Saving is blocked while a draft with content is pending.
 * A row element carries `dataset.rowState` and `el._row = { hasContent(), discard() }`.
 * Pure model first (unit tested in node), thin DOM helpers after.
 */

export function rowActionsModel({ state, complete }) {
    const draft = state === 'draft';
    return {
        accept: { visible: draft, disabled: draft && !complete },
        cancel: { visible: draft },
        remove: { visible: !draft },
    };
}

const escapeText = (text) => String(text).replace(/[&<>"']/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

/** Buttons for a row's action slot; `noun` makes the delete label specific ("author").
 *  `hint` says why the check is disabled; it is shown only while it is. */
export function rowActionsHtml(model, noun = '', hint = '') {
    const label = (verb) => `${verb}${noun ? ` ${noun}` : ''}`;
    const out = [];
    if (hint && model.accept.visible && model.accept.disabled) {
        out.push(`<small class="text-warning order-last w-100" data-f="hint">${escapeText(hint)}</small>`);
    }
    if (model.accept.visible) {
        // Gray while nothing (or not enough) is set, green once the row can be accepted.
        const colour = model.accept.disabled ? 'btn-outline-secondary' : 'btn-success';
        out.push(`<button type="button" class="btn ${colour} btn-sm" data-f="accept" aria-label="${label('Accept')}" title="${label('Accept')}"${model.accept.disabled ? ' disabled' : ''}><i class="fas fa-check"></i></button>`);
    }
    if (model.cancel.visible) {
        out.push('<button type="button" class="btn btn-outline-secondary btn-sm" data-f="cancel" title="Discard this draft">Cancel</button>');
    }
    if (model.remove.visible) {
        out.push(`<button type="button" class="btn btn-outline-danger btn-sm" data-f="remove" aria-label="${label('Delete')}" title="${label('Delete')}"><i class="fas fa-times"></i></button>`);
    }
    return out.join('');
}

/** Update an existing check button in place (disabled + gray, or enabled + green). */
export function syncAcceptButton(button, complete) {
    if (!button) return;
    button.disabled = !complete;
    button.classList.remove(complete ? 'btn-outline-secondary' : 'btn-success');
    button.classList.add(complete ? 'btn-success' : 'btn-outline-secondary');
}

export const isPending = ({ state, hasContent }) => state === 'draft' && Boolean(hasContent);

export function pendingMessage(count) {
    const entries = count === 1 ? '1 entry is' : `${count} entries are`;
    return `${entries} not accepted yet. Accept each with its green check, or discard it (Cancel, or clear the text), then save again.`;
}

/** One delegated click handler for a slot holding rowActionsHtml buttons. */
export function bindRowActions(slot, { onAccept, onCancel, onRemove }) {
    // Keep the focus where it is: a blur re-render could swallow the click (Chromium).
    slot.addEventListener('mousedown', (event) => {
        if (event.target.closest('[data-f]')) event.preventDefault();
    });
    slot.addEventListener('click', (event) => {
        const button = event.target.closest('[data-f]');
        if (!button || !slot.contains(button) || button.disabled) return;
        const row = slot.closest('[data-row-state]');
        if (row) row.classList.remove('row-pending');
        const handler = { accept: onAccept, cancel: onCancel, remove: onRemove }[button.dataset.f];
        if (handler) handler();
    });
}

const drafts = (form) => [...form.querySelectorAll('[data-row-state="draft"]')].filter((el) => el._row);

// Controls that are not rows but also lose what was typed without a click (a search
// picker with its own Add button): registered once, pending while they hold something.
const staged = [];
export function registerStagedControl(el, hasContent) {
    staged.push({ el, hasContent });
}

/** Draft rows and staged controls that hold something the user typed or chose. */
export function findPending(form) {
    const rows = drafts(form).filter((el) => isPending({ state: 'draft', hasContent: el._row.hasContent() }));
    const pickers = staged.filter((s) => form.contains(s.el) && s.hasContent()).map((s) => s.el);
    return [...rows, ...pickers];
}

/** An empty draft holds nothing to lose: drop it instead of blocking. */
export function discardEmptyDrafts(form) {
    drafts(form).filter((el) => !el._row.hasContent()).forEach((el) => el._row.discard());
}

/** true = the form may be saved. Otherwise the pending rows are marked and the user told what to do. */
export function guardSave(form, showFeedback) {
    form.querySelectorAll('.row-pending').forEach((el) => el.classList.remove('row-pending'));
    discardEmptyDrafts(form);
    const pending = findPending(form);
    if (!pending.length) return true;
    pending.forEach((el) => el.classList.add('row-pending'));
    showFeedback(pendingMessage(pending.length), 'warning'); // scrolls to the top ...
    pending[0].scrollIntoView?.({ block: 'center', behavior: 'smooth' }); // ... the row is what the user must act on
    return false;
}

/** Gives a row its action buttons and the row contract. Returns { slot, refresh }:
 *  append `slot` to the row, call `refresh()` whenever completeness may have changed.
 *  `state` is the initial state: 'draft' for rows the user adds, 'defined' for loaded rows. */
export function mountRowActions(row, { state, noun, incompleteHint, isComplete, hasContent, onAccept, onRemove }) {
    const slot = document.createElement('span');
    slot.style.display = 'contents'; // the buttons stay direct layout children of an input-group
    row.dataset.rowState = state;
    const refresh = () => {
        slot.innerHTML = rowActionsHtml(
            rowActionsModel({ state: row.dataset.rowState, complete: isComplete() }), noun, incompleteHint);
    };
    row._row = { hasContent, discard: onRemove, refresh }; // refresh: for code that fills fields without an input event
    bindRowActions(slot, {
        onAccept: () => {
            row.dataset.rowState = 'defined';
            refresh();
            onAccept();
        },
        onCancel: onRemove,
        onRemove,
    });
    refresh();
    return { slot, refresh };
}
