import { afterEach, describe, expect, it } from 'vitest';

import { prefersServerPicker } from './server-picker.js';

describe('server-picker prefersServerPicker', () => {
  afterEach(() => {
    delete globalThis.window;
  });

  it('delegates to PrismPathPicker.prefersServerPicker when available', () => {
    globalThis.window = { PrismPathPicker: { prefersServerPicker: () => true } };
    expect(prefersServerPicker()).toBe(true);
  });

  it('falls back to PrismFileSystemMode.prefersServerPicker when PrismPathPicker is unavailable', () => {
    globalThis.window = { PrismFileSystemMode: { prefersServerPicker: () => true } };
    expect(prefersServerPicker()).toBe(true);
  });

  it('returns false when neither picker is available', () => {
    globalThis.window = {};
    expect(prefersServerPicker()).toBe(false);
  });
});
