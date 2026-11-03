import { describe, expect, it } from 'vitest';

import { splitRecent } from './recent-projects.js';

const projects = (n) => Array.from({ length: n }, (_, i) => ({ path: `/p${i}` }));

describe('splitRecent', () => {
    it('shows the first five and puts the rest in the older list', () => {
        const { shown, older } = splitRecent(projects(8));
        expect(shown.map((p) => p.path)).toEqual(['/p0', '/p1', '/p2', '/p3', '/p4']);
        expect(older.map((p) => p.path)).toEqual(['/p5', '/p6', '/p7']);
    });
    it('has no older list for five or fewer', () => {
        expect(splitRecent(projects(5)).older).toEqual([]);
        expect(splitRecent(projects(2)).shown).toHaveLength(2);
    });
});
