import { describe, expect, it } from 'vitest';

import { itemIdProblem } from './item-id.js';

describe('itemIdProblem', () => {
    it('accepts letters, digits, underscore and hyphen', () => {
        expect(itemIdProblem('pss_01', ['AAI01'])).toBe('');
        expect(itemIdProblem('Task-1b', [])).toBe('');
    });
    it('rejects spaces, path characters, markup and non-ASCII letters', () => {
        for (const bad of ['A B', '../x', '<b>x</b>', 'ünï', 'a.b', 'a\\b', '__proto__']) {
            expect(itemIdProblem(bad, [])).toMatch(/letters, digits/);
        }
    });
    it('treats IDs that differ only in case as existing', () => {
        expect(itemIdProblem('aai01', ['AAI01'])).toMatch(/"AAI01" already exists/);
    });
});
