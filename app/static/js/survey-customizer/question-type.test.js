import { describe, expect, it } from 'vitest';

import { detectQuestionType } from './question-type.js';

describe('detectQuestionType', () => {
    it('is the type the backend derived (the export uses it when nothing is overridden)', () => {
        expect(detectQuestionType({ questionType: 'N', toolOverrides: {} })).toBe('N');
    });

    it("is the user's override for this export when there is one", () => {
        expect(detectQuestionType({ questionType: 'L', toolOverrides: { questionType: '!' } })).toBe('!');
    });

    it('ignores an old LimeSurvey block in the template', () => {
        const question = { questionType: 'L', originalData: { LimeSurvey: { questionType: 'N' } } };
        expect(detectQuestionType(question)).toBe('L');
    });
});
