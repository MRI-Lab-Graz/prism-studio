import { describe, expect, it } from 'vitest';

import { TERMS, criteriaFromRows, initEligibilityCriteria, isComplete, newRow, rowsFromCriteria } from './eligibility-criteria.js';

const AGE = {
    id: 'age', label: 'Age', term: 'nb:Age', type: 'numeric',
    mode: 'include', min: 18, max: 35, unit: 'years',
};
const NO_MALE = {
    id: 'sex', label: 'Sex', term: 'nb:Sex', type: 'categorical',
    mode: 'exclude', values: ['Male'],
};
const IQ = {
    id: 'iq', label: 'IQ', term: null, type: 'numeric',
    mode: 'include', min: 85, unit: 'points',
};

describe('eligibility criteria rows', () => {
    it('round-trips numeric, categorical and other-measure criteria losslessly', () => {
        const list = [AGE, NO_MALE, IQ];
        expect(criteriaFromRows(rowsFromCriteria(list))).toEqual(list);
    });

    it('offers the NeuroBagel terms plus Other measure', () => {
        const terms = TERMS.map((t) => t.term);
        expect(terms).toEqual(expect.arrayContaining(['nb:Age', 'nb:Sex', 'nb:Handedness', null]));
    });

    it('drops incomplete rows', () => {
        const rows = [
            { ...newRow('nb:Age') },                                  // no min or max
            { ...newRow('nb:Sex') },                                  // no values
            { ...newRow(null), label: '', min: '5' },                 // other measure without a name
        ];
        expect(criteriaFromRows(rows)).toEqual([]);
    });

    it('generates unique, stable ids', () => {
        const a = { ...newRow('nb:Age'), min: '18' };
        const b = { ...newRow('nb:Age'), max: '65' };
        const ids = criteriaFromRows([a, b]).map((c) => c.id);
        expect(new Set(ids).size).toBe(2);
        expect(criteriaFromRows(rowsFromCriteria(criteriaFromRows([a, b]))).map((c) => c.id)).toEqual(ids);
    });

    it('parses numbers, keeping decimals and open ends', () => {
        const [c] = criteriaFromRows([{ ...newRow('nb:Age'), min: '17.5', max: '' }]);
        expect(c.min).toBe(17.5);
        expect('max' in c).toBe(false);
    });
});

describe('initEligibilityCriteria', () => {
    it('does nothing on a page without the Eligibility form', () => {
        expect(() => initEligibilityCriteria({ list: null, select: null, addButton: null })).not.toThrow();
    });
});

describe('criteria the form cannot fully show', () => {
    it('a hand-written criterion without a label gets one from its term, or its id, instead of vanishing', () => {
        const noLabel = { id: 'age', term: 'nb:Age', type: 'numeric', mode: 'include', min: 18 };
        expect(criteriaFromRows(rowsFromCriteria([noLabel]))).toEqual([{ ...noLabel, label: 'Age' }]);
        const other = { id: 'vo2max', term: null, type: 'numeric', mode: 'include', min: 30 };
        expect(criteriaFromRows(rowsFromCriteria([other]))[0].label).toBe('vo2max');
    });

    it('keeps keys the form does not know about', () => {
        const c = { ...AGE, note: 'from a colleague' };
        expect(criteriaFromRows(rowsFromCriteria([c]))).toEqual([c]);
    });

    it('tells an incomplete row apart, so the page can say it is not saved', () => {
        expect(isComplete(newRow('nb:Age'))).toBe(false);
        expect(isComplete({ ...newRow('nb:Age'), min: '18' })).toBe(true);
        expect(isComplete({ ...newRow('nb:Sex') })).toBe(false);
        expect(isComplete({ ...newRow('nb:Sex'), values: ['Male'] })).toBe(true);
    });
});
