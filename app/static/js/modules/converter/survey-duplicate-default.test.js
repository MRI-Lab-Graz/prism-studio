import { describe, expect, it } from 'vitest';

import { applyDuplicateDefault, defaultDuplicateHandling, defaultSkipExisting } from './survey-duplicate-default.js';

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

describe('applyDuplicateDefault', () => {
    const stub = (value = 'error') => {
        const events = [];
        return { value, events, dispatchEvent: (e) => events.push(e.type) };
    };

    it('announces the change so Session ID switches to "from dates"', () => {
        const select = stub();
        applyDuplicateDefault('survey_archive_939812.lsa', select);
        expect(select.value).toBe('sessions');
        expect(select.events).toEqual(['change']);
    });

    it('leaves the select alone for other file types', () => {
        const select = stub('keep_first');
        applyDuplicateDefault('data.csv', select);
        expect(select.value).toBe('keep_first');
        expect(select.events).toEqual([]);
    });
});
