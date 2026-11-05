import { describe, expect, it, vi } from 'vitest';

import { getLatestFromServer } from './datalad-update.js';

const reply = (body, ok = true) => ({ ok, json: async () => body });

describe('getLatestFromServer', () => {
  it('asks the backend once, with no body options', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: true, updated: false }));
    await getLatestFromServer(fetchFn);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn.mock.calls[0][0]).toBe('/api/projects/datalad/update');
    expect(fetchFn.mock.calls[0][1].method).toBe('POST');
  });

  it('says nothing when there is no server or nothing new', async () => {
    const skipped = vi.fn().mockResolvedValue(reply({ success: true, skipped: true }));
    const current = vi.fn().mockResolvedValue(reply({ success: true, updated: false }));
    expect((await getLatestFromServer(skipped)).notice).toBeNull();
    expect((await getLatestFromServer(current)).notice).toBeNull();
  });

  it('tells the user what arrived', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: true, updated: true, message: 'Got the latest.' }));
    const { notice } = await getLatestFromServer(fetchFn);
    expect(notice).toEqual({ text: 'Got the latest.', kind: 'success', label: 'Updated' });
  });

  it('shows the backend refusal as it is', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: false, error: '2 unsaved change(s)' }, false));
    const { notice } = await getLatestFromServer(fetchFn);
    expect(notice).toEqual({ text: '2 unsaved change(s)', kind: 'danger', label: 'Not updated' });
  });

  it('survives an unreadable answer', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: false, json: async () => { throw new Error('bad'); } });
    const { notice } = await getLatestFromServer(fetchFn);
    expect(notice.kind).toBe('danger');
  });
});
