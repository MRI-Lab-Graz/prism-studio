import { describe, expect, it } from 'vitest';

import {
    derivedToEntry, entryToDerived, itemsUsedIn, scoreHasFormula, scoreLockReasons,
} from './formula-score.js';
import { buildRecipe } from './recipe-merge.js';

describe('Transforms.Derived entries', () => {
    it('round-trips and keeps unknown keys', () => {
        const d = { Name: 'hi', Method: 'max', Items: ['a', 'b'], Future: { x: 1 } };
        const entry = derivedToEntry(d);
        expect(entry).toMatchObject({ name: 'hi', method: 'max', items: ['a', 'b'] });
        expect(entryToDerived(entry)).toEqual(d);
        entry.method = 'min';
        entry.items = ['a'];
        expect(entryToDerived(entry)).toEqual({ Name: 'hi', Method: 'min', Items: ['a'], Future: { x: 1 } });
    });

    it('limits the method to max or min', () => {
        expect(entryToDerived({ name: 'n', method: 'sum', items: [] }).Method).toBe('max');
    });
});

describe('formula scores', () => {
    it('are editable, map scores stay locked', () => {
        const formula = { Name: 'F', Method: 'formula', Formula: '{a}+{b}', Items: ['a', 'b'] };
        expect(scoreHasFormula(formula)).toBe(true);
        expect(scoreLockReasons(formula, 'formula')).toEqual([]);
        const map = { Name: 'M', Method: 'map', Items: ['a'], Map: { 1: 2 } };
        expect(scoreHasFormula(map)).toBe(false);
        expect(scoreLockReasons(map, 'map').length).toBeGreaterThan(0);
    });

    it('a recipe with Invert, Derived and a formula score saves unchanged', () => {
        const loaded = {
            RecipeVersion: '1.0', Kind: 'survey', Survey: { Name: 'X', TaskName: 'x' },
            Transforms: {
                Invert: { Items: ['a'], Scale: { min: 1, max: 5 } },
                Derived: [{ Name: 'hi', Method: 'max', Items: ['a', 'b'], Future: 1 }],
            },
            Scores: [{ Name: 'F', Method: 'formula', Formula: '({a}+{b})/{a}', Items: ['a', 'b'] }],
        };
        const text = JSON.stringify(loaded);
        const out = buildRecipe({
            loaded: JSON.parse(text), modality: 'survey', infoKey: 'Survey', taskKey: 'TaskName', task: 'x',
            metadata: { name: 'X', description: '', citation: '' },
            invertTransform: loaded.Transforms.Invert,
            derivedTransform: loaded.Transforms.Derived.map(d => entryToDerived(derivedToEntry(d))),
            scores: loaded.Scores, versionedScores: {},
        });
        expect(JSON.stringify(out)).toBe(text);
    });

    it('itemsUsedIn lists the names between braces once', () => {
        expect(itemsUsedIn('({a}+{b})/{a}')).toEqual(['a', 'b']);
        expect(itemsUsedIn('')).toEqual([]);
    });
});
