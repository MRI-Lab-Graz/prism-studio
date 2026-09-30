/**
 * Session mapping panel: lists source session labels next to EMPTY inputs.
 * Nothing is suggested or pre-filled; the user types every session name.
 */

export function validSessionName(text) {
    return /^[A-Za-z0-9]+$/.test(String(text ?? '').trim());
}

/** A blank source label ('') has no name to map; the fix belongs in the data file. */
const mappable = (labels) => labels.filter((label) => label !== '');

export function canSaveSessionMap(labels, typed) {
    const toMap = mappable(labels);
    return toMap.length > 0 && toMap.every((label) => validSessionName(typed[label]));
}

/** Only what the user actually typed (trimmed, non-empty), never for a blank label. */
export function entriesToSave(labels, typed) {
    const entries = {};
    for (const label of mappable(labels)) {
        const value = String(typed[label] ?? '').trim();
        if (value) entries[label] = value;
    }
    return entries;
}

/**
 * Thin DOM wrapper. `root` holds #sessionMapRows, #sessionMapSaveBtn, #sessionMapStatus.
 * `save(entries)` POSTs to /api/session-map and resolves on success; `onSaved()` re-runs detection.
 */
export function createSessionMapPanel({ root, save, onSaved, onChange }) {
    const rows = root.querySelector('#sessionMapRows');
    const saveBtn = root.querySelector('#sessionMapSaveBtn');
    const status = root.querySelector('#sessionMapStatus');
    let labels = [];
    const typed = {};

    function refresh() {
        saveBtn.disabled = !canSaveSessionMap(labels, typed);
        if (onChange) onChange();
    }

    function show(unmapped) {
        labels = unmapped.slice();
        rows.replaceChildren(
            ...labels.map((label) => {
                if (label === '') {
                    const note = document.createElement('div');
                    note.className = 'small text-danger mb-1';
                    note.textContent = 'Some rows have no session value. Fill in the session column in your file; a blank cannot be mapped.';
                    return note;
                }
                const group = document.createElement('div');
                group.className = 'input-group input-group-sm mb-1';
                const name = document.createElement('span');
                name.className = 'input-group-text';
                name.textContent = label === '' ? '(empty)' : label;
                const input = document.createElement('input');
                input.className = 'form-control';
                input.placeholder = 'session name (letters and digits)';
                input.setAttribute('aria-label', `Session name for ${label === '' ? 'empty label' : label}`);
                input.addEventListener('input', () => {
                    typed[label] = input.value;
                    refresh();
                });
                group.append(name, input);
                return group;
            })
        );
        status.textContent = '';
        root.classList.remove('d-none');
        refresh();
    }

    function hide() {
        labels = [];
        root.classList.add('d-none');
        if (onChange) onChange();
    }

    saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        try {
            await save(entriesToSave(labels, typed));
            status.textContent = 'Saved.';
            if (onSaved) await onSaved();
        } catch (error) {
            status.textContent = error.message || 'Could not save the session map.';
            refresh();
        }
    });

    return { show, hide, isPending: () => labels.length > 0 };
}
