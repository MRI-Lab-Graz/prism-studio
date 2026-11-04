import { describe, expect, it, vi } from 'vitest';

import { saveDataladSnapshot } from './datalad-save.js';

const reply = (body, ok = true) => ({ ok, json: async () => body });
const blocked = reply(
  { success: false, validation_blocked: true, validation_errors: ['bad name', 'no sidecar'], error: 'refused' },
  false
);

describe('saveDataladSnapshot', () => {
  it('saves once when the dataset is valid and never asks', async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply({ success: true }));
    const confirmFn = vi.fn();
    const { data } = await saveDataladSnapshot(fetchFn, 'm', confirmFn);
    expect(data.success).toBe(true);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchFn.mock.calls[0][1].body)).toEqual({ message: 'm' });
    expect(confirmFn).not.toHaveBeenCalled();
  });

  it('lists the errors, and saves again with allow_invalid when the user confirms', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(blocked).mockResolvedValueOnce(reply({ success: true }));
    const confirmFn = vi.fn().mockReturnValue(true);
    const { data } = await saveDataladSnapshot(fetchFn, 'm', confirmFn);
    expect(confirmFn.mock.calls[0][0]).toContain('bad name');
    expect(JSON.parse(fetchFn.mock.calls[1][1].body)).toEqual({ message: 'm', allow_invalid: true });
    expect(data.success).toBe(true);
  });

  it('keeps the refusal when the user declines', async () => {
    const fetchFn = vi.fn().mockResolvedValue(blocked);
    const { data } = await saveDataladSnapshot(fetchFn, 'm', () => false);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(data.validation_blocked).toBe(true);
  });

  it('falls back to the server message when the validator could not run (no error list)', async () => {
    const crashed = reply({ success: false, validation_blocked: true, validation_errors: [], error: 'validator crashed' }, false);
    const confirmFn = vi.fn().mockReturnValue(false);
    await saveDataladSnapshot(vi.fn().mockResolvedValue(crashed), 'm', confirmFn);
    expect(confirmFn.mock.calls[0][0]).toContain('validator crashed');
  });
});
