import { describe, expect, it } from 'vitest';

import { applyPrimaryLanguage, needsPrimaryLanguage } from './primary-language.js';

const plain = () => ({
    Technical: { StimulusType: 'Questionnaire', Language: '' },
    Study: { TaskName: 'arsq', Instructions: 'Bitte antworten Sie', Description: 'Imported from Pavlovia survey: ARSQ' },
    ARSQ1: { Description: 'Ich hatte Gedanken', Levels: { 1: 'nie', 2: 'oft' }, Mandatory: false },
    ARSQ2: { Description: 'Ich fühlte mich unruhig' },
});

describe('needsPrimaryLanguage', () => {
    it('is true for a template with items and no language', () => {
        expect(needsPrimaryLanguage(plain())).toBe(true);
        const noTechnical = plain();
        delete noTechnical.Technical.Language;
        expect(needsPrimaryLanguage(noTechnical)).toBe(true);
    });

    it('is false once a language is set, and for no template or an empty one', () => {
        const done = plain();
        done.Technical.Language = 'de';
        expect(needsPrimaryLanguage(done)).toBe(false);
        expect(needsPrimaryLanguage(null)).toBe(false);
        expect(needsPrimaryLanguage({ Technical: {}, Study: {} })).toBe(false);
    });
});

describe('applyPrimaryLanguage', () => {
    it('keys every item text and level under the language and sets Technical.Language', () => {
        const template = plain();
        applyPrimaryLanguage(template, 'de');
        expect(template.Technical.Language).toBe('de');
        expect(template.ARSQ1.Description).toEqual({ de: 'Ich hatte Gedanken' });
        expect(template.ARSQ1.Levels).toEqual({ 1: { de: 'nie' }, 2: { de: 'oft' } });
        expect(template.ARSQ2.Description).toEqual({ de: 'Ich fühlte mich unruhig' });
    });

    it('does the same for the Study texts', () => {
        const template = plain();
        applyPrimaryLanguage(template, 'de');
        expect(template.Study.Instructions).toEqual({ de: 'Bitte antworten Sie' });
        expect(template.Study.Description).toEqual({ de: 'Imported from Pavlovia survey: ARSQ' });
        expect(template.Study.TaskName).toBe('arsq'); // identifiers stay plain
    });

    it('leaves texts that already have languages, and non-text fields, alone', () => {
        const template = plain();
        template.ARSQ2.Description = { en: 'I felt restless' };
        applyPrimaryLanguage(template, 'de');
        expect(template.ARSQ2.Description).toEqual({ en: 'I felt restless' });
        expect(template.ARSQ1.Mandatory).toBe(false);
    });

    it('rejects a code that is not a language code', () => {
        expect(() => applyPrimaryLanguage(plain(), 'german')).toThrow(/language code/);
        expect(() => applyPrimaryLanguage(plain(), 'DE')).toThrow(/language code/);
        expect(applyPrimaryLanguage(plain(), 'de-AT').Technical.Language).toBe('de-AT');
    });
});
