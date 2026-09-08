import { describe, expect, it } from 'vitest';

import {
    MISSING_FILE_REASON_OPTIONS,
    combineMissingFilesRow,
    parseMissingFilesValue,
} from './missing-files-row.js';

describe('parseMissingFilesValue', () => {
    it('parses a fully-specified five-field line', () => {
        const rows = parseMissingFilesValue(
            'sub-01 | ses-01 | func | motion_artifact | excessive movement'
        );

        expect(rows).toEqual([
            {
                subject: 'sub-01',
                session: 'ses-01',
                modality: 'func',
                reason: 'motion_artifact',
                detail: 'excessive movement',
            },
        ]);
    });

    it('pads a legacy two-field line (subject/session id | what is missing)', () => {
        const rows = parseMissingFilesValue('sub-002, ses-2 | T1w missing');

        expect(rows).toEqual([
            {
                subject: 'sub-002, ses-2',
                session: 'T1w missing',
                modality: '',
                reason: '',
                detail: '',
            },
        ]);
    });

    it('returns an empty array for blank input', () => {
        expect(parseMissingFilesValue('')).toEqual([]);
        expect(parseMissingFilesValue('   \n  ')).toEqual([]);
        expect(parseMissingFilesValue(undefined)).toEqual([]);
    });

    it('parses multiple lines into multiple rows', () => {
        const rows = parseMissingFilesValue(
            'sub-01 | ses-01 | func | motion_artifact | \nsub-02 | | eeg | scanner_defect | broken cap'
        );

        expect(rows).toHaveLength(2);
        expect(rows[1]).toEqual({
            subject: 'sub-02',
            session: '',
            modality: 'eeg',
            reason: 'scanner_defect',
            detail: 'broken cap',
        });
    });
});

describe('combineMissingFilesRow', () => {
    it('joins all fields with " | "', () => {
        const line = combineMissingFilesRow({
            subject: 'sub-01',
            session: 'ses-01',
            modality: 'func',
            reason: 'motion_artifact',
            detail: 'excessive movement',
        });

        expect(line).toBe('sub-01 | ses-01 | func | motion_artifact | excessive movement');
    });

    it('trims trailing empty fields', () => {
        const line = combineMissingFilesRow({
            subject: 'sub-01',
            session: 'ses-01',
            modality: '',
            reason: '',
            detail: '',
        });

        expect(line).toBe('sub-01 | ses-01');
    });

    it('returns an empty string when every field is empty', () => {
        expect(combineMissingFilesRow({})).toBe('');
        expect(combineMissingFilesRow()).toBe('');
    });

    it('round-trips through parseMissingFilesValue', () => {
        const original = {
            subject: 'sub-03',
            session: '',
            modality: 'anat',
            reason: 'other',
            detail: 'artifact from dental implant',
        };

        const [parsed] = parseMissingFilesValue(combineMissingFilesRow(original));

        expect(parsed).toEqual(original);
    });
});

describe('MISSING_FILE_REASON_OPTIONS', () => {
    it('includes the common missing-data causes', () => {
        const values = MISSING_FILE_REASON_OPTIONS.map(o => o.value);

        expect(values).toEqual(
            expect.arrayContaining([
                'motion_artifact',
                'scanner_defect',
                'task_not_understood',
                'other',
            ])
        );
    });
});
