import { describe, expect, it } from 'vitest';

import { libraryMatchSummary, renderLibraryMatchCard } from './library-match-card.js';

const escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const EXACT = {
    template_key: 'ads', source: 'global', confidence: 'exact', paired: 2, imported_items: 2, library_items: 2,
    ids_identical: false, ids_conflict: false, adoptable: true, levels_ok: true, reworded: [],
    id_map: { ADS1_1: 'ads_01', ADS1_2: 'ads_02' }, unpaired_imported: [], unpaired_library: [],
};
const PARTIAL = { ...EXACT, confidence: 'medium', adoptable: false, paired: 1, unpaired_imported: ['ADS1_2'], unpaired_library: [] };

describe('libraryMatchSummary', () => {
    it('names the template, where it lives and how well it fits', () => {
        expect(libraryMatchSummary(EXACT)).toBe('match: ads (global, exact)');
        expect(libraryMatchSummary(null)).toBe('');
    });
});

describe('renderLibraryMatchCard', () => {
    it('offers the library template for an exact match and lists the ID mapping', () => {
        const html = renderLibraryMatchCard(EXACT, escapeHtml);
        expect(html).toContain('wording identical');
        expect(html).toContain('levels identical');
        expect(html).toContain('item IDs differ');
        expect(html).toContain('data-action="use-library"');
        expect(html).toContain('data-action="import-new"');
        expect(html).toContain('ADS1_1');
        expect(html).toContain('ads_01');
    });

    it('shows a partial match as information only', () => {
        const html = renderLibraryMatchCard(PARTIAL, escapeHtml);
        expect(html).not.toContain('data-action="use-library"');
        expect(html).toContain('data-action="import-new"');
        expect(html).toContain('1 imported item(s) without a match');
    });

    it('says how many items were reworded and escapes codes', () => {
        const html = renderLibraryMatchCard(
            { ...EXACT, confidence: 'high', reworded: [{ imported: '<b>x', library: 'y', similarity: 0.9 }], id_map: { '<b>x': 'y' } },
            escapeHtml,
        );
        expect(html).toContain('1 item(s) reworded');
        expect(html).toContain('&lt;b&gt;x');
        expect(html).not.toContain('<b>x');
    });

    it('renders nothing without a match', () => {
        expect(renderLibraryMatchCard(null, escapeHtml)).toBe('');
    });
});
