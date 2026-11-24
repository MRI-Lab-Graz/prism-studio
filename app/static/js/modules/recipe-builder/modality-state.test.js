import { describe, expect, it } from 'vitest';

import { modalityListState, modalityOptions } from './modality-state.js';

describe('modalityListState', () => {
    it('says no project loaded without a project, whatever the list', () => {
        expect(modalityListState([], false).text).toBe('— no project loaded —');
        expect(modalityListState(null, false).text).toBe('— no project loaded —');
    });
    it('says the request failed, not that the project is empty', () => {
        const state = modalityListState(null, true);
        expect(state.disabled).toBe(true);
        expect(state.text).toContain('failed to load modalities');
    });
    it('says the project has nothing for a successful empty list, without naming modalities', () => {
        const text = modalityListState([], true).text;
        expect(text).toContain('no modalities');
        expect(text).not.toMatch(/survey|biometrics/);
    });
    it('is enabled with no message for a list', () => {
        expect(modalityListState([{ value: 'survey' }], true)).toEqual({ text: '', disabled: false });
    });
});

describe('modalityOptions', () => {
    const list = [{ value: 'survey', label: 'Survey' }];
    it('lists the project modalities as they are', () => {
        expect(modalityOptions(list, '')).toEqual(list);
        expect(modalityOptions(list, 'survey')).toEqual(list);
    });
    it('adds the modality a recipe carries when the project has none of it', () => {
        expect(modalityOptions(list, 'biometrics')).toEqual([
            ...list,
            { value: 'biometrics', label: 'biometrics (not in this project)' },
        ]);
    });
});
