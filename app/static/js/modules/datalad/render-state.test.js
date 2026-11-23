import { describe, expect, it } from 'vitest';

import { renderState } from './render-state.js';

const base = { enabled: true, available: true, checked: true, unsaved_count: 0, message: '' };
const ids = (actions) => actions.map((a) => a.id);

describe('renderState (Studio enables DataLad and saves; Worldline Desktop does the rest)', () => {
  it('no project open offers no action but the computer check and settings', () => {
    const view = renderState(null);
    expect(view.primary).toBeNull();
    expect(ids(view.more)).toEqual(['doctor', 'settings']);
  });

  it('install_datalad leads with the computer check', () => {
    const view = renderState({ ...base, available: false, enabled: false, next_step: 'install_datalad' });
    expect(view.primary.id).toBe('doctor');
    expect(view.notice.kind).toBe('danger');
  });

  it('enable shows "Enable DataLad", and "Finish enabling DataLad" for unregistered subject datasets', () => {
    expect(renderState({ ...base, enabled: false, next_step: 'enable' }).primary).toEqual({ id: 'enable', label: 'Enable DataLad' });
    const finish = renderState({ ...base, next_step: 'enable', enable_kind: 'finish', nested_unregistered: 3 });
    expect(finish.primary).toEqual({ id: 'enable', label: 'Finish enabling DataLad' });
    expect(finish.text).toContain('3 subject datasets');
  });

  it('save leads with Save and counts the unsaved changes', () => {
    const view = renderState({ ...base, unsaved_count: 4, next_step: 'save' });
    expect(view.primary).toEqual({ id: 'save', label: 'Save' });
    expect(view.text).toContain('4 unsaved change');
  });

  it('no server yet still offers Save, and says sharing is done in Worldline Desktop', () => {
    const view = renderState({ ...base, next_step: 'put_on_server' });
    expect(view.title).toBe('Not on a server yet');
    expect(view.primary).toEqual({ id: 'save', label: 'Save' });
    expect(view.text).toContain('Worldline Desktop');
  });

  it('everything saved with a server has no button and points to Worldline Desktop', () => {
    const view = renderState({ ...base, next_step: 'sync' });
    expect(view.primary).toBeNull();
    expect(view.text).toContain('Worldline Desktop');
  });

  it('never offers a server action', () => {
    for (const next_step of ['install_datalad', 'enable', 'save', 'put_on_server', 'sync']) {
      const view = renderState({ ...base, next_step });
      const all = [view.primary, ...view.secondary, ...view.more].filter(Boolean).map((a) => a.id);
      expect(all.filter((id) => ['open-from-server', 'put-on-server', 'sync', 'send-anyway', 'get-latest', 'get-data'].includes(id))).toEqual([]);
    }
  });
});
