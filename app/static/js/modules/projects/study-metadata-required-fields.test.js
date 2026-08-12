import { describe, expect, it } from 'vitest';

import {
    DEFAULT_REQUIRED_FIELDS_SCHEMA,
    normalizeRequiredFieldsSchema,
} from './study-metadata-required-fields.js';

describe('normalizeRequiredFieldsSchema', () => {
    it('converts the backend-served section->array shape into section->Set', () => {
        const fromApi = {
            Basics: ['EthicsApprovals', 'Funding', 'Keywords'],
            Overview: [],
            StudyDesign: ['Type'],
            Recruitment: ['Method'],
            Eligibility: ['InclusionCriteria'],
            Procedure: ['Overview'],
        };

        const schema = normalizeRequiredFieldsSchema(fromApi);

        expect(schema.Recruitment).toEqual(new Set(['Method']));
        expect(schema.Recruitment.has('Location')).toBe(false);
        expect(schema.Overview).toEqual(new Set());
        expect(schema.Basics).toEqual(new Set(['EthicsApprovals', 'Funding', 'Keywords']));
    });

    it('falls back to the built-in default schema when given null/undefined (offline)', () => {
        expect(normalizeRequiredFieldsSchema(null)).toEqual(DEFAULT_REQUIRED_FIELDS_SCHEMA);
        expect(normalizeRequiredFieldsSchema(undefined)).toEqual(DEFAULT_REQUIRED_FIELDS_SCHEMA);
    });

    it('falls back per-section when a section is missing or malformed', () => {
        const schema = normalizeRequiredFieldsSchema({ Recruitment: 'not-an-array' });

        expect(schema.Recruitment).toEqual(DEFAULT_REQUIRED_FIELDS_SCHEMA.Recruitment);
        expect(schema.Basics).toEqual(DEFAULT_REQUIRED_FIELDS_SCHEMA.Basics);
    });

    it('default schema keeps Recruitment to Method only, matching the CORE badge in the template', () => {
        expect(DEFAULT_REQUIRED_FIELDS_SCHEMA.Recruitment).toEqual(new Set(['Method']));
        expect(DEFAULT_REQUIRED_FIELDS_SCHEMA.Overview).toEqual(new Set());
    });
});
