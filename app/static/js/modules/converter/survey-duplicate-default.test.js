import { describe, expect, it } from 'vitest';

import { defaultDuplicateHandling } from './survey-duplicate-default.js';

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
