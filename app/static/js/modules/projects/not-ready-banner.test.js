import { describe, expect, it } from 'vitest';

import { bannerText } from './not-ready-banner.js';

describe('bannerText', () => {
    it('is empty without a message', () => {
        expect(bannerText('', true)).toBe('');
        expect(bannerText(null, false)).toBe('');
    });
    it('prefixes Saved only right after a save', () => {
        expect(bannerText('Blocked: x.', true)).toBe('Saved. Blocked: x.');
        expect(bannerText('Blocked: x.', false)).toBe('Blocked: x.');
    });
    it('shows a corrupt-file message as is', () => {
        expect(bannerText('p could not be read', false)).toBe('p could not be read');
    });
});
