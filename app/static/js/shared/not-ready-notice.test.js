import { describe, expect, it } from 'vitest';

import { isNotReadyResponse } from './not-ready-notice.js';

describe('isNotReadyResponse', () => {
    it('matches only 409 project_not_ready', () => {
        expect(isNotReadyResponse(409, { code: 'project_not_ready' })).toBe(true);
        expect(isNotReadyResponse(409, { code: 'other' })).toBe(false);
        expect(isNotReadyResponse(500, { code: 'project_not_ready' })).toBe(false);
        expect(isNotReadyResponse(409, null)).toBe(false);
    });
});
