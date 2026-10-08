import { describe, expect, it } from 'vitest';

import { missingLanguages, languageHint } from './language-hint.js';

describe('missingLanguages', () => {
    it('lists the selected export languages the template lacks', () => {
        expect(missingLanguages(['de'], ['de', 'en'])).toEqual(['en']);
        expect(missingLanguages(['de', 'en'], ['de', 'en'])).toEqual([]);
    });
});

describe('languageHint', () => {
    it('tells a DE-only template under EN base to switch the base language and untick EN', () => {
        expect(languageHint(['de'], ['de', 'en'], 'en')).toBe('Only in DE: set Base Language to DE and untick EN to use it.');
    });

    it('only asks to untick when the template has the base language', () => {
        expect(languageHint(['en'], ['de', 'en'], 'en')).toBe('Only in EN: untick DE to use it.');
    });

    it('names every language it has and every one to untick', () => {
        expect(languageHint(['de', 'fr'], ['en', 'it'], 'en')).toBe('Only in DE/FR: set Base Language to DE and untick EN, IT to use it.');
    });

    it('has no hint for a usable template', () => {
        expect(languageHint(['de', 'en'], ['de', 'en'], 'en')).toBe('');
    });
});
