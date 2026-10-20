import { describe, expect, it } from 'vitest';

import { reviewFormData } from './survey-session-assignments.js';

describe('reviewFormData', () => {
    it('sends the picked server path when no file was uploaded', () => {
        const form = reviewFormData({ file: null, serverPath: '/data/a.lsa', idColumn: 'token' });
        expect(form.get('source_file_path')).toBe('/data/a.lsa');
        expect(form.get('id_column')).toBe('token');
        expect(form.get('file')).toBeNull();
    });

    it('prefers an uploaded file over the server path', () => {
        const file = new File(['x'], 'a.csv');
        const form = reviewFormData({ file, serverPath: '/data/a.lsa', idColumn: 'id' });
        expect(form.get('file').name).toBe('a.csv');
        expect(form.get('source_file_path')).toBeNull();
    });

    it('returns null until a file (or path) and an ID column are chosen', () => {
        expect(reviewFormData({ file: null, serverPath: '', idColumn: 'token' })).toBeNull();
        expect(reviewFormData({ file: null, serverPath: '/data/a.lsa', idColumn: '' })).toBeNull();
    });
});
