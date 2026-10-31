import { describe, expect, it } from 'vitest';

import { defaultLanguageOptions, languageLabel, languageOptions } from './language-picker.js';

describe('languageOptions', () => {
    it('offers every known code that is not chosen yet, sorted', () => {
        expect(languageOptions(new Set(['fr', 'en', 'de']), ['en']).map((o) => o.value)).toEqual(['de', 'fr']);
    });
    it('is empty while the code list is not loaded', () => {
        expect(languageOptions(null, ['en'])).toEqual([]);
    });
    it('labels each option with code and language name', () => {
        expect(languageOptions(new Set(['de']), [])[0].label).toBe('de (German)');
    });
});

describe('languageLabel', () => {
    it('shows the name for a region code and falls back to the bare code', () => {
        expect(languageLabel('de-AT')).toMatch(/^de-AT \(.*German.*\)$/);
        expect(languageLabel('zz-nope!')).toBe('zz-nope!');
    });
});

describe('defaultLanguageOptions', () => {
    it('offers exactly the chosen languages', () => {
        expect(defaultLanguageOptions(['de', 'en'], '').map((o) => o.value)).toEqual(['de', 'en']);
    });
    it('keeps a stored default that is not chosen, so loaded data is never hidden', () => {
        expect(defaultLanguageOptions(['de'], 'fr').map((o) => o.value)).toEqual(['de', 'fr']);
    });
});
