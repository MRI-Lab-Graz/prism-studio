import { describe, expect, it } from 'vitest';

import { showPreliminarySaveModal } from './preliminary-save-modal.js';

/** Just enough DOM/bootstrap to drive the modal without a browser. */
function buildFakes() {
    const listeners = {};
    const buttons = {};
    const button = (id) => {
        buttons[id] = buttons[id] || { handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; } };
        return buttons[id];
    };
    const modalEl = {
        setAttribute() {},
        addEventListener(type, fn) { listeners[type] = fn; },
        remove() {},
    };
    const doc = {
        body: { appendChild() {} },
        createElement: () => modalEl,
        getElementById: (id) => (id === '_preliminaryMetadataSaveModal' ? null : button(id)),
    };
    const bootstrapApi = { Modal: function Modal() { this.show = () => {}; this.hide = () => {}; } };
    return { doc, bootstrapApi, buttons, listeners };
}

const settled = (promise) => Promise.race([promise, new Promise((r) => setTimeout(() => r('pending'), 20))]);

describe('showPreliminarySaveModal', () => {
    it('resolves true when the user confirms', async () => {
        const { doc, bootstrapApi, buttons } = buildFakes();
        const result = showPreliminarySaveModal(['Name'], { doc, bootstrapApi });
        buttons._prelimSaveConfirm.handlers.click();
        expect(await settled(result)).toBe(true);
    });

    it('resolves false when dismissed by X or Escape (no button click)', async () => {
        // A promise that never settles leaves the study-metadata submit lock
        // held forever, and every later project switch is refused as "busy".
        const { doc, bootstrapApi, listeners } = buildFakes();
        const result = showPreliminarySaveModal(['Name'], { doc, bootstrapApi });
        listeners['hidden.bs.modal']();
        expect(await settled(result)).toBe(false);
    });

    it('keeps true when confirm is followed by the modal hiding', async () => {
        const { doc, bootstrapApi, buttons, listeners } = buildFakes();
        const result = showPreliminarySaveModal(['Name'], { doc, bootstrapApi });
        buttons._prelimSaveConfirm.handlers.click();
        listeners['hidden.bs.modal']();
        expect(await settled(result)).toBe(true);
    });
});
