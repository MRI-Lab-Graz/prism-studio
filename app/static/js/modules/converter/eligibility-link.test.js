import { describe, expect, it } from 'vitest';

import { applyLinkToSchema, criterionOptionsHtml, effectiveLink, savedLink, unitMismatch } from './eligibility-link.js';

const CRITERIA = [
    { id: 'age', label: 'Age', term: 'nb:Age', unit: 'years' },
    { id: 'iq', label: 'IQ', term: null, unit: 'points' },
];

describe('effectiveLink', () => {
    it('uses the explicit choice, including "none"', () => {
        expect(effectiveLink({ term_url: 'nb:Age', eligibility_criterion: 'iq' }, CRITERIA)).toBe('iq');
        expect(effectiveLink({ term_url: 'nb:Age', eligibility_criterion: '' }, CRITERIA)).toBe('');
    });
    it('never picks a criterion for the user, not even for the same NeuroBagel term', () => {
        expect(effectiveLink({ term_url: 'nb:Age' }, CRITERIA)).toBe('');
    });
    it('drops a link whose criterion no longer exists', () => {
        expect(effectiveLink({ eligibility_criterion: 'gone' }, CRITERIA)).toBe('');
    });
});

describe('savedLink', () => {
    it('saves only what the user chose: nothing chosen writes nothing', () => {
        expect(savedLink({ term_url: 'nb:Age' }, CRITERIA)).toBeUndefined();
    });
    it('saves an explicit choice, and an explicit "none" as an empty string', () => {
        expect(savedLink({ eligibility_criterion: 'age' }, CRITERIA)).toBe('age');
        expect(savedLink({ eligibility_criterion: '' }, CRITERIA)).toBe('');
    });
    it('turns a link to a deleted criterion into an explicit "none"', () => {
        expect(savedLink({ eligibility_criterion: 'gone' }, CRITERIA)).toBe('');
    });
});

describe('applyLinkToSchema', () => {
    it('sets the link, sets "" for an explicit none, and leaves Annotations alone', () => {
        const schema = { age: { Description: 'Age', Annotations: { IsAbout: 'x' } } };
        applyLinkToSchema(schema, 'age', 'age');
        expect(schema.age).toEqual({ Description: 'Age', Annotations: { IsAbout: 'x' }, EligibilityCriterion: 'age' });
        applyLinkToSchema(schema, 'age', '');
        expect(schema.age.EligibilityCriterion).toBe('');
    });
    it('writes nothing for a column that was never linked', () => {
        const schema = { age: { Description: 'Age' } };
        applyLinkToSchema(schema, 'age', undefined);
        expect(schema.age).toEqual({ Description: 'Age' });
    });
});

describe('unitMismatch', () => {
    it('flags differing units only when both are known', () => {
        expect(unitMismatch('years', 'months')).toBe(true);
        expect(unitMismatch('', 'years')).toBe(false);
        expect(unitMismatch('Years', 'years')).toBe(false);
    });
});

describe('criterionOptionsHtml', () => {
    it('escapes ids, labels and units that come from a shared project.json', () => {
        const html = criterionOptionsHtml(
            [{ id: 'a"b', label: '<img src=x onerror=alert(1)>', unit: '&' }], 'a"b');
        expect(html).not.toContain('<img');
        expect(html).toContain('value="a&quot;b"');
        expect(html).toContain('selected');
        expect(html).toContain('&amp;');
    });
    it('always offers "none" first, and falls back to the id when a label is missing', () => {
        const html = criterionOptionsHtml([{ id: 'iq' }], '');
        expect(html.startsWith('<option value="">none</option>')).toBe(true);
        expect(html).toContain('>iq<');
    });
});
