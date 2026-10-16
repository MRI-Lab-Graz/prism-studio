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

/** Mounts the input row and the chip area into `container`; returns { getValues, setValues }. */
export function mountChipList(container, { placeholder = '', onChange = () => {} } = {}) {
    container.innerHTML = `
        <div class="input-group input-group-sm chip-input-row">
            <input type="text" class="form-control chip-input" placeholder="${escapeHtml(placeholder)}">
            <button type="button" class="btn btn-outline-secondary btn-sm" data-f="accept" disabled
                    aria-label="Add entry" title="Add entry"><i class="fas fa-check"></i></button>
        </div>
        <div class="d-flex flex-wrap gap-1 chip-badges"></div>`;
    const inputRow = container.querySelector('.chip-input-row');
    const input = container.querySelector('.chip-input');
    const accept = container.querySelector('[data-f="accept"]');
    const badges = container.querySelector('.chip-badges');
    let values = [];

    const renderChips = () => {
        badges.innerHTML = '';
        values.forEach((value) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1 chip-badge';
            chip.title = `Remove: ${value}`;
            chip.setAttribute('aria-label', `Remove ${value}`);
            chip.innerHTML = `${escapeHtml(value)} <span aria-hidden="true">&times;</span>`;
            chip.addEventListener('click', () => {
                values = removeChip(values, value);
                renderChips();
                onChange(values);
            });
            badges.appendChild(chip);
        });
    };

    const syncAccept = () => syncAcceptButton(accept, normalizeChipText(input.value) !== '');
    const acceptEntry = () => {
        values = addChip(values, input.value);
        input.value = '';
        syncAccept();
        renderChips();
        onChange(values);
    };

    input.addEventListener('input', () => {
        syncAccept();
        inputRow.classList.remove('row-pending');
    });
    input.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        acceptEntry();
    });
    accept.addEventListener('mousedown', (event) => event.preventDefault());
    accept.addEventListener('click', acceptEntry);
    registerStagedControl(inputRow, () => normalizeChipText(input.value) !== '');

    return {
        getValues: () => values,
        setValues(next) {
            values = [];
            (next || []).forEach((value) => { values = addChip(values, value); });
            input.value = '';
            syncAccept();
            renderChips();
        },
    };
}
