/**
 * Time or content: what the sessions of a project with several timepoints are.
 * The Projects page asks it only for `multiple`, and a NEW project must answer;
 * what each answer does is decided by the backend (src.session_order).
 */

export const SESSION_LABELS_INFO = 'Time: sessions are waves in the same order for everyone (ses-1, ses-2 or pre/post). '
    + 'Content: sessions are conditions whose order differs per participant (e.g. sleepdep / rested in '
    + "counterbalanced order); you then provide each participant's order, and the folders are named after "
    + 'the condition (ses-rested, not ses-2).';

export const SESSION_LABELS_MISSING_LABEL = 'Session labels (time or content)';

export function sessionLabelsVisible(timepoints) {
    return timepoints === 'multiple';
}

export function sessionLabelsMissing(timepoints, sessionLabels) {
    return sessionLabelsVisible(timepoints) && !sessionLabels;
}

/** Show the question next to Timepoints only when it applies; fill the explanation once. */
export function syncSessionLabelsField() {
    const group = document.getElementById('smSDSessionLabelsGroup');
    if (!group) return;
    group.classList.toggle('d-none', !sessionLabelsVisible(document.getElementById('smSDTimepoints')?.value));
    const info = document.getElementById('smSDSessionLabelsInfo');
    if (info && !info.textContent) info.textContent = SESSION_LABELS_INFO;
}
