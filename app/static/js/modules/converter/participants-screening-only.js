/** Merge step: which participants of the source file are screening-only.
 *
 * Ticked ids stay in participants.tsv and get group "screening-only" (the backend does the
 * writing). By default everyone without a sub-folder is ticked. Pure helpers, no DOM state.
 */
import { escapeHtml } from '../../shared/dom.js';

export const SCREENING_GROUP = 'screening-only';

export const defaultScreeningTicks = (candidates) =>
    new Set(candidates.filter((row) => !row.has_folder).map((row) => row.participant_id));

/** Only worth asking when someone has no folder yet or is marked from an earlier run. */
export const needsScreeningChoice = (candidates) =>
    candidates.some((row) => !row.has_folder || String(row.group).toLowerCase() === SCREENING_GROUP);

export function screeningRowsHtml(candidates, ticked) {
    return candidates.map((row) => {
        const id = escapeHtml(row.participant_id);
        const group = row.group ? escapeHtml(row.group) : '<span class="text-muted">-</span>';
        const folder = row.has_folder ? 'yes' : '<span class="text-warning">no</span>';
        return `<tr><td><input type="checkbox" class="form-check-input" data-screening-id="${id}"`
            + `${ticked.has(row.participant_id) ? ' checked' : ''}></td>`
            + `<td>${id}</td><td>${folder}</td><td>${group}</td></tr>`;
    }).join('');
}

/** `ticked` null = no choice was offered: send nothing and the group column stays as it is. */
export function appendScreeningOnlyIds(formData, ticked) {
    if (ticked) formData.append('screening_only_ids', JSON.stringify([...ticked]));
}
