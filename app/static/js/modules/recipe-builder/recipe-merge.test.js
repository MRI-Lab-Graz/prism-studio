import { describe, expect, it } from 'vitest';

import { buildRecipe, metadataFieldText } from './recipe-merge.js';

const LOADED = {
    RecipeVersion: '1.0',
    Kind: 'survey',
    Survey: {
        Name: 'Wellbeing',
        TaskName: 'wellbeing',
        Description: 'WHO-5 adaptation',
        Authors: ['Topp', 'Bech'],
        DOI: '10.1159/000376585',
    },
    Transforms: {
        Invert: { Items: ['WB02'], Scale: { min: 0, max: 5 } },
        Derived: [{ Name: 'helper', Method: 'sum', Items: ['WB01', 'WB02'] }],
    },
    Scores: [{ Name: 'Total', Method: 'sum', Items: ['WB01', 'WB02'] }],
    Psychometrics: { Reliability: { Note: 'validated' } },
    Usage: { ScoringGuidelines: { en: 'Sum all items.' } },
    References: [{ Citation: 'Topp et al. (2015)' }],
};

const EDITS = {
    modality: 'survey',
    infoKey: 'Survey',
    taskKey: 'TaskName',
    task: 'wellbeing',
    metadata: { name: 'Wellbeing', description: 'WHO-5 adaptation', citation: '' },
    invertTransform: { Items: ['WB02'], Scale: { min: 0, max: 5 } },
    scores: [{ Name: 'Total', Method: 'sum', Items: ['WB01', 'WB02'] }],
    versionedScores: {},
};

describe('buildRecipe', () => {
    it('keeps every top-level section the builder does not edit', () => {
        const recipe = buildRecipe({ loaded: LOADED, ...EDITS });

        expect(recipe.Psychometrics).toEqual(LOADED.Psychometrics);
        expect(recipe.Usage).toEqual(LOADED.Usage);
        expect(recipe.References).toEqual(LOADED.References);
    });

    it('keeps Survey keys it does not edit and updates the ones it owns', () => {
        const recipe = buildRecipe({
            loaded: LOADED,
            ...EDITS,
            metadata: { name: 'New name', description: '', citation: 'Cite' },
        });

        expect(recipe.Survey.Authors).toEqual(['Topp', 'Bech']);
        expect(recipe.Survey.DOI).toBe('10.1159/000376585');
        expect(recipe.Survey.TaskName).toBe('wellbeing');
        expect(recipe.Survey.Name).toBe('New name');
        expect(recipe.Survey.Citation).toBe('Cite');
        expect('Description' in recipe.Survey).toBe(false); // emptied by the user
    });

    it('keeps Transforms.Derived while updating Invert', () => {
        const recipe = buildRecipe({
            loaded: LOADED,
            ...EDITS,
            invertTransform: { Items: ['WB01'], Scale: { min: 0, max: 5 } },
        });

        expect(recipe.Transforms.Derived).toEqual(LOADED.Transforms.Derived);
        expect(recipe.Transforms.Invert.Items).toEqual(['WB01']);
    });

    it('removes Invert when nothing is inverted, and Transforms when it ends up empty', () => {
        const noInvert = buildRecipe({ loaded: LOADED, ...EDITS, invertTransform: null });
        expect('Invert' in noInvert.Transforms).toBe(false);
        expect(noInvert.Transforms.Derived).toBeDefined();

        const onlyInvert = { ...LOADED, Transforms: { Invert: LOADED.Transforms.Invert } };
        const bare = buildRecipe({ loaded: onlyInvert, ...EDITS, invertTransform: null });
        expect('Transforms' in bare).toBe(false);
    });

    it('replaces Scores and VersionedScores as a whole, so removed scales disappear', () => {
        const withVariants = {
            ...LOADED,
            VersionedScores: { short: [{ Name: 'S', Method: 'sum', Items: ['WB01'] }] },
        };
        const recipe = buildRecipe({ loaded: withVariants, ...EDITS, scores: [], versionedScores: {} });

        expect('Scores' in recipe).toBe(false);
        expect('VersionedScores' in recipe).toBe(false);
    });

    it('keeps a localized name unchanged unless the user edited the text', () => {
        const localized = { ...LOADED, Survey: { ...LOADED.Survey, Name: { en: 'Wellbeing', de: 'Wohlbefinden' } } };

        const untouched = buildRecipe({
            loaded: localized,
            ...EDITS,
            metadata: { name: metadataFieldText(localized.Survey.Name), description: 'WHO-5 adaptation', citation: '' },
        });
        expect(untouched.Survey.Name).toEqual({ en: 'Wellbeing', de: 'Wohlbefinden' });

        const edited = buildRecipe({
            loaded: localized,
            ...EDITS,
            metadata: { name: 'Custom', description: 'WHO-5 adaptation', citation: '' },
        });
        expect(edited.Survey.Name).toBe('Custom');
    });

    it('builds a minimal recipe when nothing was loaded', () => {
        const recipe = buildRecipe({
            loaded: null,
            ...EDITS,
            metadata: { name: '', description: '', citation: '' },
            invertTransform: null,
            scores: [],
        });

        expect(recipe).toEqual({ RecipeVersion: '1.0', Kind: 'survey', Survey: { TaskName: 'wellbeing' } });
    });

    it('does not mutate the loaded recipe', () => {
        const before = JSON.stringify(LOADED);
        buildRecipe({ loaded: LOADED, ...EDITS, invertTransform: null, scores: [] });
        expect(JSON.stringify(LOADED)).toBe(before);
    });
});

describe('metadataFieldText', () => {
    it('returns a string as is, a localized value as its English (else first) text, and nothing otherwise', () => {
        expect(metadataFieldText(' Plain ')).toBe('Plain');
        expect(metadataFieldText({ de: 'Nur', en: 'Only' })).toBe('Only');
        expect(metadataFieldText({ de: 'Nur Deutsch' })).toBe('Nur Deutsch');
        expect(metadataFieldText(undefined)).toBe('');
    });
});
