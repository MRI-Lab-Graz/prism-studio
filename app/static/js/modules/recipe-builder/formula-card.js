/** Pure helpers of the formula box (no DOM, no formula logic: the backend checks and renders formulas). */

/** `{name}` placed over text[start..end); returns the new text and the cursor behind the insert. */
export function insertAtCursor(text, start, end, name) {
    const token = `{${name}}`;
    return { text: text.slice(0, start) + token + text.slice(end), cursor: start + token.length };
}

/** The list with `name` appended; the same list when it is already in it. */
export const addItemOnce = (items, name) => (items.includes(name) ? items : [...items, name]);

export function debounce(fn, ms) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}
