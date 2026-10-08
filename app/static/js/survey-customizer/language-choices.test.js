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
