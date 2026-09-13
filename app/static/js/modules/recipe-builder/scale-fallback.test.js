import { describe, expect, it } from 'vitest';

import { buildInvertTransform, resolveInvertScale } from './scale-fallback.js';

describe('resolveInvertScale', () => {
    it('prefers an exact variation match', () => {
        const scaleRanges = { v1: { min: 0, max: 4 }, '': { min: 1, max: 7 } };
        expect(resolveInvertScale(scaleRanges, 'v1')).toEqual({ min: 0, max: 4 });
    });

    it('falls back to the default variation', () => {
        const scaleRanges = { '': { min: 1, max: 5 } };
        expect(resolveInvertScale(scaleRanges, 'v1')).toEqual({ min: 1, max: 5 });
    });

    it('returns null instead of a fabricated range when nothing was detected', () => {
        expect(resolveInvertScale({}, 'v1')).toBeNull();
        expect(resolveInvertScale(undefined, 'v1')).toBeNull();
    });
});

describe('buildInvertTransform', () => {
    it('builds a shared Scale when every inverted item has the same detected range', () => {
        const ranges = { A: { min: 1, max: 5 }, B: { min: 1, max: 5 } };
        const result = buildInvertTransform(['A', 'B'], id => ranges[id] || null);
        expect(result.transform).toEqual({
            Scale: { min: 1, max: 5 },
            Items: ['A', 'B'],
        });
        expect(result.itemsWithoutRange).toEqual([]);
    });

    it('adds ItemScales when inverted items have differing detected ranges', () => {
        const ranges = { A: { min: 1, max: 5 }, B: { min: 0, max: 4 } };
        const result = buildInvertTransform(['A', 'B'], id => ranges[id] || null);
        expect(result.transform.ItemScales).toEqual({
            A: { min: 1, max: 5 },
            B: { min: 0, max: 4 },
        });
    });

    it('never fabricates a 1-7 range for an item with no detected range', () => {
        const ranges = { A: { min: 1, max: 5 } };
        const result = buildInvertTransform(['A', 'B'], id => ranges[id] || null);
        // B has no detected range -- it must be excluded from the emitted
        // Invert.Items, not silently scored against A's (or any) scale.
        expect(result.transform.Items).toEqual(['A']);
        expect(result.transform.Items).not.toContain('B');
        expect(result.itemsWithoutRange).toEqual(['B']);
    });

    it('returns a null transform when no inverted item has a detected range', () => {
        const result = buildInvertTransform(['A', 'B'], () => null);
        expect(result.transform).toBeNull();
        expect(result.itemsWithoutRange).toEqual(['A', 'B']);
    });

    it('returns a null transform for an empty inverted set', () => {
        const result = buildInvertTransform([], () => null);
        expect(result.transform).toBeNull();
    });
});
