import { describe, expect, it } from 'vitest';

import { computeGlobalTierTotals } from './global-tier-totals.js';

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
