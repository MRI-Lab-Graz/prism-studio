import { describe, expect, it } from 'vitest';

import { groupTemplatesByCategory } from './group-by-category.js';

const ORDER = ['Mood, Anxiety & Clinical Screening', 'Well-being & Life Satisfaction', 'Other / Uncategorized'];

function file(name, category) {
    return { filename: name, study: { Category: category } };
}

describe('groupTemplatesByCategory', () => {
    it('groups files under their category, in fixed category order', () => {
        const files = [
            file('survey-swls.json', 'Well-being & Life Satisfaction'),
            file('survey-aai.json', 'Mood, Anxiety & Clinical Screening'),
            file('survey-who5.json', 'Well-being & Life Satisfaction'),
        ];

        const groups = groupTemplatesByCategory(files, ORDER);

        expect(groups.map((g) => g.category)).toEqual([
            'Mood, Anxiety & Clinical Screening',
            'Well-being & Life Satisfaction',
        ]);
        expect(groups[0].files.map((f) => f.filename)).toEqual(['survey-aai.json']);
        expect(groups[1].files.map((f) => f.filename)).toEqual(['survey-swls.json', 'survey-who5.json']);
    });

    it('omits categories with no files instead of rendering an empty group', () => {
        const files = [file('survey-aai.json', 'Mood, Anxiety & Clinical Screening')];

        const groups = groupTemplatesByCategory(files, ORDER);

        expect(groups).toHaveLength(1);
    });

    it('folds files with a missing or unrecognized category into the last (fallback) group', () => {
        const files = [
            file('survey-legacy.json', ''),
            file('survey-custom.json', 'Not A Real Category'),
            { filename: 'survey-no-study.json' },
        ];

        const groups = groupTemplatesByCategory(files, ORDER);

        expect(groups).toHaveLength(1);
        expect(groups[0].category).toBe('Other / Uncategorized');
        expect(groups[0].files.map((f) => f.filename)).toEqual([
            'survey-legacy.json',
            'survey-custom.json',
            'survey-no-study.json',
        ]);
    });

    it('also works for biometrics-style slug categories, not just survey category names', () => {
        const order = ['cardiorespiratory', 'muscular-strength', ''];
        const files = [
            file('biometrics-fitness.json', 'cardiorespiratory'),
            file('biometrics-grip.json', 'muscular-strength'),
        ];

        const groups = groupTemplatesByCategory(files, order);

        expect(groups.map((g) => g.category)).toEqual(['cardiorespiratory', 'muscular-strength']);
    });
});
