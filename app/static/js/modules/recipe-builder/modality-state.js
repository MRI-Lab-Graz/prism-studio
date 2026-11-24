// What the modality picker and the template list say about the project's modality list.
// `modalities` is the list from the backend, or null when the request failed.
export function modalityListState(modalities) {
    if (modalities === null) return { text: '— failed to load modalities —', disabled: true };
    if (modalities.length === 0) {
        return { text: '— no survey or biometrics data or templates in this project —', disabled: true };
    }
    return { text: '', disabled: false };
}
