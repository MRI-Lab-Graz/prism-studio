import { describe, expect, it } from 'vitest';

import { languageCodeProblem } from './language-codes.js';

const known = new Set(['en', 'de', 'fr']);

describe('languageCodeProblem', () => {
    it('accepts known codes with and without region', () => {
        for (const code of ['en', 'de', 'de-AT', ' fr ']) expect(languageCodeProblem(code, known)).toBe('');
    });
    it('rejects malformed codes', () => {
        for (const code of ['', 'EN', 'english', 'en-us', 'en_US', 'e']) expect(languageCodeProblem(code, known)).toMatch(/not a language code/);
    });
    it('rejects well-formed codes that do not exist', () => {
        expect(languageCodeProblem('xx', known)).toMatch(/not an ISO 639-1/);
    });
    it('only checks the format while the list is not loaded', () => {
        expect(languageCodeProblem('xx', null)).toBe('');
    });
});
