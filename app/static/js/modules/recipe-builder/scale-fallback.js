/**
 * Pure decision logic for how the Recipe Builder resolves the reverse-
 * scoring (Invert) scale range for an item.
 *
 * Extracted out of the recipe_builder.js monolith: previously an item with
 * no detected MinValue/MaxValue (auto-detected from its survey template)
 * silently fell back to a hardcoded 1-7 range. That fabricated range then
 * got written into the saved recipe's Transforms.Invert.Scale, so an
 * instrument with a real 0-4 or 1-5 scale had its reverse-coded items
 * scored against the wrong range with no error anywhere.
 */
'use strict';

/**
 * Resolve the detected {min, max} range for a variation, preferring an
 * exact variant match, then the default ('') variation. Returns null --
 * never a fabricated range -- when nothing was actually detected.
 */
export function resolveInvertScale(scaleRanges, variationKey) {
    return (scaleRanges || {})[variationKey] || (scaleRanges || {})[''] || null;
}

/**
 * Build a recipe's Transforms.Invert block from the set of globally
 * inverted item IDs and a per-item range lookup.
 *
 * Items with no detected range are excluded from the emitted Invert.Items
 * list (never scored against a fabricated global scale) and reported back
 * in `itemsWithoutRange` so the UI can warn the user. When *no* inverted
 * item has a detected range, `transform` is null -- there is nothing safe
 * to write.
 *
 * @param {string[]} invertedItemIds
 * @param {(itemId: string) => {min:number,max:number}|null} getItemRange
 * @returns {{transform: object|null, itemsWithoutRange: string[]}}
 */
export function buildInvertTransform(invertedItemIds, getItemRange) {
    const itemScales = {};
    const itemsWithoutRange = [];

    (invertedItemIds || []).forEach(id => {
        const r = getItemRange(id);
        if (r) itemScales[id] = { min: r.min, max: r.max };
        else itemsWithoutRange.push(id);
    });

    const scoredItems = (invertedItemIds || []).filter(id => itemScales[id]);
    if (scoredItems.length === 0) {
        return { transform: null, itemsWithoutRange };
    }

    // Most common range among items with a detected scale becomes the
    // shared fallback Scale; a minority of differing items get ItemScales.
    const freq = {};
    Object.values(itemScales).forEach(r => {
        const k = r.min + ',' + r.max;
        freq[k] = (freq[k] || 0) + 1;
    });
    const bestKey = Object.keys(freq).sort((a, b) => freq[b] - freq[a])[0];
    const [mn, mx] = bestKey.split(',').map(Number);
    const globalScale = { min: mn, max: mx };

    const uniqueRanges = new Set(Object.values(itemScales).map(r => r.min + ',' + r.max));
    const invert = { Scale: globalScale, Items: scoredItems };
    if (uniqueRanges.size > 1) invert.ItemScales = itemScales;

    return { transform: invert, itemsWithoutRange };
}
