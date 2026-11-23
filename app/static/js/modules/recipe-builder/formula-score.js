/**
 * Data model for formula scores and Transforms.Derived entries. Pure, no DOM.
 * It only stores and reads the text; the formula is parsed and evaluated by the
 * backend (src/), never here.
 */

export const EDITABLE_METHODS = new Set(['sum', 'mean', 'formula']);
export const SAFE_SCORE_KEYS = new Set([
    'Name', 'Method', 'Description', 'Formula', 'Items', 'Missing', 'Range', 'MinValid',
]);
export const DERIVED_METHODS = ['max', 'min'];

export const scoreHasFormula = (score) =>
    String((score && score.Method) || '').trim().toLowerCase() === 'formula';

/** Why a stored score cannot be edited in the builder (empty list = editable). */
export function scoreLockReasons(rawScore, method) {
    const reasons = [];
    if (!EDITABLE_METHODS.has(method)) reasons.push(`Method "${method}" is not editable here.`);
    const unsupported = Object.keys(rawScore).filter((key) => !SAFE_SCORE_KEYS.has(key));
    if (unsupported.length > 0) reasons.push(`Uses advanced fields: ${unsupported.join(', ')}.`);
    return reasons;
}

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

/** Wraps an async `fn` so only the newest call's result is delivered: `fn(...args)` then `show(result)`. */
export function latest(fn, show) {
    let token = 0;
    return async (...args) => {
        const mine = ++token;
        const result = await fn(...args);
        if (mine === token) show(result);
    };
}

let nextId = 0;

export function derivedToEntry(d) {
    const original = structuredClone(d);
    // only max/min are edited here; any other Derived method (map, formula, ...) is kept exactly as loaded
    const editable = DERIVED_METHODS.includes(original.Method);
    return {
        readOnly: !editable,
        id: `derived-${nextId++}`,
        name: original.Name || '',
        method: original.Method,
        items: Array.isArray(original.Items) ? [...original.Items] : [],
        original,
    };
}

export function entryToDerived(entry) {
    if (entry.readOnly) return structuredClone(entry.original);
    return {
        ...structuredClone(entry.original || {}),
        Name: entry.name,
        Method: DERIVED_METHODS.includes(entry.method) ? entry.method : DERIVED_METHODS[0],
        Items: [...entry.items],
    };
}

/** What is saved: read-only entries as loaded, edited ones only when they have a name. */
export const derivedForSave = (entries) =>
    entries.filter((e) => e.readOnly || String(e.name).trim() !== '').map(entryToDerived);
