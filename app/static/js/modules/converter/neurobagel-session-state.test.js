import { describe, expect, it } from 'vitest';

import { carryForwardColumnEdits } from './neurobagel-session-state.js';

describe('carryForwardColumnEdits', () => {
    it('keeps unsaved edits when the widget state is rebuilt', () => {
        const prev = {
            age: { description: 'Age at scan', unit: 'years', data_type: 'continuous', label: 'Age', term_url: 'nb:Age', standardized_variable: 'age' },
        };
        const next = { age: { description: 'Age of participant', data_type: 'continuous' } };

        carryForwardColumnEdits(prev, next);

        expect(next.age).toMatchObject({
            description: 'Age at scan', unit: 'years', label: 'Age', term_url: 'nb:Age', standardized_variable: 'age',
        });
    });

    it('keeps level labels/mappings for codes still present, drops codes that are gone', () => {
        const prev = {
            sex: {
                levels: { M: { label: 'Male', description: 'd', uri: 'nb:M' }, X: { label: 'Gone' } },
                level_key_mappings: { M: 'M' },
            },
        };
        const next = { sex: { levels: { M: { label: 'M', description: '', uri: null }, F: { label: 'F', description: '', uri: null } } } };

        carryForwardColumnEdits(prev, next);

        expect(next.sex.levels.M).toEqual({ label: 'Male', description: 'd', uri: 'nb:M' });
        expect(next.sex.levels.F.label).toBe('F');
        expect(next.sex.levels.X).toBeUndefined();
        expect(next.sex.level_key_mappings).toEqual({ M: 'M' });
    });

    it('leaves new columns untouched', () => {
        const next = { new_col: { description: 'x' } };
        carryForwardColumnEdits({}, next);
        expect(next.new_col.description).toBe('x');
    });
});
