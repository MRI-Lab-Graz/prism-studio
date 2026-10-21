import { describe, expect, it } from 'vitest';

import { parseRecipeFile } from './recipe-file.js';

const survey = { Kind: 'survey', Survey: { TaskName: 'phq9' }, Scores: [] };
const biometrics = { Kind: 'biometrics', Biometrics: { BiometricName: 'vo2' }, Scores: [] };

describe('parseRecipeFile', () => {
    it('reads modality and task from a survey recipe', () => {
        expect(parseRecipeFile(JSON.stringify(survey), 'biometrics')).toEqual({
            recipe: survey,
            modality: 'survey',
            task: 'phq9',
        });
    });

    it('reads modality and task from a biometrics recipe', () => {
        expect(parseRecipeFile(JSON.stringify(biometrics), 'survey')).toMatchObject({
            modality: 'biometrics',
            task: 'vo2',
        });
    });

    it('falls back to the selected modality when Kind is missing', () => {
        const { Kind, ...noKind } = biometrics;
        expect(parseRecipeFile(JSON.stringify(noKind), 'biometrics').modality).toBe('biometrics');
    });

    it('rejects text that is not JSON', () => {
        expect(() => parseRecipeFile('{nope', 'survey')).toThrow(/not valid JSON/);
    });

    it('rejects JSON that is not a recipe object', () => {
        expect(() => parseRecipeFile('[1]', 'survey')).toThrow(/recipe/);
    });

    it('rejects a recipe without a task name', () => {
        expect(() => parseRecipeFile(JSON.stringify({ Kind: 'survey', Survey: {} }), 'survey')).toThrow(
            /TaskName/
        );
    });
});
