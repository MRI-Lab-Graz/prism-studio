import { describe, expect, it } from 'vitest';

import { languageChoices } from './language-choices.js';

const group = (name, languages) => ({ name, detected_languages: languages });

describe('languageChoices', () => {
    it('lists every language any group has, sorted', () => {
        expect(languageChoices([group('A', ['en']), group('B', ['de'])]).languages).toEqual(['de', 'en']);
    });

    it('shares only the languages every group has', () => {
        const groups = [group('PSS', ['de', 'en']), group('Stress', ['de'])];
        expect(languageChoices(groups).shared).toEqual(['de']);
    });

    it('names the groups that lack a language, so the user is never surprised', () => {
        const groups = [group('PSS', ['de', 'en']), group('Stress', ['de']), group('WHO-5', ['de', 'en'])];
        expect(languageChoices(groups).missing).toEqual({ en: ['Stress'] });
    });

    it('names a group once even when it appears several times', () => {
        const groups = [group('Stress', ['de']), group('Stress', ['de']), group('PSS', ['de', 'en'])];
        expect(languageChoices(groups).missing).toEqual({ en: ['Stress'] });
    });

    it('treats a group without detected languages as English, like the generator', () => {
        expect(languageChoices([group('A', undefined), group('B', ['en'])]).shared).toEqual(['en']);
    });

    it('has no languages for no groups', () => {
        expect(languageChoices([])).toEqual({ languages: [], shared: [], missing: {} });
    });
});

import { languageLabel, resolveLanguages } from './language-choices.js';

describe('resolveLanguages', () => {
    const bilingual = [group('BFI-S', ['de', 'en']), group('PSS', ['de', 'en'])];

    it('a DE-only choice selects DE and has DE as the only base language', () => {
        const result = resolveLanguages(bilingual, { base_language: 'de', languages: ['de'] });
        expect(result.selected).toEqual(['de']);
        expect(result.base).toBe('de');
    });

    it('fixes an inconsistent incoming state (base EN, but only DE chosen): the base is a chosen language', () => {
        const result = resolveLanguages(bilingual, { base_language: 'en', languages: ['de'] });
        expect(result.selected).toEqual(['de']);
        expect(result.base).toBe('de');
    });

    it('puts the base first and keeps the other chosen languages', () => {
        const groups = [group('A', ['de', 'en', 'es']), group('B', ['de', 'en', 'es'])];
        const result = resolveLanguages(groups, { base_language: 'es', languages: ['de', 'es'] });
        expect(result.selected).toEqual(['es', 'de']);
        expect(result.base).toBe('es');
    });

    it('drops a chosen language some template lacks', () => {
        const groups = [group('A', ['de', 'es']), group('B', ['de'])];
        expect(resolveLanguages(groups, { base_language: 'de', languages: ['de', 'es'] }).selected).toEqual(['de']);
    });

    it('falls back to the base language, then to the first shared one, when nothing valid is chosen', () => {
        expect(resolveLanguages(bilingual, { base_language: 'en', languages: [] }).selected).toEqual(['en']);
        expect(resolveLanguages(bilingual, { base_language: 'fr', languages: ['fr'] }).selected).toEqual(['de']);
    });

    it('passes the coverage through so the dropdown can list every language and name who lacks it', () => {
        const groups = [group('A', ['de', 'es']), group('B', ['de'])];
        const result = resolveLanguages(groups, { base_language: 'de', languages: ['de'] });
        expect(result.languages).toEqual(['de', 'es']);
        expect(result.missing).toEqual({ es: ['B'] });
    });
});

describe('languageLabel', () => {
    it('names any language, with its code', () => {
        expect(languageLabel('de')).toMatch(/German/);
        expect(languageLabel('es')).toMatch(/Spanish/);
        expect(languageLabel('es')).toMatch(/ES/);
    });

    it('falls back to the code for something that is not a language', () => {
        expect(languageLabel('zz-invalid-code!')).toBe('ZZ-INVALID-CODE!');
    });
});
