import { describe, expect, it } from 'vitest';

import { renderState, sendAnywayLabel } from './render-state.js';

const ids = (actions) => actions.map((a) => a.id);
const base = { enabled: true, available: true, checked: true, unsaved_count: 0, message: '', server: null, other_servers: [] };
const server = { name: 'origin', url: '/srv/study', reachable: null };

describe('renderState', () => {
  it('no project open leads with "Open from server..."', () => {
    const view = renderState(null);
    expect(view.primary).toEqual({ id: 'open-from-server', label: 'Open from server...' });
    expect(view.secondary).toEqual([]);
  });

  it('install_datalad leads with the computer check', () => {
    const view = renderState({ ...base, available: false, enabled: false, next_step: 'install_datalad' });
    expect(view.primary.id).toBe('doctor');
    expect(view.notice.kind).toBe('danger');
  });

  it('enable shows "Enable DataLad" plus the secondary "Open from server..."', () => {
    const view = renderState({ ...base, enabled: false, next_step: 'enable' });
    expect(view.primary).toEqual({ id: 'enable', label: 'Enable DataLad' });
    expect(view.secondary).toEqual([{ id: 'open-from-server', label: 'Open from server...' }]);
  });

  it('put_on_server shows "Put on server..." with Save and no error notice', () => {
    const view = renderState({ ...base, next_step: 'put_on_server' });
    expect(view.primary).toEqual({ id: 'put-on-server', label: 'Put on server...' });
    expect(ids(view.secondary)).toEqual(['save']);
    expect(view.notice).toBeNull();
    expect(view.text).toMatch(/stay on this computer/);
  });

  it('put_on_server with a server under another name offers to sync with it', () => {
    const view = renderState({ ...base, next_step: 'put_on_server', other_servers: ['ria-store'] });
    expect(view.secondary).toContainEqual({ id: 'sync', label: 'Sync now with "ria-store"', sibling: 'ria-store' });
  });

  it('save leads with "Save", then "Sync now"', () => {
    const view = renderState({ ...base, unsaved_count: 3, server, next_step: 'save' });
    expect(view.primary).toEqual({ id: 'save', label: 'Save' });
    expect(view.secondary).toEqual([{ id: 'sync', label: 'Sync now' }]);
    expect(view.text).toMatch(/3 unsaved/);
  });

  it('sync leads with "Sync now"', () => {
    const view = renderState({ ...base, server, next_step: 'sync' });
    expect(view.primary).toEqual({ id: 'sync', label: 'Sync now' });
    expect(view.notice).toBeNull();
  });

  it('an unreachable server is a plain notice and does not disable Save', () => {
    const view = renderState({ ...base, unsaved_count: 1, server: { ...server, reachable: false }, next_step: 'save' });
    expect(view.notice.kind).toBe('info');
    expect(view.notice.text).toMatch(/could not be reached/);
    expect(view.primary).toEqual({ id: 'save', label: 'Save' });
    expect(view.primary.disabled).toBeUndefined();
  });

  it('More always holds Get latest, Get data, Check this computer and the Settings link', () => {
    const states = [null, { ...base, enabled: false, next_step: 'enable' }, { ...base, server, next_step: 'sync' }];
    for (const state of states) {
      expect(ids(renderState(state).more)).toEqual(['get-latest', 'get-data', 'doctor', 'settings']);
    }
  });

  it('a valid == false state shows the count and the "Send anyway" choice', () => {
    const view = renderState({ ...base, server, next_step: 'sync', valid: false, error_count: 4 });
    expect(view.notice.kind).toBe('warning');
    expect(view.notice.text).toMatch(/4 validation error/);
    expect(view.secondary).toContainEqual({ id: 'send-anyway', label: sendAnywayLabel(4) });
    expect(sendAnywayLabel(4)).toBe('Send anyway, I understand this dataset has 4 errors');
  });
});
