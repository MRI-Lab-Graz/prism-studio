import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { FIELD_LABELS, LICENSE_FIRST, QUESTIONNAIRE_SECTIONS, assignFields, isMissing } from './questionnaire-sections.js';

const schema = JSON.parse(readFileSync(new URL('../../../schemas/stable/survey.schema.json', import.meta.url), 'utf8'));
const schemaFields = ['Technical', 'Study', 'Metadata', 'I18n'].flatMap((section) =>
    Object.keys(schema.properties[section].properties).map((field) => `${section}/${field}`),
);
const NOWHERE = ['Technical/StimulusType', 'Technical/FileFormat'];

describe('assignFields', () => {
    it('puts every field of the survey schema in exactly one section, except the single-value ones', () => {
        const placed = [...assignFields(schemaFields).values()].flat();
        expect(placed.sort()).toEqual(schemaFields.filter((f) => !NOWHERE.includes(f)).sort());
    });

    it('lists the sections in order and keeps each field in its section', () => {
        const map = assignFields(schemaFields);
        expect([...map.keys()]).toEqual(QUESTIONNAIRE_SECTIONS.map((s) => s.id));
        expect(map.get('identity')).toContain('Study/TaskName');
        expect(map.get('administration')).toEqual(expect.arrayContaining(['Technical/Respondent', 'Technical/Language']));
        expect(map.get('languages')).toEqual(['I18n/Languages', 'I18n/DefaultLanguage', 'I18n/TranslationMethod']);
    });

    it('never hides a field the map does not know: it lands in Advanced', () => {
        expect(assignFields([...schemaFields, 'Study/NewThing']).get('advanced')).toContain('Study/NewThing');
    });
});

describe('isMissing', () => {
    it.each([undefined, null, '', '  ', [], { en: '', de: 'x' }, { de: 'x' }])('%j is missing', (value) => {
        expect(isMissing(value)).toBe(true);
    });

    it.each(['x', { en: 'x' }, 0, false, ['a']])('%j is filled in', (value) => {
        expect(isMissing(value)).toBe(false);
    });
});

describe('labels', () => {
    it('names the fields people stumble over', () => {
        expect(FIELD_LABELS['Study/TaskName']).toBe('File ID (e.g. phq9)');
        expect(FIELD_LABELS['ITEM/ApplicableVersions']).toBe('Used in forms');
        expect(LICENSE_FIRST).toEqual(['CC-BY-4.0', 'CC0-1.0', 'Proprietary']);
    });
});
