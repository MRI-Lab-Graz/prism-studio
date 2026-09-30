import { describe, expect, it } from 'vitest';

import {
    REPLACE_CONFIRMATION_MESSAGE,
    discardsExistingSchema,
    effectiveSelectedCase,
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


describe('effectiveSelectedCase', () => {
    const existing = { requiresSelection: true, availableCases: ['1', '2', '3'] };

    it('an unchosen default is not a choice when the user must pick a workflow', () => {
        expect(effectiveSelectedCase({ ...existing, selectedCaseId: '1', chosenCaseId: '' })).toBe(null);
    });

    it('keeps the workflow the user picked', () => {
        expect(effectiveSelectedCase({ ...existing, selectedCaseId: '2', chosenCaseId: '2' })).toBe('2');
    });

    it('drops a pick that is no longer available', () => {
        expect(
            effectiveSelectedCase({
                requiresSelection: true,
                availableCases: ['1'],
                selectedCaseId: '3',
                chosenCaseId: '3',
            })
        ).toBe(null);
    });

    it('a selection that differs from the recorded pick is not a choice', () => {
        expect(effectiveSelectedCase({ ...existing, selectedCaseId: '1', chosenCaseId: '2' })).toBe(null);
    });
});
