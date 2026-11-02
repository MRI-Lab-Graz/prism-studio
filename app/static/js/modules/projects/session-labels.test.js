import { describe, expect, it } from 'vitest';

import { SESSION_LABELS_INFO, sessionLabelsMissing, sessionLabelsVisible } from './session-labels.js';

describe('session labels (time or content) on the Projects page', () => {
    it('is asked only for several timepoints', () => {
        expect(sessionLabelsVisible('multiple')).toBe(true);
        for (const other of ['single', '', undefined]) expect(sessionLabelsVisible(other)).toBe(false);
    });

    it('a new project with several timepoints must answer', () => {
        expect(sessionLabelsMissing('multiple', '')).toBe(true);
        expect(sessionLabelsMissing('multiple', 'time')).toBe(false);
        expect(sessionLabelsMissing('multiple', 'content')).toBe(false);
    });

    it('is never missing when the question is not asked', () => {
        expect(sessionLabelsMissing('single', '')).toBe(false);
        expect(sessionLabelsMissing('', '')).toBe(false);
    });

    it('explains both answers and the resulting folder names', () => {
        expect(SESSION_LABELS_INFO).toContain('same order for everyone');
        expect(SESSION_LABELS_INFO).toContain('order differs per participant');
        expect(SESSION_LABELS_INFO).toContain('ses-rested, not ses-2');
    });
});
