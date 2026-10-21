import { describe, expect, it } from 'vitest';

import {
    appendScreeningOnlyIds,
    defaultScreeningTicks,
    needsScreeningChoice,
    screeningRowsHtml,
} from './participants-screening-only.js';

const rows = [
    { participant_id: 'sub-1', has_folder: true, group: 'control' },
    { participant_id: 'sub-2', has_folder: false, group: '' },
    { participant_id: 'sub-3', has_folder: true, group: 'screening-only' },
];

describe('participants screening-only choice', () => {
    it('ticks the participants without a sub-folder by default', () => {
        expect([...defaultScreeningTicks(rows)]).toEqual(['sub-2']);
    });

    it('is only offered when someone has no folder or is already screening-only', () => {
        expect(needsScreeningChoice(rows)).toBe(true);
        expect(needsScreeningChoice([rows[0]])).toBe(false);
        expect(needsScreeningChoice([])).toBe(false);
    });

    it('shows the current group so an overwrite is no surprise', () => {
        const html = screeningRowsHtml([rows[0]], new Set(['sub-1']));
        expect(html).toContain('control');
        expect(html).toMatch(/data-screening-id="sub-1"[^>]*checked/);
    });

    it('sends the ticked ids, and nothing when no choice was offered', () => {
        const withChoice = new FormData();
        appendScreeningOnlyIds(withChoice, new Set(['sub-2']));
        expect(JSON.parse(withChoice.get('screening_only_ids'))).toEqual(['sub-2']);

        const noChoice = new FormData();
        appendScreeningOnlyIds(noChoice, null);
        expect(noChoice.has('screening_only_ids')).toBe(false);
    });

    it('sends an empty list when everything was unticked', () => {
        const form = new FormData();
        appendScreeningOnlyIds(form, new Set());
        expect(JSON.parse(form.get('screening_only_ids'))).toEqual([]);
    });
});
