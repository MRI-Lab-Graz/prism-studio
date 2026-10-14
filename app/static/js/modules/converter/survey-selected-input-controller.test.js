import { describe, expect, it } from 'vitest';

import { createSurveySelectedInputController } from './survey-selected-input-controller.js';

describe('survey selected input (server-picked file)', () => {
    it.each([
        ['C:\\Users\\me\\data\\survey.xlsx', 'survey.xlsx'],
        ['/home/me/data/survey.csv', 'survey.csv'],
    ])('uses the last path segment of %s as filename', (path, name) => {
        const controller = createSurveySelectedInputController({ getConvertServerFilePath: () => path });
        expect(controller.getSelectedSurveyFilename()).toBe(name);
    });
});
