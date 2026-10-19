import { describe, expect, it } from 'vitest';

import { TERMS, checkedCriteriaCount, criteriaFromRows, criterionKey, hasContent, initEligibilityCriteria, isComplete, newRow, rememberRemoved, rowsFromCriteria, setEligibilityCriteria } from './eligibility-criteria.js';

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
        const a = { ...newRow('nb:Age'), min: '18', accepted: true };
        const b = { ...newRow('nb:Age'), max: '65', accepted: true };
        const ids = criteriaFromRows([a, b]).map((c) => c.id);
        expect(new Set(ids).size).toBe(2);
        expect(criteriaFromRows(rowsFromCriteria(criteriaFromRows([a, b]))).map((c) => c.id)).toEqual(ids);
    });

    it('parses numbers, keeping decimals and open ends', () => {
        const [c] = criteriaFromRows([{ ...newRow('nb:Age'), min: '17.5', max: '', accepted: true }]);
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
        expect(isComplete({ ...newRow('nb:Age'), min: '35', max: '18' })).toBe(false); // inverted range
        expect(isComplete({ ...newRow('nb:Age'), min: '18', max: '18' })).toBe(true);
        expect(isComplete({ ...newRow('nb:Sex') })).toBe(false);
        expect(isComplete({ ...newRow('nb:Sex'), values: ['Male'] })).toBe(true);
    });
});

describe('id stability', () => {
    it('keeps a generated id when the label is renamed before the next load', () => {
        const row = { ...newRow(null), label: 'IQ', min: '85', accepted: true };
        const [first] = criteriaFromRows([row]);
        expect(first.id).toBe('iq');
        row.label = 'IQ (WAIS)';
        const [second] = criteriaFromRows([row]);
        expect(second.id).toBe('iq');
    });
});

describe('draft and accepted rows', () => {
    it('a new row is a draft; only accepted, complete rows are saved', () => {
        const draft = { ...newRow('nb:Age'), min: '18' };
        expect(draft.accepted).toBe(false);
        expect(criteriaFromRows([draft])).toEqual([]);
        expect(criteriaFromRows([{ ...draft, accepted: true }]).map((c) => c.id)).toEqual(['age']);
    });

    it('rows loaded from project.json are already accepted', () => {
        expect(rowsFromCriteria([AGE])[0].accepted).toBe(true);
    });

    it('accepted state is not written into project.json', () => {
        expect('accepted' in criteriaFromRows(rowsFromCriteria([AGE]))[0]).toBe(false);
    });
});

describe('checkedCriteriaCount', () => {
    it('counts accepted criteria per mode, which feeds the Core badges', () => {
        setEligibilityCriteria([AGE, NO_MALE, IQ]);
        expect(checkedCriteriaCount('include')).toBe(2);
        expect(checkedCriteriaCount('exclude')).toBe(1);
        setEligibilityCriteria([]);
        expect(checkedCriteriaCount('include')).toBe(0);
    });
});

describe('hasContent (decides whether a draft blocks a save or is discarded silently)', () => {
    it('a freshly added row holds nothing, even though Age comes with a default unit', () => {
        expect(hasContent(newRow('nb:Age'))).toBe(false);
        expect(hasContent(newRow('nb:Sex'))).toBe(false);
        expect(hasContent(newRow(null))).toBe(false);
    });
    it('a typed limit, a ticked value or a name for Other measure is content', () => {
        expect(hasContent({ ...newRow('nb:Age'), min: '18' })).toBe(true);
        expect(hasContent({ ...newRow('nb:Sex'), values: ['Male'] })).toBe(true);
        expect(hasContent({ ...newRow(null), label: 'IQ' })).toBe(true);
    });
});

describe('criteria loaded from project.json', () => {
    it('a complete one is accepted (a chip); an incomplete one comes back as a draft to fix, not dropped', () => {
        const incomplete = { id: 'age', label: 'Age', term: 'nb:Age', type: 'numeric', mode: 'include' }; // no bounds
        const [complete, fixme] = rowsFromCriteria([AGE, incomplete]);
        expect(complete.accepted).toBe(true);
        expect(fixme.accepted).toBe(false);
        expect(fixme.id).toBe('age'); // its id is kept, so linked columns still find it once fixed
    });
});

describe('remembering the id of a removed criterion', () => {
    const ageRow = (extra = {}) => ({ ...newRow('nb:Age'), min: '5', accepted: true, ...extra });

    it('a criterion with the same term and name gets its removed id back', () => {
        const remembered = new Map();
        rememberRemoved([{ ...ageRow(), id: 'min_age' }], remembered);
        const [again] = criteriaFromRows([ageRow()], remembered);
        expect(again.id).toBe('min_age');
    });

    it('the remembered id is used once', () => {
        const remembered = new Map();
        rememberRemoved([{ ...ageRow(), id: 'min_age' }], remembered);
        const [first, second] = criteriaFromRows([ageRow(), ageRow({ min: '6' })], remembered);
        expect(first.id).toBe('min_age');
        expect(second.id).not.toBe('min_age');
    });

    it('a different term or name is not affected', () => {
        const remembered = new Map();
        rememberRemoved([{ ...ageRow(), id: 'min_age' }], remembered);
        const [other] = criteriaFromRows([{ ...newRow(null), label: 'IQ', min: '85', accepted: true }], remembered);
        expect(other.id).toBe('iq');
    });

    it('is not used when another criterion already holds that id', () => {
        const remembered = new Map();
        rememberRemoved([{ ...ageRow(), id: 'min_age' }], remembered);
        const holder = { ...newRow(null), label: 'Holder', min: '1', accepted: true, id: 'min_age' };
        const [, again] = criteriaFromRows([holder, ageRow()], remembered);
        expect(again.id).toBe('age');
    });

    it('the key ignores case and surrounding spaces of the name', () => {
        expect(criterionKey({ term: null, label: '  IQ ' })).toBe(criterionKey({ term: null, label: 'iq' }));
        expect(criterionKey({ term: 'nb:Age', label: 'Age' })).not.toBe(criterionKey({ term: null, label: 'Age' }));
    });

    it('several removed criteria with the same key come back in turn', () => {
        const remembered = new Map();
        rememberRemoved([{ ...ageRow(), id: 'age' }, { ...ageRow(), id: 'age-2' }], remembered);
        const [a, b] = criteriaFromRows([ageRow(), ageRow({ min: '6' })], remembered);
        expect([a.id, b.id].sort()).toEqual(['age', 'age-2']);
    });
});
