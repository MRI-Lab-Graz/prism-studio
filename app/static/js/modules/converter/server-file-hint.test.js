import { describe, expect, it } from 'vitest';

import { serverFileHintText } from './server-file-hint.js';

describe('serverFileHintText', () => {
    it('shows the picked server path', () => {
        expect(serverFileHintText('C:\\data\\survey.xlsx')).toBe('Server file: C:\\data\\survey.xlsx');
    });
});
