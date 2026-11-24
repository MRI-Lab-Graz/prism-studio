import { describe, expect, it } from 'vitest';

import { initialInversionExpanded } from './inversion-fold.js';

describe('initialInversionExpanded', () => {
    it('is folded when no item is inverted', () => {
        expect(initialInversionExpanded(0)).toBe(false);
        expect(initialInversionExpanded(undefined)).toBe(false);
    });

    it('is open when at least one item is inverted', () => {
        expect(initialInversionExpanded(1)).toBe(true);
        expect(initialInversionExpanded(12)).toBe(true);
    });
});
