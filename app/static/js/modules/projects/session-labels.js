/**
 * Time or content: what the sessions of a project with several timepoints are.
 * The Projects page asks it only for `multiple`, and a NEW project must answer;
 * what each answer does is decided by the backend (src.session_order).
 */

export const SESSION_LABELS_MISSING_LABEL = 'Session labels (time or content)';

export function sessionLabelsVisible(timepoints) {
    return timepoints === 'multiple';
}

export function sessionLabelsMissing(timepoints, sessionLabels) {
    return sessionLabelsVisible(timepoints) && !sessionLabels;
}

/** Show the question next to Timepoints only when it applies. */
export function syncSessionLabelsField() {
    const group = document.getElementById('smSDSessionLabelsGroup');
    if (!group) return;
    group.classList.toggle('d-none', !sessionLabelsVisible(document.getElementById('smSDTimepoints')?.value));
}
