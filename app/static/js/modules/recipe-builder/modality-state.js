// What the modality picker and the template list say about the project's modality list.
// `modalities` is the list from the backend, or null when the request failed.
export function modalityListState(modalities, hasProject) {
    if (!hasProject) return { text: '— no project loaded —', disabled: true };
    if (modalities === null) return { text: '— failed to load modalities —', disabled: true };
    if (modalities.length === 0) return { text: '— no modalities (data or templates) in this project —', disabled: true };
    return { text: '', disabled: false };
}

// The picker's options: the project's modalities, plus the one a recipe carries when the project has none of it.
export function modalityOptions(modalities, carried) {
    if (!carried || modalities.some(m => m.value === carried)) return modalities;
    return [...modalities, { value: carried, label: carried + ' (not in this project)' }];
}
