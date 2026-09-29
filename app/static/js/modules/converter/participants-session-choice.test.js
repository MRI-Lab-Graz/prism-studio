import { describe, expect, it } from 'vitest';

import {
    createSessionChoiceState,
    sessionChoiceBlockReason,
    sessionChoiceFormFields,
    setSessionChoiceColumn,
    setSessionChoiceLongitudinal,
    setSessionChoiceSession,
} from './participants-session-choice.js';

const ONE = [{ column: 'session', values: ['baseline', 'followup'] }];
const TWO = [
    { column: 'session', values: ['baseline', 'followup'] },
    { column: 'visit', values: ['v1', 'v2', 'v3'] },
];

describe('participants session choice', () => {
    it('does not block a file without several sessions', () => {
        expect(sessionChoiceBlockReason([], createSessionChoiceState())).toBe('');
        expect(sessionChoiceFormFields(createSessionChoiceState())).toEqual({});
    });

    it('blocks until the user has said whether the dataset is longitudinal', () => {
        expect(sessionChoiceBlockReason(ONE, createSessionChoiceState())).toMatch(/longitudinal/i);
    });

    it('answering "no" unblocks and sends no session fields', () => {
        const state = setSessionChoiceLongitudinal(createSessionChoiceState(), false, ONE);

        expect(sessionChoiceBlockReason(ONE, state)).toBe('');
        expect(sessionChoiceFormFields(state)).toEqual({});
    });

    it('answering "yes" still blocks until one session is picked', () => {
        const state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, ONE);

        expect(sessionChoiceBlockReason(ONE, state)).toMatch(/session/i);
    });

    it('preselects the session column when there is only one candidate', () => {
        const state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, ONE);

        expect(state.column).toBe('session');
    });

    it('asks for the column when there are several candidates', () => {
        const state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, TWO);

        expect(state.column).toBe('');
        expect(sessionChoiceBlockReason(TWO, state)).toMatch(/column/i);
    });

    it('a picked column and session produce the form fields', () => {
        let state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, TWO);
        state = setSessionChoiceColumn(state, 'visit', TWO);
        state = setSessionChoiceSession(state, 'v2');

        expect(sessionChoiceBlockReason(TWO, state)).toBe('');
        expect(sessionChoiceFormFields(state)).toEqual({
            session_column: 'visit',
            session_value: 'v2',
        });
    });

    it('changing the column drops a session that does not exist in it', () => {
        let state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, TWO);
        state = setSessionChoiceColumn(state, 'session', TWO);
        state = setSessionChoiceSession(state, 'baseline');
        state = setSessionChoiceColumn(state, 'visit', TWO);

        expect(state.session).toBe('');
    });

    it('switching back to "no" clears the column and session', () => {
        let state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, ONE);
        state = setSessionChoiceSession(state, 'baseline');
        state = setSessionChoiceLongitudinal(state, false, ONE);

        expect(state).toEqual({ longitudinal: false, column: '', session: '' });
    });

    it('never rewrites session labels', () => {
        const labels = [{ column: 'ses', values: ['1', '01', 'pre'] }];
        let state = setSessionChoiceLongitudinal(createSessionChoiceState(), true, labels);
        state = setSessionChoiceSession(state, '01');

        expect(sessionChoiceFormFields(state).session_value).toBe('01');
    });
});
