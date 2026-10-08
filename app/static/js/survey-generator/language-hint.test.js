import { describe, expect, it } from 'vitest';

import { languageHint } from './language-hint.js';

describe('languageHint', () => {
    it('tells a template without the base language which Base Language would make it usable', () => {
        expect(languageHint(['de'], 'en')).toBe('Only in DE: set Base Language to DE to use it.');
    });

    it('lists every language the template has and suggests the first', () => {
        expect(languageHint(['de', 'fr'], 'en')).toBe('Only in DE/FR: set Base Language to DE to use it.');
    });

    it('has no hint when the template has the base language', () => {
        expect(languageHint(['de', 'en'], 'en')).toBe('');
        expect(languageHint(['en'], 'en')).toBe('');
    });
});
