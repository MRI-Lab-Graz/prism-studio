import { describe, expect, it } from 'vitest';

import { orderGrid, orderPayload } from './session-order-panel.js';

const rows = [
    { participant: 'P01', response_id: '1', number: '1', session: 'sleepdep', reason: 'auto' },
    { participant: 'P01', response_id: '2', number: '2', session: 'rested', reason: 'auto' },
    { participant: 'P02', response_id: '3', number: '1', session: null, reason: 'not in session order' },
    { participant: 'P02', response_id: '4', number: null, session: 'rested', reason: 'override' },
    { participant: 'P03', response_id: '5', number: null, session: null, reason: 'incomplete' },
];

describe('session order grid', () => {
    it('lists one cell per numbered response with the recorded name', () => {
        const order = { P01: { 1: 'sleepdep', 2: 'rested' } };
        expect(orderGrid(rows, order)).toEqual([
            { participant: 'P01', number: '1', name: 'sleepdep' },
            { participant: 'P01', number: '2', name: 'rested' },
            { participant: 'P02', number: '1', name: '' },
        ]);
    });

    it('leaves out responses that have no number (named by hand, skipped, incomplete)', () => {
        const numbers = orderGrid(rows, {}).map((cell) => `${cell.participant}:${cell.number}`);
        expect(numbers).not.toContain('P03:null');
        expect(numbers).toHaveLength(3);
    });
});

describe('session order save payload', () => {
    it('a typed name is saved as typed; blank removes the entry', () => {
        expect(orderPayload('P01', '1', ' sleepdep ')).toEqual({ participant: 'P01', number: '1', session: ' sleepdep ' });
        expect(orderPayload('P01', '1', '  ')).toEqual({ participant: 'P01', number: '1', clear: true });
    });
});
