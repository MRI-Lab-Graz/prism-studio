import { describe, expect, it } from 'vitest';

import { modalityListState } from './modality-state.js';

describe('modalityListState', () => {
    it('says the request failed, not that the project is empty', () => {
        const state = modalityListState(null);
        expect(state.disabled).toBe(true);
        expect(state.text).toContain('failed to load modalities');
        expect(state.text).not.toContain('no survey or biometrics');
    });
    it('says the project has nothing for a successful empty list', () => {
        expect(modalityListState([]).text).toContain('no survey or biometrics data or templates');
    });
    it('is enabled with no message for a list', () => {
        expect(modalityListState([{ value: 'survey' }])).toEqual({ text: '', disabled: false });
    });
});
