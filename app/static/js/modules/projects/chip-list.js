/** A list field as one input plus green chips (the look of the CRediT roles).
 *
 * Type, press Enter or click the check: the entry becomes a chip below the input and
 * the input is ready for the next one. Clicking a chip removes it. Text typed but not
 * accepted is a staged control, so saving is blocked meanwhile (see row-state.js).
 * Pure list logic first (unit tested), thin DOM after.
 */
import { escapeHtml } from '../../shared/dom.js';
import { registerStagedControl, syncAcceptButton } from './row-state.js';

export const normalizeChipText = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();

/** New list with `text` appended; empty text and duplicates (any case) change nothing. */
export function addChip(values, text) {
    const entry = normalizeChipText(text);
    if (!entry || values.some((v) => v.toLowerCase() === entry.toLowerCase())) return values;
    return [...values, entry];
}

export const removeChip = (values, text) => values.filter((v) => v !== text);

/** Mounts an entry row and the chip area into `container`; returns { getValues, setValues, addValue }.
 *  Default: one text input. For structured entries pass `fields` (input/select elements the
 *  caller built), `compose(values) -> string` (the stored string, '' = incomplete) and
 *  `chipText(storedString) -> string` (what the chip shows). */
export function mountChipList(container, {
    placeholder = '',
    fields = null,
    compose = ([text]) => normalizeChipText(text),
    chipText = (value) => value,
    onChange = () => {},
} = {}) {
    container.innerHTML = `
        <div class="input-group input-group-sm chip-input-row">
            <button type="button" class="btn btn-outline-secondary btn-sm" data-f="accept" disabled
                    aria-label="Add entry" title="Add entry"><i class="fas fa-check"></i></button>
        </div>
        <div class="d-flex flex-wrap gap-1 chip-badges"></div>`;
    const inputRow = container.querySelector('.chip-input-row');
    const accept = container.querySelector('[data-f="accept"]');
    const badges = container.querySelector('.chip-badges');
    const entryFields = fields || [Object.assign(document.createElement('input'), {
        type: 'text', className: 'form-control chip-input', placeholder,
    })];
    entryFields.forEach((field) => {
        field.classList.add('chip-input');
        inputRow.insertBefore(field, accept);
    });
    let values = [];

    const readFields = () => entryFields.map((field) => field.value);
    const hasContent = () => readFields().some((value) => normalizeChipText(value) !== '');

    const renderChips = () => {
        badges.innerHTML = '';
        values.forEach((value) => {
            const text = chipText(value);
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1 chip-badge';
            chip.title = `Remove: ${text}`;
            chip.setAttribute('aria-label', `Remove ${text}`);
            chip.innerHTML = `${escapeHtml(text)} <span aria-hidden="true">&times;</span>`;
            chip.addEventListener('click', () => {
                values = removeChip(values, value);
                renderChips();
                onChange(values);
            });
            badges.appendChild(chip);
        });
    };

    const syncAccept = () => syncAcceptButton(accept, compose(readFields()) !== '');
    const addValue = (value) => {
        const next = addChip(values, value);
        if (next === values) return false;
        values = next;
        renderChips();
        onChange(values);
        return true;
    };
    const clearFields = () => {
        entryFields.forEach((field) => { field.value = ''; });
        syncAccept();
    };
    const acceptEntry = () => {
        const entry = compose(readFields());
        if (!entry) return;
        addValue(entry);
        clearFields();
    };

    entryFields.forEach((field) => {
        const onEdit = () => {
            syncAccept();
            inputRow.classList.remove('row-pending');
        };
        field.addEventListener('input', onEdit);
        field.addEventListener('change', onEdit);
        if (field.tagName === 'INPUT') {
            field.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter') return;
                event.preventDefault();
                acceptEntry();
            });
        }
    });
    accept.addEventListener('mousedown', (event) => event.preventDefault());
    accept.addEventListener('click', acceptEntry);
    registerStagedControl(inputRow, hasContent);

    return {
        getValues: () => values,
        addValue,
        setValues(next) {
            values = [];
            (next || []).forEach((value) => { values = addChip(values, value); });
            clearFields();
            renderChips();
        },
    };
}
