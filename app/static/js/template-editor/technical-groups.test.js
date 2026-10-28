import { describe, expect, it } from 'vitest';

import { opensByDefault } from './technical-groups.js';

const software = { label: 'Data Collection Software', defaultOpen: false, fields: new Set(['SoftwarePlatform', 'SoftwareVersion']) };

describe('opensByDefault', () => {
    it('opens a group that is open by default', () => {
        expect(opensByDefault({ ...software, defaultOpen: true }, [], {})).toBe(true);
    });

    it('opens a closed group when one of its required fields is empty, so the user finds it', () => {
        const required = ['SoftwareVersion'];
        expect(opensByDefault(software, required, { SoftwarePlatform: 'Pavlovia' })).toBe(true);
        expect(opensByDefault(software, required, { SoftwareVersion: '' })).toBe(true);
        expect(opensByDefault(software, required, { SoftwareVersion: null })).toBe(true);
    });

    it('stays closed when the required field is filled or nothing in the group is required', () => {
        expect(opensByDefault(software, ['SoftwareVersion'], { SoftwareVersion: '2026.1' })).toBe(false);
        expect(opensByDefault(software, ['Language'], {})).toBe(false);
        expect(opensByDefault(software, [], undefined)).toBe(false);
    });
});
