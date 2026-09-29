import { describe, expect, it } from 'vitest';
import { describeProjectNameProblem } from './create-preflight.js';

describe('describeProjectNameProblem', () => {
    it('accepts valid and empty names', () => {
        expect(describeProjectNameProblem('my_study-1')).toBe('');
        expect(describeProjectNameProblem('')).toBe('');
    });
    it('names spaces, umlauts and other characters distinctly', () => {
        expect(describeProjectNameProblem('fdsaf Agder')).toMatch(/spaces/);
        expect(describeProjectNameProblem('wellbeingÄ')).toMatch(/umlauts/);
        expect(describeProjectNameProblem('a$b')).toMatch(/Only letters/);
    });
});
