import { describe, expect, it } from 'vitest';

import { isPending, pendingMessage, rowActionsHtml, rowActionsModel } from './row-state.js';

describe('rowActionsModel', () => {
    it('an incomplete draft shows a disabled check and Cancel, never the delete cross', () => {
        expect(rowActionsModel({ state: 'draft', complete: false })).toEqual({
            accept: { visible: true, disabled: true },
            cancel: { visible: true },
            remove: { visible: false },
        });
    });
    it('a complete draft has an enabled check', () => {
        expect(rowActionsModel({ state: 'draft', complete: true }).accept.disabled).toBe(false);
    });
    it('a defined row shows only the delete cross', () => {
        expect(rowActionsModel({ state: 'defined', complete: true })).toEqual({
            accept: { visible: false, disabled: false },
            cancel: { visible: false },
            remove: { visible: true },
        });
    });
});

describe('rowActionsHtml', () => {
    it('a draft has accept and cancel, disabled accept while incomplete, and no red button', () => {
        const html = rowActionsHtml(rowActionsModel({ state: 'draft', complete: false }));
        expect(html).toContain('data-f="accept"');
        expect(html).toContain('data-f="cancel"');
        expect(html).toMatch(/data-f="accept"[^>]*disabled/);
        expect(html).not.toContain('btn-outline-danger');
        expect(html).not.toContain('data-f="remove"');
    });
    it('a defined row has a labelled red delete button only', () => {
        const html = rowActionsHtml(rowActionsModel({ state: 'defined', complete: true }));
        expect(html).toContain('btn-outline-danger');
        expect(html).toContain('aria-label="Delete"');
        expect(html).not.toContain('data-f="accept"');
    });
});

describe('isPending', () => {
    it('only a draft with content is pending', () => {
        expect(isPending({ state: 'draft', hasContent: true })).toBe(true);
        expect(isPending({ state: 'draft', hasContent: false })).toBe(false);
        expect(isPending({ state: 'defined', hasContent: true })).toBe(false);
    });
});

describe('pendingMessage', () => {
    it('names the count and what to do', () => {
        const message = pendingMessage(3);
        expect(message).toContain('3');
        expect(message).toContain('green check');
        expect(message).toContain('Cancel');
    });
    it('uses the singular for one row', () => {
        expect(pendingMessage(1)).toContain('1 row ');
    });
});
