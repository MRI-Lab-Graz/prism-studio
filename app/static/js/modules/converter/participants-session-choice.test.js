import { describe, expect, it } from 'vitest';

import {
    createSessionChoiceState,
    sessionChoiceBlockReason,
    sessionChoiceBlockReasonForRoute,
    sessionChoiceFormFields,
    sessionChoiceCardVisible,
    setSessionChoiceColumn,
    setSessionChoiceMode,
    setSessionChoiceSession,
} from './participants-session-choice.js';

const ONE = [{ column: 'session', values: ['baseline', 'followup'] }];
const TWO = [
    { column: 'session', values: ['baseline', 'followup'] },
    { column: 'visit', values: ['v1', 'v2', 'v3'] },
];
const AGE = ['age'];

describe('participants session choice', () => {
    it('asks nothing while no value changes between a participant\'s rows', () => {
        const state = createSessionChoiceState();

        expect(sessionChoiceBlockReason([], ONE, state)).toBe('');
        expect(sessionChoiceCardVisible([], ONE, state)).toBe(false);
        expect(sessionChoiceFormFields(state)).toEqual({});
    });

    it('blocks and shows the card when a value changes between sessions', () => {
        const state = createSessionChoiceState();

        expect(sessionChoiceBlockReason(AGE, ONE, state)).toMatch(/age/);
        expect(sessionChoiceCardVisible(AGE, ONE, state)).toBe(true);
    });

    it('without a session column in the file the reason points to numbering by date', () => {
        expect(sessionChoiceBlockReason(AGE, [], createSessionChoiceState())).toMatch(/date/i);
    });

    it('"one session" blocks until a session is picked, then sends column and value', () => {
        let state = setSessionChoiceMode(createSessionChoiceState(), 'one', ONE);
        expect(state.column).toBe('session');
        expect(sessionChoiceBlockReason(AGE, ONE, state)).toMatch(/session/i);

        state = setSessionChoiceSession(state, 'followup');
        expect(sessionChoiceBlockReason(AGE, ONE, state)).toBe('');
        expect(sessionChoiceFormFields(state)).toEqual({
            session_column: 'session',
            session_value: 'followup',
        });
    });

    it('"one column per session" only needs the column and sends the split flag', () => {
        let state = setSessionChoiceMode(createSessionChoiceState(), 'split', TWO);
        expect(sessionChoiceBlockReason(AGE, TWO, state)).toMatch(/column/i);

        state = setSessionChoiceColumn(state, 'visit', TWO);
        expect(sessionChoiceBlockReason(AGE, TWO, state)).toBe('');
        expect(sessionChoiceFormFields(state)).toEqual({
            session_column: 'visit',
            split_sessions: '1',
        });
    });

    it('keeps the card and the rule once one session is chosen (the preview then has no conflicts left)', () => {
        let state = setSessionChoiceMode(createSessionChoiceState(), 'one', ONE);
        state = setSessionChoiceSession(state, 'baseline');

        expect(sessionChoiceCardVisible([], ONE, state)).toBe(true);
        expect(sessionChoiceBlockReason([], ONE, state)).toBe('');
    });

    it('changing the column drops a session that does not exist in it', () => {
        let state = setSessionChoiceMode(createSessionChoiceState(), 'one', TWO);
        state = setSessionChoiceColumn(state, 'session', TWO);
        state = setSessionChoiceSession(state, 'baseline');
        state = setSessionChoiceColumn(state, 'visit', TWO);

        expect(state.session).toBe('');
    });

    it('switching the mode clears the picked session', () => {
        let state = setSessionChoiceMode(createSessionChoiceState(), 'one', ONE);
        state = setSessionChoiceSession(state, 'baseline');
        state = setSessionChoiceMode(state, 'split', ONE);

        expect(state).toEqual({ mode: 'split', column: 'session', session: '' });
    });

    it('never rewrites session labels', () => {
        const labels = [{ column: 'ses', values: ['1', '01', 'pre'] }];
        let state = setSessionChoiceMode(createSessionChoiceState(), 'one', labels);
        state = setSessionChoiceSession(state, '01');

        expect(sessionChoiceFormFields(state).session_value).toBe('01');
    });

    describe('sessionChoiceBlockReasonForRoute', () => {
        const unanswered = createSessionChoiceState();

        it('blocks a plain file import that still owes the choice', () => {
            expect(sessionChoiceBlockReasonForRoute({ mode: 'file', useMergeRoute: false }, AGE, ONE, unanswered)).toMatch(/age/);
        });

        it('never blocks the merge route or modifying the existing file', () => {
            expect(sessionChoiceBlockReasonForRoute({ mode: 'file', useMergeRoute: true }, AGE, ONE, unanswered)).toBe('');
            expect(sessionChoiceBlockReasonForRoute({ mode: 'existing', useMergeRoute: false }, AGE, ONE, unanswered)).toBe('');
        });
    });
});
