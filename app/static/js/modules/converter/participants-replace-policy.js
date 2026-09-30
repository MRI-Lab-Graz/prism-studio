/**
 * Replace means "the imported file becomes the new source of truth": the
 * current participants.tsv/.json are fully replaced, annotations included.
 * Modify and Merge keep the existing annotations. Without a participants.tsv
 * there is nothing to replace, so a draft schema saved earlier is still used.
 */

export const REPLACE_CONFIRMATION_MESSAGE =
    'Replace discards the existing participants.tsv and participants.json, '
    + 'including all annotations (NeuroBagel terms, descriptions and value labels). '
    + 'Continue?';

export function discardsExistingSchema({ mode, fileAction, hasParticipantsTsv }) {
    return mode === 'file' && fileAction === 'replace' && Boolean(hasParticipantsTsv);
}

/**
 * Which workflow card counts as selected. When the project already has
 * participant files the user must pick Replace, Modify or Merge: the built-in
 * default ('1') is not a choice, so it must not suppress the Replace
 * confirmation by looking "already selected".
 */
export function effectiveSelectedCase({
    requiresSelection,
    availableCases,
    selectedCaseId,
    chosenCaseId,
}) {
    if (!requiresSelection) return selectedCaseId;
    const isChosen = Boolean(chosenCaseId) && selectedCaseId === chosenCaseId;
    return isChosen && availableCases.includes(selectedCaseId) ? selectedCaseId : null;
}
