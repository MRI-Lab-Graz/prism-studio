/**
 * Plain-language rules for what a recipe does with missing answers and reverse
 * coding, plus the mapping between one friendly "if answers are missing" choice
 * and the recipe fields it stands for (Missing / MinValid).
 *
 * The wording must match what the scoring engine really does
 * (src/recipes_formula_engine.py: _calculate_scores):
 *  - sum/mean skip missing items unless MinValid / Missing=require_all stop it;
 *  - formula scores are empty when any item they use is missing;
 *  - a cell is missing when it is empty, "n/a" or not a number.
 */

export const POLICY = {
    USE_ANSWERED: 'use_answered',
    REQUIRE_N: 'require_n',
    REQUIRE_ALL: 'require_all',
};

export const MISSING_MEANING =
    'An answer counts as missing when the cell is empty, "n/a" or not a number.';

const REQUIRE_ALL_ALIASES = new Set(['require_all', 'all', 'strict']);

export function policyFromScore(score) {
    const missing = String((score && score.Missing) || '').trim().toLowerCase();
    if (REQUIRE_ALL_ALIASES.has(missing)) {
        return { policy: POLICY.REQUIRE_ALL, minValid: null };
    }
    const minValid = score && score.MinValid;
    if (Number.isInteger(minValid) && minValid > 0) {
        return { policy: POLICY.REQUIRE_N, minValid };
    }
    return { policy: POLICY.USE_ANSWERED, minValid: null };
}

export function applyPolicyToScore(score, { policy, minValid }) {
    const next = { ...score };
    delete next.Missing;
    delete next.MinValid;
    if (policy === POLICY.REQUIRE_ALL) {
        next.Missing = 'require_all';
    } else if (policy === POLICY.REQUIRE_N && Number.isInteger(minValid) && minValid > 0) {
        next.MinValid = minValid;
    }
    return next;
}

export function describeMissingHandling({ method, itemCount, policy, minValid }) {
    const n = Number(itemCount) || 0;
    if (n === 0) return 'No items in this score yet.';

    if (method === 'formula') {
        return 'Left empty (n/a) when any item used in the formula is missing.';
    }
    if (method !== 'sum' && method !== 'mean') {
        return 'Left empty (n/a) when the source item is missing.';
    }
    if (n === 1) return 'Left empty (n/a) when the item is unanswered.';

    if (policy === POLICY.REQUIRE_ALL) {
        return `Only computed when all ${n} items are answered; otherwise left empty (n/a).`;
    }
    if (policy === POLICY.REQUIRE_N) {
        const needed = Math.min(Math.max(Number(minValid) || 1, 1), n);
        return `Only computed when at least ${needed} of ${n} items are answered; otherwise left empty (n/a).`;
    }

    const example = Math.ceil(n / 2);
    if (method === 'mean') {
        return `Mean of the answered items. Someone who answered ${example} of ${n} items gets the mean of those ${example} items.`;
    }
    return (
        `Computed from the answered items only. Someone who answered ${example} of ${n} items gets ` +
        `the sum of those ${example} items, which is lower than a complete response.`
    );
}

export function describeReverseCoding(invertedItems, itemsWithoutRange) {
    const withoutRange = new Set(itemsWithoutRange || []);
    const reversed = (invertedItems || []).filter((item) => !withoutRange.has(item));
    const parts = [];
    if (reversed.length > 0) {
        parts.push(
            `${reversed.length} item${reversed.length === 1 ? '' : 's'} reverse-coded ` +
            `(${reversed.join(', ')}): the highest and lowest answers swap, using each item's scale range.`
        );
    }
    if (withoutRange.size > 0) {
        parts.push(
            `Not reversed because the template defines no scale range (MinValue/MaxValue): ` +
            `${[...withoutRange].join(', ')}.`
        );
    }
    return parts.length > 0 ? parts.join(' ') : 'No items are reverse-coded.';
}

/**
 * What the optional IRV (response variability) column does. Matches the engine
 * (src/recipes_formula_engine.py, method "irv"): the SAMPLE standard deviation of the
 * RAW answers (reverse coding is not applied), empty with fewer than 2 answered items.
 */
export function describeIrv(itemCount) {
    if (itemCount < 2) {
        return `IRV needs at least 2 items; this survey has ${itemCount}, so the column would stay empty.`;
    }
    return (
        `A column "IRV" is added: the sample standard deviation of one person's raw answers across all `
        + `${itemCount} items. 0 = the same answer to every question (possible straight-lining). `
        + `Reverse coding is ignored. The value is left empty when fewer than 2 items were answered.`
    );
}
