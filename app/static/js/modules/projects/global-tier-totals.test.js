import { describe, expect, it } from 'vitest';

import { computeGlobalTierTotals, computeGroupTierTotals, sectionKeyFromBadgeId } from './global-tier-totals.js';

function section({ required_total = 0, required_filled = 0, optional_total = 0, optional_filled = 0, fields = [] }) {
    return { required_total, required_filled, optional_total, optional_filled, fields };
}

describe('computeGlobalTierTotals', () => {
    it('sums CORE and FAIR totals across every section', () => {
        const sections = {
            Basics: section({ required_total: 3, required_filled: 1, optional_total: 5, optional_filled: 2 }),
            StudyDesign: section({ required_total: 1, required_filled: 1, optional_total: 2, optional_filled: 0 }),
        };

        const totals = computeGlobalTierTotals(sections);

        expect(totals.coreTotal).toBe(4);
        expect(totals.coreFilled).toBe(2);
        expect(totals.fairTotal).toBe(7);
        expect(totals.fairFilled).toBe(2);
    });

    it('counts creation-blocking (REQUIRED-tier) fields separately from CORE, across sections', () => {
        const sections = {
            Basics: section({
                fields: [
                    { name: 'Name', filled: true, blocksCreation: true },
                    { name: 'Authors', filled: false, blocksCreation: true },
                    { name: 'Keywords', filled: true, blocksCreation: false },
                ],
            }),
            Overview: section({ fields: [{ name: 'Main', filled: false, blocksCreation: false }] }),
        };

        const totals = computeGlobalTierTotals(sections);

        expect(totals.blockingTotal).toBe(2);
        expect(totals.blockingFilled).toBe(1);
    });

    it('returns all zeros for an empty or missing sections map', () => {
        expect(computeGlobalTierTotals({})).toEqual({
            blockingTotal: 0, blockingFilled: 0,
            coreTotal: 0, coreFilled: 0,
            fairTotal: 0, fairFilled: 0,
        });
        expect(computeGlobalTierTotals(undefined)).toEqual({
            blockingTotal: 0, blockingFilled: 0,
            coreTotal: 0, coreFilled: 0,
            fairTotal: 0, fairFilled: 0,
        });
    });

    it('tolerates a section with no fields array (read-only/auto sections)', () => {
        const sections = { MissingData: section({ required_total: 0, optional_total: 3, optional_filled: 1 }) };
        delete sections.MissingData.fields;

        expect(() => computeGlobalTierTotals(sections)).not.toThrow();
        expect(computeGlobalTierTotals(sections).fairTotal).toBe(3);
    });
});

describe('sectionKeyFromBadgeId', () => {
    it('strips the sm prefix and Badge suffix used by section header badges', () => {
        expect(sectionKeyFromBadgeId('smBasicsBadge')).toBe('Basics');
        expect(sectionKeyFromBadgeId('smDiscoveryCitationBadge')).toBe('DiscoveryCitation');
    });

    it('returns an empty string for a falsy id instead of throwing', () => {
        expect(sectionKeyFromBadgeId('')).toBe('');
        expect(sectionKeyFromBadgeId(undefined)).toBe('');
    });
});

describe('computeGroupTierTotals', () => {
    it('sums only the given section keys, ignoring sections outside the group', () => {
        const sections = {
            Basics: section({ required_total: 3, required_filled: 1, optional_total: 5, optional_filled: 2 }),
            StudyDesign: section({ required_total: 1, required_filled: 1, optional_total: 2, optional_filled: 0 }),
            // Not in the requested key list - a "Core study setup" group must
            // not pick up Recruitment's numbers.
            Recruitment: section({ required_total: 1, required_filled: 0, optional_total: 4, optional_filled: 0 }),
        };

        const totals = computeGroupTierTotals(sections, ['Basics', 'StudyDesign']);

        expect(totals.coreTotal).toBe(4);
        expect(totals.coreFilled).toBe(2);
        expect(totals.fairTotal).toBe(7);
        expect(totals.fairFilled).toBe(2);
    });

    it('ignores a key that has no matching section (badge id for a field-level badge, not a section one)', () => {
        const sections = { Basics: section({ required_total: 1, required_filled: 1 }) };

        const totals = computeGroupTierTotals(sections, ['Basics', 'EligCriteriaRequired']);

        expect(totals.coreTotal).toBe(1);
        expect(totals.coreFilled).toBe(1);
    });

    it('returns all zeros for an empty key list', () => {
        const sections = { Basics: section({ required_total: 3, required_filled: 1 }) };

        expect(computeGroupTierTotals(sections, [])).toEqual({
            blockingTotal: 0, blockingFilled: 0,
            coreTotal: 0, coreFilled: 0,
            fairTotal: 0, fairFilled: 0,
        });
    });
});
