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
 * Groups of digit-only labels that differ only by leading zeros ('1', '01', '001').
 * They are different labels and stay different; this only lets the panel point it out.
 */
export function numericTwinLabels(labels) {
    const groups = new Map();
    for (const label of labels) {
        if (!/^\d+$/.test(label)) continue;
        const key = String(BigInt(label));
        groups.set(key, [...(groups.get(key) ?? []), label]);
    }
    return [...groups.values()].filter((group) => group.length > 1);
}

/**
 * Thin DOM wrapper. `root` holds elements with data-role="rows" | "save" | "status".
 * `save(entries)` POSTs to /api/session-map and resolves on success; `onSaved()` re-runs detection.
 */
export function createSessionMapPanel({ root, save, onSaved, onChange }) {
    const rows = root.querySelector('[data-role="rows"]');
    const saveBtn = root.querySelector('[data-role="save"]');
    const status = root.querySelector('[data-role="status"]');
    let labels = [];
    const typed = {};

    function refresh() {
        saveBtn.disabled = !canSaveSessionMap(labels, typed);
        if (onChange) onChange();
    }

    function show(unmapped) {
        labels = unmapped.slice();
        // Only what is visible may count toward Save: drop names of labels no longer listed.
        for (const key of Object.keys(typed)) {
            if (!labels.includes(key)) delete typed[key];
        }
        const warnings = numericTwinLabels(labels).map((group) => {
            const note = document.createElement('div');
            note.className = 'small text-warning mb-1';
            note.textContent = `${group.map((label) => `'${label}'`).join(', ')} are different session labels. Map each one yourself; PRISM does not treat them as the same.`;
            return note;
        });
        rows.replaceChildren(
            ...warnings,
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
                input.value = typed[label] ?? '';
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
