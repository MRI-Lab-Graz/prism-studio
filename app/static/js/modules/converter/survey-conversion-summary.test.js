import { describe, expect, it } from 'vitest';

import { isTemplateMatchConverted } from './survey-conversion-summary.js';

describe('isTemplateMatchConverted', () => {
    const tasks = [{ task: 'stress' }, { task: 'who5' }];

    it('is true when the survey group or its template is one of the converted tasks', () => {
        expect(isTemplateMatchConverted('Stress', { template_key: 'x' }, tasks)).toBe(true);
        expect(isTemplateMatchConverted('grp', { template_key: 'WHO5' }, tasks)).toBe(true);
    });

    it('is false for groups found in the file that have no data to convert', () => {
        expect(isTemplateMatchConverted('ads', { template_key: 'ads' }, tasks)).toBe(false);
    });
});
