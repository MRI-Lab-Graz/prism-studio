import { describe, expect, it, vi } from 'vitest';

import {
    addItemOnce, debounce, derivedForSave, derivedToEntry, entryToDerived, insertAtCursor,
    scoreHasFormula, scoreLockReasons,
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
});

describe('insertAtCursor', () => {
    it('inserts {ITEM} at the cursor and moves the cursor behind it', () => {
        expect(insertAtCursor('a+b', 1, 1, 'x')).toEqual({ text: 'a{x}+b', cursor: 4 });
    });
    it('replaces a selection', () => {
        expect(insertAtCursor('a+b', 0, 3, 'x')).toEqual({ text: '{x}', cursor: 3 });
    });
});

describe('addItemOnce', () => {
    it('adds a name once and returns the same list otherwise', () => {
        const items = ['a'];
        expect(addItemOnce(items, 'b')).toEqual(['a', 'b']);
        expect(addItemOnce(items, 'a')).toBe(items);
    });
});

describe('debounce', () => {
    it('runs once after the pause with the last arguments', () => {
        vi.useFakeTimers();
        const fn = vi.fn();
        const d = debounce(fn, 300);
        d(1); d(2);
        vi.advanceTimersByTime(299);
        expect(fn).not.toHaveBeenCalled();
        vi.advanceTimersByTime(1);
        expect(fn).toHaveBeenCalledTimes(1);
        expect(fn).toHaveBeenCalledWith(2);
        vi.useRealTimers();
    });
});

describe('Derived entries other than max/min', () => {
    it('pass through untouched, read-only', () => {
        const d = { Name: 'x', Method: 'map', Source: 'a', Mapping: { 1: 2 } };
        const entry = derivedToEntry(d);
        expect(entry.readOnly).toBe(true);
        expect(entryToDerived(entry)).toEqual(d);
        expect(derivedForSave([entry])).toEqual([d]);
    });
    it('empty-named editable entries are not saved', () => {
        const blank = derivedToEntry({ Name: '', Method: 'max', Items: [] });
        const named = derivedToEntry({ Name: 'hi', Method: 'max', Items: ['a'] });
        expect(derivedForSave([blank, named])).toEqual([{ Name: 'hi', Method: 'max', Items: ['a'] }]);
    });
});
