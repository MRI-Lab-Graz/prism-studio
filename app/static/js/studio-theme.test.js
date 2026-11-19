import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

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

// A badge that records its text, classes and title, like a rendered tier badge.
function realBadge(label, cls) {
  const classes = new Set([cls]);
  const attrs = {};
  return {
    classes, attrs, textContent: label,
    classList: { add: (c) => classes.add(c), remove: (...cs) => cs.forEach((c) => classes.delete(c)) },
    setAttribute: (k, v) => { attrs[k] = v; }, removeAttribute: (k) => { delete attrs[k]; },
  };
}

describe('a required-in-project field that is open in a library template', () => {
  it('is neutral and says PROJECT, neither green nor red', () => {
    const b = realBadge('REQUIRED', 'bg-danger');
    StudioTheme.setFilled(b, false, true);
    expect([...b.classes]).toEqual(['badge-tier-project']);
    expect(b.textContent).toBe('PROJECT');
    expect(b.attrs.title).toMatch(/project/i);
  });

  it('is green and REQUIRED again once filled, red once emptied in a project', () => {
    const b = realBadge('REQUIRED', 'bg-danger');
    StudioTheme.setFilled(b, false, true);
    StudioTheme.setFilled(b, true, false);
    expect([...b.classes]).toEqual(['bg-success']);
    expect(b.textContent).toBe('REQUIRED');
    expect(b.attrs.title).toBeUndefined();
    StudioTheme.setFilled(b, false, false);
    expect([...b.classes]).toEqual(['bg-danger']);
  });
});

describe('tally with project fields', () => {
  it('shows open project fields neutral, never green or red', () => {
    const html = StudioTheme.tally({ required: [2, 2], project: [0, 2] });
    expect(html).toContain('bg-success bg-opacity-75">Required 2/2');
    expect(html).toContain('badge-tier-project bg-opacity-75">Project 0/2');
  });

  it('shows only the neutral badge for a section with open project fields only', () => {
    const html = StudioTheme.tally({ required: [0, 0], project: [0, 2] });
    expect(html).not.toContain('bg-success');
    expect(html).not.toContain('bg-danger');
    expect(html).toContain('Project 0/2');
  });

  it('turns green when every project field is filled', () => {
    expect(StudioTheme.tally({ project: [2, 2] })).toContain('bg-success bg-opacity-75">Project 2/2');
  });
});

describe('long text fields (a reference of 300 to 600 characters is shown whole)', () => {
  it('names the Study-level fields that grow with their text, by path', () => {
    for (const f of ['Citation', 'Description', 'Reliability', 'Validity', 'Norming', 'Notes', 'PermissionsNote', 'Construct']) expect(StudioTheme.isLongText(`Study/${f}`)).toBe(true);
    expect(StudioTheme.isLongText('Study/References/Citation')).toBe(true);
    expect(StudioTheme.isLongText('Study/DOI')).toBe(false);
    expect(StudioTheme.isLongText('ITEM/Description')).toBe(false); // an item's Description is not a Study field
    expect(StudioTheme.isLongText('Description')).toBe(false);
    expect(StudioTheme.isLongText('')).toBe(false);
  });

  it('autoGrow sets the height to the content height, so nothing needs scrolling', () => {
    const ta = { style: {}, scrollHeight: 148 };
    StudioTheme.autoGrow(ta, 500);
    expect(ta.style.height).toBe('148px');
    expect(ta.style.overflowY).toBe('hidden');
  });

  it('autoGrow stops at the maximum height and scrolls inside the box from there', () => {
    const ta = { style: {}, scrollHeight: 900 };
    StudioTheme.autoGrow(ta, 500);
    expect(ta.style.height).toBe('500px');
    expect(ta.style.overflowY).toBe('auto');
  });

  it('gives long descriptive fields room: 6 rows, a citation 4', () => {
    expect(StudioTheme.longTextRows('Study/Reliability')).toBe(6);
    expect(StudioTheme.longTextRows('Study/Description')).toBe(6);
    expect(StudioTheme.longTextRows('Study/Citation')).toBe(4);
    expect(StudioTheme.longTextRows('Study/Construct')).toBe(2);
    expect(StudioTheme.longTextRows('Study/PermissionsNote')).toBe(3);
    expect(StudioTheme.longTextRows('Study/References/Citation')).toBe(4);
  });

  it('longText (also the string form of a string-or-object field) is a full-width wrapping text area with that room', () => {
    const made = [];
    globalThis.document = { createElement: (tag) => { const el = { tag, style: {}, addEventListener() {} }; made.push(el); return el; } };
    const kse = 'x'.repeat(700);
    const ta = StudioTheme.longText(kse, () => {}, '— Not set —', 'Study/Reliability');
    expect(ta.tag).toBe('textarea');
    expect(ta.value).toBe(kse);
    expect(ta.rows).toBe(6);
    expect(ta.style.width).toBe('100%');
    expect(StudioTheme.longText('c', () => {}, '', 'Study/Citation').rows).toBe(4);
    delete globalThis.document;
  });
});

describe('offersMultilingual (descriptive header fields are English only)', () => {
  it('refuses the conversion for the English-only descriptive fields of the Study section', () => {
    for (const f of ['Description', 'Construct', 'Reliability', 'Validity', 'Norming', 'Notes', 'PermissionsNote', 'Keywords', 'Citation', 'LicenseTerms']) {
      expect(StudioTheme.offersMultilingual('Study', f)).toBe(false);
    }
  });

  it('covers the descriptive biometrics fields of Study, Technical, Scoring and Normative', () => {
    for (const f of ['ExclusionCriteria', 'TargetPopulation', 'WarmupProtocol']) expect(StudioTheme.offersMultilingual('Study', f)).toBe(false);
    expect(StudioTheme.offersMultilingual('Technical', 'Equipment')).toBe(false);
    for (const f of ['ScoringMethod', 'CutoffsSource', 'NormsSource']) expect(StudioTheme.offersMultilingual('Scoring', f)).toBe(false);
    for (const f of ['ReferencePopulation', 'ReferenceSource']) expect(StudioTheme.offersMultilingual('Normative', f)).toBe(false);
  });

  it('makes the item-level Description English only outside surveys (a column description is metadata; a survey item is the instrument text)', () => {
    for (const m of ['biometrics', 'biosample', 'environment']) expect(StudioTheme.offersMultilingual('ITEM', 'Description', m)).toBe(false);
    expect(StudioTheme.offersMultilingual('ITEM', 'Description', 'survey')).toBe(true);
    expect(StudioTheme.offersMultilingual('ITEM', 'Description')).toBe(true);
  });

  it('includes RecallPeriod, as the library check does', () => {
    expect(StudioTheme.offersMultilingual('Study', 'RecallPeriod')).toBe(false);
  });

  it('keeps it for fields where any language is allowed', () => {
    for (const f of ['Instructions', 'OriginalName', 'Levels', 'Text']) expect(StudioTheme.offersMultilingual('Study', f)).toBe(true);
  });

  it('keeps it for a same-named field outside the Study section (item level)', () => {
    for (const f of ['Description', 'Notes', 'Keywords']) {
      expect(StudioTheme.offersMultilingual('Questions', f)).toBe(true);
      expect(StudioTheme.offersMultilingual('', f)).toBe(true);
    }
  });
});

describe('every StudioTheme function the pages call exists', () => {
  it('template-editor.js and its modules use only functions the theme exports (a missing one aborts the whole render)', () => {
    const files = ['template-editor.js', 'template-editor/author-entry.js', 'template-editor/doi-check.js'];
    for (const f of files) {
      const src = readFileSync(new URL(`./${f}`, import.meta.url), 'utf8');
      for (const [, name] of src.matchAll(/StudioTheme\.(\w+)\(/g)) {
        expect(typeof StudioTheme[name], `${f} calls StudioTheme.${name}`).toBe('function');
      }
    }
  });
});
