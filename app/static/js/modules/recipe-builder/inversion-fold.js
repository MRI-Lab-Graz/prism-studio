/**
 * The Inversion box is rarely relevant: it starts folded when no item is
 * inverted and open when at least one is (page state only, never saved).
 */
'use strict';

export function initialInversionExpanded(invertedCount) {
    return (invertedCount || 0) > 0;
}
