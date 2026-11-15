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

// A minimal stand-in for a rendered field: <div><label class="studio-field-label"><span class="badge">REQUIRED</span></label></div>
function fakeField(label, cls) {
  const classes = new Set([cls]);
  const badge = { textContent: label, classList: { add: (c) => classes.add(c), remove: (...cs) => cs.forEach((c) => classes.delete(c)) } };
  return { classes, field: { querySelector: () => badge } };
}

describe('paintRequired (fields inside structured array cards)', () => {
  it('is green for a stored value and red for a blank one, and follows every change', () => {
    const { classes, field } = fakeField('REQUIRED', 'bg-danger');
    StudioTheme.paintRequired(field, 'primary');
    expect([...classes]).toEqual(['bg-success']);
    StudioTheme.paintRequired(field, '');
    expect([...classes]).toEqual(['bg-danger']);
    StudioTheme.paintRequired(field, undefined);
    expect([...classes]).toEqual(['bg-danger']);
    StudioTheme.paintRequired(field, 'secondary');
    expect([...classes]).toEqual(['bg-success']);
  });

  it('leaves non-required badges alone', () => {
    const { classes, field } = fakeField('OPTIONAL', 'bg-secondary');
    StudioTheme.paintRequired(field, 'x');
    expect([...classes]).toEqual(['bg-secondary']);
  });
});

describe('isBlank', () => {
  it('is the backend not-filled-in rule', () => {
    for (const v of [undefined, null, '', '  ', [], { en: '' }]) expect(StudioTheme.isBlank(v)).toBe(true);
    for (const v of ['a', ['a'], { en: 'a' }, 0, false]) expect(StudioTheme.isBlank(v)).toBe(false);
  });
});
