/**
 * Decision state for repeated rows in the Sociodemographics converter.
 * participants.tsv has one row per participant. Repeated rows with identical
 * values collapse quietly; only when a value CHANGES between a participant's
 * rows (e.g. age across sessions) does the user decide: keep ONE session for
 * everybody, or one column per session (age@ses-1, age@ses-2).
 *
 * Session labels are free-form strings: never rewritten here ("1" != "01").
 * `candidates` is the backend's session_candidates: [{ column, values }];
 * `conflicts` is its repeat_conflicts: the columns whose values change.
 */

export function createSessionChoiceState() {
    return { mode: '', column: '', session: '' };
}

/** mode: 'one' (keep one session) or 'split' (one column per session). */
export function setSessionChoiceMode(state, mode, candidates) {
    const onlyColumn = candidates.length === 1 ? candidates[0].column : '';
    return { mode, column: onlyColumn, session: '' };
}

export function setSessionChoiceColumn(state, column, candidates) {
    const known = candidates.find((candidate) => candidate.column === column);
    const keepSession = known && known.values.includes(state.session);
    return { ...state, column, session: keepSession ? state.session : '' };
}

export function setSessionChoiceSession(state, session) {
    return { ...state, session };
}

/**
 * The card shows while values conflict, and stays once a choice is made: a
 * chosen session removes the conflict from the next preview.
 */
export function sessionChoiceCardVisible(conflicts, candidates, state) {
    return (conflicts && conflicts.length > 0) || state.mode !== '';
}

/** Why the user cannot continue yet ('' when nothing blocks). */
export function sessionChoiceBlockReason(conflicts, candidates, state) {
    if (!sessionChoiceCardVisible(conflicts, candidates, state)) return '';
    if (state.mode === '') {
        const columns = conflicts.join(', ');
        return candidates.length === 0
            ? `${columns} change(s) between rows of the same participant. Number the responses by date, or fix the source file.`
            : `${columns} differ(s) between sessions. Choose how to keep the values: one session, or one column per session.`;
    }
    if (!state.column) return 'Please select the session column.';
    if (state.mode === 'one' && !state.session) {
        return 'Please select the one session to import into participants.tsv.';
    }
    return '';
}

/**
 * Same as sessionChoiceBlockReason, but only for the route that writes one row
 * per participant from the file (not the merge route, not editing the existing file).
 */
export function sessionChoiceBlockReasonForRoute({ mode, useMergeRoute }, conflicts, candidates, state) {
    return mode === 'file' && !useMergeRoute
        ? sessionChoiceBlockReason(conflicts, candidates, state)
        : '';
}

/** Form fields to send to the preview/convert endpoints. */
export function sessionChoiceFormFields(state) {
    if (state.mode === 'one' && state.column && state.session) {
        return { session_column: state.column, session_value: state.session };
    }
    if (state.mode === 'split' && state.column) {
        return { session_column: state.column, split_sessions: '1' };
    }
    return {};
}
