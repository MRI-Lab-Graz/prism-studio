import { describe, expect, it } from 'vitest';

import { isPavloviaSurvey, parsePrismTemplateJson } from './json-import.js';

const SURVEY = {
    Technical: { StimulusType: 'Questionnaire' },
    Study: { TaskName: 'wellbeing', OriginalName: { en: 'Wellbeing' } },
    WB01: { Description: { en: 'I felt cheerful' }, MinValue: 0, MaxValue: 5 },
};
const BIOMETRICS = {
    Study: { BiometricName: 'fitness', OriginalName: 'Fitness battery' },
    resting_hr: { Description: 'Resting heart rate' },
};

const text = (value) => JSON.stringify(value);

describe('parsePrismTemplateJson', () => {
    it('returns the parsed survey template', () => {
        expect(parsePrismTemplateJson(text(SURVEY), 'survey')).toEqual(SURVEY);
    });

    it('returns the parsed biometrics template', () => {
        expect(parsePrismTemplateJson(text(BIOMETRICS), 'biometrics')).toEqual(BIOMETRICS);
    });

    it('accepts a file that starts with a byte-order mark', () => {
        expect(parsePrismTemplateJson('﻿' + text(SURVEY), 'survey')).toEqual(SURVEY);
    });

    it('says so when the file is not valid JSON', () => {
        expect(() => parsePrismTemplateJson('{not json', 'survey')).toThrow(/not valid JSON/);
    });

    it('rejects JSON that is not an object', () => {
        expect(() => parsePrismTemplateJson('[1, 2]', 'survey')).toThrow(/not a PRISM template/);
        expect(() => parsePrismTemplateJson('"text"', 'survey')).toThrow(/not a PRISM template/);
    });

    it('rejects an object without a Study block', () => {
        expect(() => parsePrismTemplateJson(text({ WB01: { Description: 'x' } }), 'survey')).toThrow(
            /no Study block/
        );
        expect(() => parsePrismTemplateJson(text({ Study: 'x' }), 'survey')).toThrow(/no Study block/);
    });

    it('tells the user to switch modality when the template is for the other one', () => {
        expect(() => parsePrismTemplateJson(text(BIOMETRICS), 'survey')).toThrow(
            /biometrics template.*switch Modality to biometrics/i
        );
        expect(() => parsePrismTemplateJson(text(SURVEY), 'biometrics')).toThrow(
            /survey template.*switch Modality to survey/i
        );
    });

    it('leaves anything else to the editor validation', () => {
        const odd = { Study: { Name: 'no task name yet' } };
        expect(parsePrismTemplateJson(text(odd), 'survey')).toEqual(odd);
    });
});

describe('isPavloviaSurvey', () => {
    it('recognises a SurveyJS survey by its pages', () => {
        expect(isPavloviaSurvey(text({ title: 'x', pages: [{ name: 'p', elements: [] }] }))).toBe(true);
        expect(isPavloviaSurvey(text({ elements: [{ type: 'text', name: 'a' }] }))).toBe(true);
    });

    it('leaves PRISM templates, other JSON and broken JSON to the normal path', () => {
        expect(isPavloviaSurvey(text(SURVEY))).toBe(false);
        expect(isPavloviaSurvey(text([1, 2]))).toBe(false);
        expect(isPavloviaSurvey('not json')).toBe(false);
    });
});
