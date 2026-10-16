import { describe, expect, it } from 'vitest';

import {
    findPending, guardSave, isPending, pendingMessage, registerStagedControl, rowActionsHtml, rowActionsModel,
    syncAcceptButton,
} from './row-state.js';

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

describe('rowActionsHtml colours', () => {
    const accept = (html) => html.match(/<button[^>]*data-f="accept"[^>]*>/)[0];

    it('the check is gray while the row is empty or incomplete: nothing is set yet, so nothing looks ok', () => {
        const tag = accept(rowActionsHtml(rowActionsModel({ state: 'draft', complete: false })));
        expect(tag).toContain('btn-outline-secondary');
        expect(tag).not.toMatch(/btn-(outline-)?success/);
        expect(tag).toContain('disabled');
    });

    it('the check turns green as soon as the row is complete', () => {
        const tag = accept(rowActionsHtml(rowActionsModel({ state: 'draft', complete: true })));
        expect(tag).toContain('btn-success');
        expect(tag).not.toContain('btn-outline-secondary');
        expect(tag).not.toContain('disabled');
    });
});

describe('syncAcceptButton (rows that update the check in place instead of re-rendering)', () => {
    const fakeButton = () => {
        const classes = new Set(['btn', 'btn-sm', 'btn-outline-secondary']);
        return {
            disabled: true,
            classList: {
                add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c),
            },
        };
    };

    it('enables the check and turns it green when the row becomes complete', () => {
        const button = fakeButton();
        syncAcceptButton(button, true);
        expect(button.disabled).toBe(false);
        expect(button.classList.has('btn-success')).toBe(true);
        expect(button.classList.has('btn-outline-secondary')).toBe(false);
    });

    it('goes back to gray and disabled when it is incomplete again', () => {
        const button = fakeButton();
        syncAcceptButton(button, true);
        syncAcceptButton(button, false);
        expect(button.disabled).toBe(true);
        expect(button.classList.has('btn-success')).toBe(false);
        expect(button.classList.has('btn-outline-secondary')).toBe(true);
    });

    it('does nothing for a row without a check (an accepted row)', () => {
        expect(() => syncAcceptButton(null, true)).not.toThrow();
    });
});

describe('rowActionsHtml hint', () => {
    it('says why the check is disabled, only while it is disabled', () => {
        const draft = rowActionsHtml(rowActionsModel({ state: 'draft', complete: false }), 'author', 'Enter first and last name');
        expect(draft).toContain('data-f="hint"');
        expect(draft).toContain('Enter first and last name');
        const complete = rowActionsHtml(rowActionsModel({ state: 'draft', complete: true }), 'author', 'Enter first and last name');
        expect(complete).not.toContain('data-f="hint"');
        const defined = rowActionsHtml(rowActionsModel({ state: 'defined', complete: true }), 'author', 'Enter first and last name');
        expect(defined).not.toContain('data-f="hint"');
    });
    it('escapes the hint', () => {
        const html = rowActionsHtml(rowActionsModel({ state: 'draft', complete: false }), '', '<b>x</b>');
        expect(html).not.toContain('<b>');
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
    it('names the count and what to do, for rows and for chip entry rows alike', () => {
        const message = pendingMessage(3);
        expect(message).toContain('3 entries are');
        expect(message).toContain('green check');
        expect(message).toContain('Cancel');
        expect(message).toContain('clear');
    });
    it('uses the singular for one entry', () => {
        expect(pendingMessage(1)).toContain('1 entry is');
    });
});

// Minimal DOM fakes: the guard only needs querySelectorAll/contains/classList/_row.
const fakeEl = (hasContent, discard = () => {}) => {
    const classes = new Set();
    return {
        _row: { hasContent: () => hasContent, discard },
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c) },
        scrollIntoView: () => {},
    };
};
const fakeForm = (draftRows = [], extra = []) => ({
    querySelectorAll: (selector) => (selector === '[data-row-state="draft"]' ? draftRows : extra),
    contains: () => true,
});

describe('guardSave', () => {
    it('lets a form with no pending rows be saved, without any message', () => {
        let said = 0;
        expect(guardSave(fakeForm(), () => { said += 1; })).toBe(true);
        expect(said).toBe(0);
    });

    it('blocks while a draft holds content: marks it and says what to do', () => {
        const draft = fakeEl(true);
        const calls = [];
        expect(guardSave(fakeForm([draft]), (...args) => calls.push(args))).toBe(false);
        expect(draft.classList.has('row-pending')).toBe(true);
        expect(calls).toHaveLength(1);
        expect(calls[0][1]).toBe('warning');
        expect(calls[0][0]).toContain('1 entry is');
    });

    it('discards an empty draft instead of blocking', () => {
        let discarded = 0;
        const empty = fakeEl(false, () => { discarded += 1; });
        expect(guardSave(fakeForm([empty]), () => {})).toBe(true);
        expect(discarded).toBe(1);
    });

    it('counts several pending rows in one message', () => {
        const calls = [];
        guardSave(fakeForm([fakeEl(true), fakeEl(true), fakeEl(false)]), (...args) => calls.push(args));
        expect(calls[0][0]).toContain('2 entries are');
    });
});

describe('staged controls (a picker whose typed text is lost without a click)', () => {
    it('are pending while they hold something, and not otherwise', () => {
        const picker = {};
        let typed = true;
        registerStagedControl(picker, () => typed);
        expect(findPending(fakeForm())).toContain(picker);
        typed = false;
        expect(findPending(fakeForm())).not.toContain(picker);
    });

    it('block the save like a draft row does', () => {
        const picker = { classList: fakeEl(true).classList, scrollIntoView: () => {} };
        registerStagedControl(picker, () => true);
        expect(guardSave(fakeForm(), () => {})).toBe(false);
        expect(picker.classList.has('row-pending')).toBe(true);
    });
});
