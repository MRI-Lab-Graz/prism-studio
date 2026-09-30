/**
 * Wording of the "Delete Files" confirmation. The previewed list is on screen, but the
 * question itself must say how much is about to go, and say it loudly when the selection
 * is effectively the whole project (every subject ticked, no modality or filter).
 */

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

export function deleteConfirmMessage({ count, sidecars = 0, everything = false }) {
    const files = plural(count, 'file');
    const extra = sidecars > 0 ? ` (and ${plural(sidecars, 'orphaned sidecar')})` : '';
    if (everything) {
        return (
            `All subjects are selected and there is no modality or filter, so this will permanently delete EVERY file `
            + `in the project (${files}${extra}). This action cannot be undone. Continue?`
        );
    }
    return `Permanently delete ${files}${extra} from this project? This action cannot be undone.`;
}
