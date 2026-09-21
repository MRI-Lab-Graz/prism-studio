import { describe, expect, it } from 'vitest';

// validation.js touches `window` at module top-level (debug flag + legacy
// window.* exports), so it must be stubbed before a dynamic import.
globalThis.window = globalThis;
const { setRequiredFieldBorder } = await import('./validation.js');

function stubField() {
    const classes = new Set();
    return {
        classList: {
            add: (c) => classes.add(c),
            remove: (c) => classes.delete(c),
            contains: (c) => classes.has(c),
        },
        classes,
    };
}

function stubBadge(initialText, initialClasses = []) {
    const classes = new Set(initialClasses);
    return {
        textContent: initialText,
        classList: {
            add: (c) => classes.add(c),
            remove: (c) => classes.delete(c),
            contains: (c) => classes.has(c),
        },
        classes,
    };
}

describe('setRequiredFieldBorder', () => {
    it('marks a required/core field red when empty', () => {
        const field = stubField();
        setRequiredFieldBorder(field, false, false);
        expect(field.classes.has('required-field-empty')).toBe(true);
        expect(field.classes.has('required-field-filled')).toBe(false);
    });

    it('marks any field green when filled, regardless of tier', () => {
        const field = stubField();
        setRequiredFieldBorder(field, true, false);
        expect(field.classes.has('required-field-filled')).toBe(true);
        expect(field.classes.has('required-field-empty')).toBe(false);
    });

    it('never applies the alarming red border to an OPTIONAL field when empty', () => {
        const field = stubField();
        setRequiredFieldBorder(field, false, true);
        expect(field.classes.has('required-field-empty')).toBe(false);
        expect(field.classes.has('required-field-filled')).toBe(false);
    });

    it('an OPTIONAL field still turns green once filled', () => {
        const field = stubField();
        setRequiredFieldBorder(field, true, true);
        expect(field.classes.has('required-field-filled')).toBe(true);
        expect(field.classes.has('required-field-empty')).toBe(false);
    });
});

describe('updateBadgeColor', () => {
    it('gives an unfilled CORE badge a color distinct from the filled/success color', async () => {
        const { updateBadgeColor } = await import('./validation.js');
        const badge = stubBadge('CORE');

        updateBadgeColor(badge, false);
        expect(badge.classes.has('badge-tier-core')).toBe(true);
        expect(badge.classes.has('bg-success')).toBe(false);
        expect(badge.classes.has('bg-primary')).toBe(false);
    });

    it('turns a filled CORE badge bg-success and strips the tier color', async () => {
        const { updateBadgeColor } = await import('./validation.js');
        const badge = stubBadge('CORE');

        updateBadgeColor(badge, false);
        updateBadgeColor(badge, true);
        expect(badge.classes.has('bg-success')).toBe(true);
        expect(badge.classes.has('badge-tier-core')).toBe(false);
    });
});

// Minimal document stub: validation.js reaches the DOM only through
// getById()/querySelectorAll(), so a map-backed fake is enough and keeps the
// suite in the repo's existing `environment: 'node'` setup (no jsdom).
function stubDocument(elementsById) {
    globalThis.document = {
        getElementById: (id) => elementsById[id] || null,
        querySelectorAll: () => [],
    };
}

describe('isOptionalTierBadge', () => {
    it('treats a field with no tier badge as optional', async () => {
        const { isOptionalTierBadge } = await import('./validation.js');
        // Target Sample Size / Power Analysis and 15 other fields carry no
        // tier badge at all - they must never render as "missing".
        expect(isOptionalTierBadge(null)).toBe(true);
    });

    it('treats an OPTIONAL badge as optional and CORE/REQUIRED as not', async () => {
        const { isOptionalTierBadge } = await import('./validation.js');
        expect(isOptionalTierBadge(stubBadge('OPTIONAL'))).toBe(true);
        expect(isOptionalTierBadge(stubBadge('CORE'))).toBe(false);
        expect(isOptionalTierBadge(stubBadge('REQUIRED'))).toBe(false);
    });
});

describe('validateEligibilityCriteriaBadges', () => {
    function setupEligibility(inclusionText, exclusionText) {
        const inclusionField = { ...stubField(), value: inclusionText };
        const exclusionField = { ...stubField(), value: exclusionText };
        const coreBadge = stubBadge('CORE');
        const optionalBadge = stubBadge('OPTIONAL');
        stubDocument({
            smEligInclusion: inclusionField,
            smEligExclusion: exclusionField,
            smEligCriteriaRequiredBadge: coreBadge,
            smEligExclusionOptionalBadge: optionalBadge,
        });
        return { inclusionField, exclusionField, coreBadge, optionalBadge };
    }

    it('turns the CORE badge green on a single inclusion criterion', async () => {
        const { validateEligibilityCriteriaBadges } = await import('./validation.js');
        const { coreBadge, inclusionField } = setupEligibility('older than 18', '');

        validateEligibilityCriteriaBadges();

        expect(coreBadge.classes.has('bg-success')).toBe(true);
        expect(inclusionField.classes.has('required-field-empty')).toBe(false);
    });

    it('leaves the CORE badge unfilled when no inclusion criterion is given', async () => {
        const { validateEligibilityCriteriaBadges } = await import('./validation.js');
        const { coreBadge, inclusionField } = setupEligibility('', 'some exclusion');

        validateEligibilityCriteriaBadges();

        expect(coreBadge.classes.has('bg-success')).toBe(false);
        expect(inclusionField.classes.has('required-field-empty')).toBe(true);
    });

    it('never lets the OPTIONAL exclusion field show the red missing border', async () => {
        const { validateEligibilityCriteriaBadges } = await import('./validation.js');
        const { exclusionField } = setupEligibility('older than 18', '');

        validateEligibilityCriteriaBadges();

        expect(exclusionField.classes.has('required-field-empty')).toBe(false);
    });
});
