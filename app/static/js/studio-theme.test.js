import { describe, expect, it } from 'vitest';

const loaded = await import('./studio-theme.js');  // a plain script: global in the browser, module.exports under vitest
const StudioTheme = globalThis.StudioTheme || loaded.default || loaded;

describe('tierBadgeClass', () => {
  it('turns a filled field green whatever its tier', () => {
    for (const label of ['REQUIRED', 'CORE', 'OPTIONAL']) expect(StudioTheme.tierBadgeClass(label, true)).toBe('bg-success');
  });

  it('gives an empty field its tier colour back, as the project page does', () => {
    expect(StudioTheme.tierBadgeClass('REQUIRED', false)).toBe('bg-danger');
    expect(StudioTheme.tierBadgeClass('CORE', false)).toBe('badge-tier-core');
    expect(StudioTheme.tierBadgeClass('OPTIONAL', false)).toBe('bg-secondary');
  });
});
