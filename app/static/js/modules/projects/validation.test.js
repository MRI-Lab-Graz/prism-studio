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
