import { describe, expect, it } from 'vitest';

import { applyLinkToSchema, effectiveLink, suggestCriterion, unitMismatch } from './eligibility-link.js';

const CRITERIA = [
    { id: 'age', label: 'Age', term: 'nb:Age', unit: 'years' },
    { id: 'iq', label: 'IQ', term: null, unit: 'points' },
];

describe('suggestCriterion', () => {
    it('matches a column mapped to the same NeuroBagel term, ignoring case', () => {
        expect(suggestCriterion({ term_url: 'nb:age' }, CRITERIA)).toBe('age');
    });
    it('never suggests term-less criteria or unmapped columns', () => {
        expect(suggestCriterion({ term_url: null }, CRITERIA)).toBe('');
        expect(suggestCriterion({ term_url: 'nb:Sex' }, CRITERIA)).toBe('');
    });
});

describe('effectiveLink', () => {
    it('uses the explicit choice, including "none", before any suggestion', () => {
        expect(effectiveLink({ term_url: 'nb:Age', eligibility_criterion: 'iq' }, CRITERIA)).toBe('iq');
        expect(effectiveLink({ term_url: 'nb:Age', eligibility_criterion: '' }, CRITERIA)).toBe('');
    });
    it('falls back to the suggestion when nothing was chosen', () => {
        expect(effectiveLink({ term_url: 'nb:Age' }, CRITERIA)).toBe('age');
    });
    it('drops a link whose criterion no longer exists', () => {
        expect(effectiveLink({ eligibility_criterion: 'gone' }, CRITERIA)).toBe('');
    });
});

describe('applyLinkToSchema', () => {
    it('sets and removes only the link, leaving Annotations alone', () => {
        const schema = { age: { Description: 'Age', Annotations: { IsAbout: 'x' } } };
        applyLinkToSchema(schema, 'age', 'age');
        expect(schema.age).toEqual({ Description: 'Age', Annotations: { IsAbout: 'x' }, EligibilityCriterion: 'age' });
        applyLinkToSchema(schema, 'age', '');
        expect(schema.age).toEqual({ Description: 'Age', Annotations: { IsAbout: 'x' } });
    });
});

describe('unitMismatch', () => {
    it('flags differing units only when both are known', () => {
        expect(unitMismatch('years', 'months')).toBe(true);
        expect(unitMismatch('', 'years')).toBe(false);
        expect(unitMismatch('Years', 'years')).toBe(false);
    });
});
