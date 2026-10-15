import { describe, expect, it } from 'vitest';

import { notReadyText } from './not-ready-banner.js';

describe('notReadyText', () => {
    it('is empty when nothing is missing', () => {
        expect(notReadyText([])).toBe('');
        expect(notReadyText(undefined)).toBe('');
    });
    it('lists the missing fields and says tools are blocked', () => {
        const t = notReadyText(['Authors', 'Timepoints']);
        expect(t).toMatch(/Saved/);
        expect(t).toMatch(/Authors, Timepoints/);
        expect(t).toMatch(/blocked/);
    });
});
