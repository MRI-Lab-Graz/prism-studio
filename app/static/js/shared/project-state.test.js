import { describe, expect, it } from 'vitest';

import { isSameProjectPath, normalizeProjectPathForCompare } from './project-state.js';

describe('project path identity', () => {
    it('treats the Windows and posix spelling of one project as the same project', () => {
        // This is the exact pair that stranded the study metadata form: the
        // browser holds the forward-slash form, the server answers with
        // str(Path(...)) - the backslash form - and the mismatch made an
        // in-flight load look stale, so the form never unlocked.
        expect(isSameProjectPath('C:/Users/karl/proj', 'C:\\Users\\karl\\proj')).toBe(true);
    });

    it('ignores trailing separators and surrounding whitespace', () => {
        expect(isSameProjectPath('/data/study', '/data/study/')).toBe(true);
        expect(isSameProjectPath('  /data/study  ', '/data/study')).toBe(true);
        expect(isSameProjectPath('C:\\data\\study\\', 'C:/data/study')).toBe(true);
    });

    it('still tells genuinely different projects apart', () => {
        expect(isSameProjectPath('/data/study-a', '/data/study-b')).toBe(false);
        expect(isSameProjectPath('/data/study', '/data/study/sub')).toBe(false);
    });

    it('does not fold case, because posix paths are case-sensitive', () => {
        expect(isSameProjectPath('/data/Study', '/data/study')).toBe(false);
    });

    it('treats empty and missing values as equal and normalizes to an empty string', () => {
        expect(normalizeProjectPathForCompare(null)).toBe('');
        expect(normalizeProjectPathForCompare(undefined)).toBe('');
        expect(isSameProjectPath('', null)).toBe(true);
    });

    it('does not collapse a posix root to an empty string', () => {
        expect(isSameProjectPath('/', '')).toBe(false);
    });
});
