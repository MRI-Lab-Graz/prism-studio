/**
 * Decision state for longitudinal source files in the Sociodemographics
 * converter. participants.tsv has one row per participant, so when the file
 * holds several sessions the user says whether it is longitudinal and, if so,
 * picks the session column and ONE session for everybody.
 *
 * Session labels are free-form strings: never rewritten here ("1" != "01").
 * `candidates` is the backend's session_candidates: [{ column, values }].
 */

export function createSessionChoiceState() {
    return { longitudinal: null, column: '', session: '' };
}

export function setSessionChoiceLongitudinal(state, isLongitudinal, candidates) {
    if (!isLongitudinal) {
        return { longitudinal: false, column: '', session: '' };
    }
    const onlyColumn = candidates.length === 1 ? candidates[0].column : '';
    return { longitudinal: true, column: onlyColumn, session: '' };
}

export function setSessionChoiceColumn(state, column, candidates) {
    const known = candidates.find((candidate) => candidate.column === column);
    const keepSession = known && known.values.includes(state.session);
    return { ...state, column, session: keepSession ? state.session : '' };
}

export function setSessionChoiceSession(state, session) {
    return { ...state, session };
}

/** Why the user cannot continue yet ('' when nothing blocks). */
export function sessionChoiceBlockReason(candidates, state) {
    if (!candidates || candidates.length === 0) return '';
    if (state.longitudinal === null) {
        return 'This file contains several sessions. Please say whether it is a longitudinal dataset.';
    }
    if (state.longitudinal === false) return '';
    if (!state.column) return 'Please select the session column.';
    if (!state.session) return 'Please select the one session to import into participants.tsv.';
    return '';
}

/**
 * Same as sessionChoiceBlockReason, but only for the route that writes one row
 * per participant from the file (not the merge route, not editing the existing file).
 */
export function sessionChoiceBlockReasonForRoute({ mode, useMergeRoute }, candidates, state) {
    return mode === 'file' && !useMergeRoute ? sessionChoiceBlockReason(candidates, state) : '';
}

/** Form fields to send to the preview/convert endpoints. */
export function sessionChoiceFormFields(state) {
    if (state.longitudinal === true && state.column && state.session) {
        return { session_column: state.column, session_value: state.session };
    }
    return {};
}
