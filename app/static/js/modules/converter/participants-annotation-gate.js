/**
 * Annotation is a required stage before Create/Replace. The user explicitly
 * confirms it (we do not judge what counts as "annotated"); any new preview,
 * file or column change resets the confirmation so a stale one cannot be used.
 */
export function createAnnotationGate() {
    let confirmed = false;
    return {
        confirm() { confirmed = true; },
        reset() { confirmed = false; },
        isConfirmed() { return confirmed; },
    };
}
