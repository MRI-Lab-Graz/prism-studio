import { describe, expect, it, vi } from 'vitest';

import { enableDatalad } from './datalad-enable.js';

const reply = (body, ok = true) => ({ ok, json: async () => body });

describe('enableDatalad', () => {
  it('repeats the enable call until no nested dataset is left', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce(reply({ success: true, enable_continue: true, datalad: { subdatasets_remaining_count: 2 } }))
      .mockResolvedValueOnce(reply({ success: true, message: 'done', datalad: { subdatasets_remaining_count: 0 } }));
    const onProgress = vi.fn();
    const data = await enableDatalad(fetchFn, { askIdentity: vi.fn(), onProgress });
    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(fetchFn.mock.calls[0][0]).toBe('/api/projects/datalad/enable');
    expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ confirmed: true });
    expect(onProgress).toHaveBeenCalledTimes(1);
    expect(data.message).toBe('done');
  });

  it('does not decide on its own to go on: one call when the backend does not ask for another', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: true, datalad: { subdatasets_remaining_count: 5 } }));
    await enableDatalad(fetchFn, { askIdentity: vi.fn() });
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('asks for the name and email once, then tries again', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce(reply({ success: false, needs_git_identity: true }))
      .mockResolvedValueOnce(reply({ success: true, datalad: {} }));
    const askIdentity = vi.fn().mockResolvedValue(true);
    await enableDatalad(fetchFn, { askIdentity });
    expect(askIdentity).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('stops with the error when the name and email are not given', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: false, needs_git_identity: true }));
    await expect(enableDatalad(fetchFn, { askIdentity: async () => false })).rejects.toThrow(/name and email/);
  });

  it('stops with the failure when the backend says registration is stuck', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: true, enable_stuck: true, datalad: { subdataset_failures: ['sub-01: locked'] } }));
    await expect(enableDatalad(fetchFn, { askIdentity: vi.fn() })).rejects.toThrow(/sub-01: locked/);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('passes the backend error on', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: false, error: 'git-annex missing' }, false));
    await expect(enableDatalad(fetchFn, { askIdentity: vi.fn() })).rejects.toThrow('git-annex missing');
  });
});
