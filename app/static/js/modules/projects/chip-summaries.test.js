import { describe, expect, it } from 'vitest';

import { criterionSummary, knownIssueChipText, missingFilesChipText } from './chip-summaries.js';

describe('knownIssueChipText', () => {
    it('shows "file | issue" as "file – issue" and leaves a single field alone', () => {
        expect(knownIssueChipText('sub-02_bold.nii | Shorter scan')).toBe('sub-02_bold.nii – Shorter scan');
        expect(knownIssueChipText('only a note')).toBe('only a note');
    });
});

describe('missingFilesChipText', () => {
    it('joins what is filled, with the reason as a readable label and the detail in brackets', () => {
        expect(missingFilesChipText('sub-01 | ses-01 | func | motion_artifact | excessive movement'))
            .toBe('sub-01 · ses-01 · func · Motion artifact (excessive movement)');
    });
    it('skips empty parts and keeps an unknown reason as written', () => {
        expect(missingFilesChipText('sub-01 |  |  | other')).toBe('sub-01 · Other');
        expect(missingFilesChipText('sub-01 | | | something_new')).toBe('sub-01 · something_new');
    });
});

describe('criterionSummary', () => {
    it('numeric: label, mode and the range with its unit', () => {
        expect(criterionSummary({ label: 'Age', mode: 'include', min: 18, max: 35, unit: 'years' }))
            .toBe('Age · include 18–35 years');
    });
    it('numeric with one open end', () => {
        expect(criterionSummary({ label: 'IQ', mode: 'include', min: 85, unit: 'points' })).toBe('IQ · include ≥ 85 points');
        expect(criterionSummary({ label: 'IQ', mode: 'exclude', max: 69 })).toBe('IQ · exclude ≤ 69');
    });
    it('categorical: the labels', () => {
        expect(criterionSummary({ label: 'Sex', mode: 'exclude', type: 'categorical', values: ['Male', 'Other'] }))
            .toBe('Sex · exclude Male, Other');
    });
});
