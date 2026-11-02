import { describe, expect, it } from 'vitest';

import { sessionLabelsMissing, sessionLabelsVisible } from './session-labels.js';

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
});
