import { describe, expect, it } from 'vitest';
import { parseRolesInput } from './roles.js';

describe('parseRolesInput', () => {
    it('splits on commas, semicolons and newlines', () => {
        expect(parseRolesInput('Investigation; chef, pilot\nSoftware'))
            .toEqual(['Investigation', 'chef', 'pilot', 'Software']);
    });
    it('normalizes CRediT casing and de-duplicates', () => {
        expect(parseRolesInput('investigation, Investigation;')).toEqual(['Investigation']);
    });
    it('returns [] for empty input', () => {
        expect(parseRolesInput('')).toEqual([]);
    });
});
