import { describe, expect, it } from 'vitest';

import { defaultDuplicateHandling, defaultSkipExisting } from './survey-duplicate-default.js';

describe('defaultDuplicateHandling', () => {
    it('numbers repeated participants as sessions by date for LimeSurvey archives', () => {
        expect(defaultDuplicateHandling('survey_archive_939812.lsa')).toBe('sessions');
        expect(defaultDuplicateHandling('/data/Survey.LSA')).toBe('sessions');
    });

    it('leaves the choice alone for other file types', () => {
        expect(defaultDuplicateHandling('data.xlsx')).toBeNull();
        expect(defaultDuplicateHandling('')).toBeNull();
    });
});

describe('defaultSkipExisting', () => {
    it('is on for LimeSurvey archives and off for everything else', () => {
        expect(defaultSkipExisting('survey_archive_939812.lsa')).toBe(true);
        expect(defaultSkipExisting('data.csv')).toBe(false);
        expect(defaultSkipExisting('')).toBe(false);
    });
});
