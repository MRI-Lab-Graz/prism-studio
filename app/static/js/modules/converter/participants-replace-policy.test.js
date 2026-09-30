import { describe, expect, it } from 'vitest';

import {
    REPLACE_CONFIRMATION_MESSAGE,
    discardsExistingSchema,
} from './participants-replace-policy.js';

describe('participants Replace policy', () => {
    it('Replace with an existing participants.tsv starts from a clean annotation state', () => {
        expect(
            discardsExistingSchema({ mode: 'file', fileAction: 'replace', hasParticipantsTsv: true })
        ).toBe(true);
    });

    it('Replace without a participants.tsv keeps a draft schema saved earlier', () => {
        expect(
            discardsExistingSchema({ mode: 'file', fileAction: 'replace', hasParticipantsTsv: false })
        ).toBe(false);
    });

    it('Merge keeps the existing annotations', () => {
        expect(
            discardsExistingSchema({ mode: 'file', fileAction: 'merge', hasParticipantsTsv: true })
        ).toBe(false);
    });

    it('Modify edits the existing files, so it keeps their annotations', () => {
        expect(
            discardsExistingSchema({ mode: 'existing', fileAction: 'replace', hasParticipantsTsv: true })
        ).toBe(false);
    });

    it('the confirmation names everything that is discarded', () => {
        expect(REPLACE_CONFIRMATION_MESSAGE).toMatch(/participants\.tsv/);
        expect(REPLACE_CONFIRMATION_MESSAGE).toMatch(/participants\.json/);
        expect(REPLACE_CONFIRMATION_MESSAGE).toMatch(/annotations/i);
    });
});
