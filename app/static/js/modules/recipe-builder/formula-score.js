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

/** Names written between { and } in a formula, in first-seen order (text scan, not evaluation). */
export function itemsUsedIn(formula) {
    const names = [...String(formula || '').matchAll(/\{([^{}]+)\}/g)].map((m) => m[1]);
    return [...new Set(names)];
}

let nextId = 0;

export function derivedToEntry(d) {
    const original = structuredClone(d);
    return {
        id: `derived-${nextId++}`,
        name: original.Name || '',
        method: original.Method,
        items: Array.isArray(original.Items) ? [...original.Items] : [],
        original,
    };
}

export function entryToDerived(entry) {
    return {
        ...structuredClone(entry.original || {}),
        Name: entry.name,
        Method: DERIVED_METHODS.includes(entry.method) ? entry.method : DERIVED_METHODS[0],
        Items: [...entry.items],
    };
}
