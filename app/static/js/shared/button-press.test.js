import { describe, expect, it } from 'vitest';

import { installButtonPressGuard } from './button-press.js';

// Minimal document: records the mousedown listener and fakes event.target.closest.
const setup = () => {
    let listener;
    installButtonPressGuard({ addEventListener: (type, fn) => { if (type === 'mousedown') listener = fn; } });
    return (matches) => {
        const event = { target: { closest: (sel) => (matches(sel) ? {} : null) }, preventDefault: () => { event.prevented = true; } };
        listener(event);
        return event.prevented === true;
    };
};

describe('installButtonPressGuard', () => {
    it('keeps focus in the field when a button is pressed, so a blur re-render cannot swallow the click', () => {
        const press = setup();
        expect(press((sel) => sel.includes('button'))).toBe(true);
    });

    it('leaves inputs, selects and links alone', () => {
        const press = setup();
        expect(press(() => false)).toBe(false);
    });
});
