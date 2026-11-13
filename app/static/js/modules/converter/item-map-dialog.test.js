import { describe, expect, it } from 'vitest';

import { choicesToSend, columnsFor, unmappedItems, unusedColumns } from './item-map-dialog.js';

describe('item map dialog rules', () => {
    const rows = [
        { item: 'ADS01', column: 'A01', why: 'number' },
        { item: 'ADS02', column: null, why: 'none' },
    ];
    const columns = ['id', 'A01', 'A02'];

    it('offers an item its own column plus every column no other row uses', () => {
        expect(columnsFor('ADS02', rows, columns)).toEqual(['id', 'A02']);
        expect(columnsFor('ADS01', rows, columns)).toEqual(['id', 'A01', 'A02']);
    });

    it('lists unused columns, the choices to send and the unmapped items', () => {
        expect(unusedColumns(rows, columns)).toEqual(['id', 'A02']);
        expect(choicesToSend(rows)).toEqual({ ADS01: 'A01', ADS02: '' });
        expect(unmappedItems(rows)).toEqual(['ADS02']);
    });
});
