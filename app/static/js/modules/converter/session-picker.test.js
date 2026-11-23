import { describe, expect, it } from 'vitest';

import { sessionToRestore } from './session-picker.js';

describe('session picker selection', () => {
    it('never preselects the only existing session: the file may be another wave', () => {
        expect(sessionToRestore('', ['1'])).toBe('');
    });

    it('keeps what the user had picked while the list is reloaded', () => {
        expect(sessionToRestore('2', ['1', '2'])).toBe('2');
        expect(sessionToRestore('3', ['1', '2'])).toBe('');
    });
});
