import { describe, expect, it } from 'vitest';

import {
    MISSING_MEANING,
    POLICY,
    applyPolicyToScore,
    describeMissingHandling,
    describeReverseCoding,
    policyFromScore,
} from './missing-data.js';

describe('policyFromScore', () => {
    it('defaults to using whatever was answered', () => {
        expect(policyFromScore({ Name: 'a', Method: 'sum', Items: ['x', 'y'] })).toEqual({
            policy: POLICY.USE_ANSWERED,
            minValid: null,
        });
    });

    it('reads MinValid as "require at least N"', () => {
        expect(policyFromScore({ Items: ['x', 'y', 'z'], MinValid: 2 })).toEqual({
            policy: POLICY.REQUIRE_N,
            minValid: 2,
        });
    });

    it('reads Missing=require_all (and its aliases) as "require all"', () => {
        ['require_all', 'all', 'strict'].forEach((alias) => {
            expect(policyFromScore({ Missing: alias }).policy).toBe(POLICY.REQUIRE_ALL);
        });
    });
});

describe('applyPolicyToScore', () => {
    const base = { Name: 'a', Method: 'sum', Items: ['x', 'y', 'z'], Description: 'keep me' };

    it('use answered: no Missing/MinValid', () => {
        const score = applyPolicyToScore({ ...base, MinValid: 2, Missing: 'require_all' }, {
            policy: POLICY.USE_ANSWERED,
            minValid: null,
        });
        expect(score).toEqual(base);
    });

    it('require N: sets MinValid and clears Missing', () => {
        const score = applyPolicyToScore({ ...base, Missing: 'require_all' }, {
            policy: POLICY.REQUIRE_N,
            minValid: 2,
        });
        expect(score).toEqual({ ...base, MinValid: 2 });
    });

    it('require all: sets Missing=require_all and clears MinValid', () => {
        const score = applyPolicyToScore({ ...base, MinValid: 2 }, {
            policy: POLICY.REQUIRE_ALL,
            minValid: null,
        });
        expect(score).toEqual({ ...base, Missing: 'require_all' });
    });

    it('does not mutate its input and keeps unrelated fields', () => {
        const input = { ...base, Range: { min: 0, max: 15 } };
        const before = JSON.stringify(input);
        applyPolicyToScore(input, { policy: POLICY.REQUIRE_N, minValid: 1 });
        expect(JSON.stringify(input)).toBe(before);
        expect(applyPolicyToScore(input, { policy: POLICY.USE_ANSWERED, minValid: null }).Range).toEqual({
            min: 0,
            max: 15,
        });
    });
});

describe('describeMissingHandling', () => {
    it('sum over answered items says it is lower than a complete response', () => {
        const text = describeMissingHandling({ method: 'sum', itemCount: 5, policy: POLICY.USE_ANSWERED });
        expect(text).toMatch(/answered items/);
        expect(text).toMatch(/3 of 5/);
        expect(text).toMatch(/lower/);
    });

    it('mean over answered items', () => {
        const text = describeMissingHandling({ method: 'mean', itemCount: 4, policy: POLICY.USE_ANSWERED });
        expect(text).toMatch(/mean of the answered items/i);
    });

    it('require N names the threshold and the empty result', () => {
        const text = describeMissingHandling({
            method: 'sum',
            itemCount: 5,
            policy: POLICY.REQUIRE_N,
            minValid: 4,
        });
        expect(text).toMatch(/at least 4 of 5/);
        expect(text).toMatch(/left empty/i);
    });

    it('require all names the item count', () => {
        const text = describeMissingHandling({ method: 'mean', itemCount: 5, policy: POLICY.REQUIRE_ALL });
        expect(text).toMatch(/all 5 items/);
        expect(text).toMatch(/left empty/i);
    });

    it('formula scores are always empty when an item is missing, whatever the policy', () => {
        const text = describeMissingHandling({ method: 'formula', itemCount: 3, policy: POLICY.USE_ANSWERED });
        expect(text).toMatch(/any item.*missing/i);
        expect(text).toMatch(/left empty/i);
    });

    it('a single-item score has nothing to average or sum over', () => {
        const text = describeMissingHandling({ method: 'sum', itemCount: 1, policy: POLICY.USE_ANSWERED });
        expect(text).toMatch(/left empty/i);
    });

    it('has no items yet', () => {
        expect(describeMissingHandling({ method: 'sum', itemCount: 0, policy: POLICY.USE_ANSWERED })).toMatch(
            /no items/i
        );
    });
});

describe('describeReverseCoding', () => {
    it('says nothing is reversed when nothing is', () => {
        expect(describeReverseCoding([], [])).toMatch(/no items are reverse-coded/i);
    });

    it('lists the reversed items', () => {
        const text = describeReverseCoding(['WB02', 'WB04'], []);
        expect(text).toMatch(/2 items/);
        expect(text).toMatch(/WB02, WB04/);
    });

    it('warns about items whose scale range is unknown', () => {
        const text = describeReverseCoding(['WB02'], ['WB02']);
        expect(text).toMatch(/not reversed/i);
        expect(text).toMatch(/MinValue\/MaxValue/);
    });
});

describe('MISSING_MEANING', () => {
    it('states what counts as a missing answer', () => {
        expect(MISSING_MEANING).toMatch(/empty/);
        expect(MISSING_MEANING).toMatch(/n\/a/);
        expect(MISSING_MEANING).toMatch(/not a number/);
    });
});
