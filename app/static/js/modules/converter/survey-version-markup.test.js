import { describe, expect, it } from 'vitest';

import { buildVariantDefinitionBadges, buildVersionOptions } from './survey-version-markup.js';

const EVIL = '<img src=x onerror=alert(1)>';

describe('buildVariantDefinitionBadges', () => {
    it('escapes template-controlled VariantID, ItemCount and ScaleType', () => {
        const html = buildVariantDefinitionBadges(
            [{ VariantID: EVIL, ItemCount: EVIL, ScaleType: EVIL }],
            'other'
        );
        expect(html).not.toContain('<img');
        expect(html).toContain('&lt;img');
    });

    it('marks the selected variant active and ignores junk entries', () => {
        const html = buildVariantDefinitionBadges(
            [{ VariantID: 'short', ItemCount: 5 }, null, { VariantID: '' }],
            'short'
        );
        expect(html).toContain('survey-version-variant-badge-active');
        expect(html).toContain('short, 5 items');
        expect(html.match(/<span/g)).toHaveLength(1);
    });

    it('returns an empty string without definitions', () => {
        expect(buildVariantDefinitionBadges(undefined, 'x')).toBe('');
        expect(buildVariantDefinitionBadges([], 'x')).toBe('');
    });
});

describe('buildVersionOptions', () => {
    it('escapes version labels in both value and text and selects the chosen one', () => {
        const html = buildVersionOptions([EVIL, 'long'], 'long');
        expect(html).not.toContain('<img');
        expect(html).toContain('value="long" selected');
    });
});
