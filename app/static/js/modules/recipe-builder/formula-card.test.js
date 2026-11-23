import { describe, expect, it, vi } from 'vitest';

import { addItemOnce, debounce, insertAtCursor } from './formula-card.js';

describe('insertAtCursor', () => {
    it('inserts {ITEM} at the cursor and moves the cursor behind it', () => {
        expect(insertAtCursor('a+b', 1, 1, 'x')).toEqual({ text: 'a{x}+b', cursor: 4 });
    });
    it('replaces a selection', () => {
        expect(insertAtCursor('a+b', 0, 3, 'x')).toEqual({ text: '{x}', cursor: 3 });
    });
});

describe('addItemOnce', () => {
    it('adds a name once and returns the same list otherwise', () => {
        const items = ['a'];
        expect(addItemOnce(items, 'b')).toEqual(['a', 'b']);
        expect(addItemOnce(items, 'a')).toBe(items);
    });
});

describe('debounce', () => {
    it('runs once after the pause with the last arguments', () => {
        vi.useFakeTimers();
        const fn = vi.fn();
        const d = debounce(fn, 300);
        d(1); d(2);
        vi.advanceTimersByTime(299);
        expect(fn).not.toHaveBeenCalled();
        vi.advanceTimersByTime(1);
        expect(fn).toHaveBeenCalledTimes(1);
        expect(fn).toHaveBeenCalledWith(2);
        vi.useRealTimers();
    });
});
