import { describe, expect, it } from 'vitest';

import { canSaveSessionMap, entriesToSave, numericTwinLabels, validSessionName, withDefaults } from './session-map-panel.js';

describe('session map panel rules', () => {
    it('accepts letters and digits only', () => {
        for (const ok of ['1', '01', 'pre', 'T0', 'a1B2']) expect(validSessionName(ok)).toBe(true);
        for (const bad of ['', ' ', 'ses-1', 'a b', '1_2', 'é']) expect(validSessionName(bad)).toBe(false);
    });

    it('cannot save until every label has a valid name typed by the user', () => {
        expect(canSaveSessionMap(['pre', 'post'], {})).toBe(false);
        expect(canSaveSessionMap(['pre', 'post'], { pre: '1' })).toBe(false);
        expect(canSaveSessionMap(['pre', 'post'], { pre: '1', post: 'ses-2' })).toBe(false);
        expect(canSaveSessionMap(['pre', 'post'], { pre: '1', post: '2' })).toBe(true);
    });

    it('never invents a value: nothing typed means nothing to save', () => {
        expect(entriesToSave(['pre', 'post'], {})).toEqual({});
        expect(entriesToSave(['pre', 'post'], { pre: ' 1 ', post: '' })).toEqual({ pre: '1' });
    });

    it('a blank label can never be mapped: not saved, and it never enables Save', () => {
        expect(canSaveSessionMap([''], { '': '1' })).toBe(false);
        expect(entriesToSave([''], { '': '1' })).toEqual({});
        // the other labels can still be saved while the blank one is left to be fixed in the file
        expect(canSaveSessionMap(['', 'pre'], { pre: '1' })).toBe(true);
        expect(entriesToSave(['', 'pre'], { '': '9', pre: '1' })).toEqual({ pre: '1' });
    });

    it('spots labels that differ only by leading zeros, without ever treating them as equal', () => {
        expect(numericTwinLabels(['1', '01', 'pre'])).toEqual([['1', '01']]);
        expect(numericTwinLabels(['1', '2', 'pre'])).toEqual([]);
        expect(numericTwinLabels(['1', '01', '001', '2'])).toEqual([['1', '01', '001']]);
        expect(numericTwinLabels(['', '0', '00'])).toEqual([['0', '00']]);
        expect(numericTwinLabels(['12345678901234567890', '012345678901234567890'])).toEqual([
            ['12345678901234567890', '012345678901234567890'],
        ]);
    });

    it('pre-fills suggested names for empty inputs only, never over what the user typed', () => {
        const typed = { pre: 'T0' };
        expect(withDefaults(['pre', 'post', ''], typed, { pre: '1', post: '2', '': '3' })).toEqual({ pre: 'T0', post: '2' });
        expect(withDefaults(['pre'], {}, undefined)).toEqual({});
    });
});
