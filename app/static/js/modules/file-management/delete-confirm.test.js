import { describe, expect, it } from 'vitest';

import { deleteConfirmMessage } from './delete-confirm.js';

describe('deleteConfirmMessage', () => {
    it('states how many files are about to be deleted', () => {
        const message = deleteConfirmMessage({ count: 2, everything: false });
        expect(message).toContain('2 files');
        expect(message).toContain('cannot be undone');
    });

    it('uses the singular for one file', () => {
        expect(deleteConfirmMessage({ count: 1, everything: false })).toContain('1 file ');
    });

    it('mentions orphaned sidecars that go with them', () => {
        expect(deleteConfirmMessage({ count: 3, sidecars: 2, everything: false })).toContain('2 orphaned sidecar');
    });

    it('says plainly that EVERYTHING goes when every subject is selected with no filter', () => {
        const message = deleteConfirmMessage({ count: 40, everything: true });
        expect(message).toContain('EVERY file');
        expect(message).toContain('40');
        expect(message).toMatch(/all subjects/i);
    });

    it('does not shout about everything when the user narrowed it down', () => {
        expect(deleteConfirmMessage({ count: 40, everything: false })).not.toContain('EVERY');
    });
});
