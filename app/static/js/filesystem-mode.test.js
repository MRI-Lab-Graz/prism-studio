import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// filesystem-mode.js is a browser IIFE: give it a minimal window, then import it.
async function load() {
  const open = vi.fn(async () => '/picked');
  const fetchSpy = vi.fn(async () => { throw new Error('no network expected'); });
  globalThis.window = { PrismFolderBrowser: { open }, prompt: () => 'out.json', location: { href: 'https://x/' } };
  globalThis.document = { currentScript: { src: 'https://x/js/filesystem-mode.js' } };
  globalThis.fetch = fetchSpy;
  vi.resetModules();
  await import('./filesystem-mode.js');
  return { picker: globalThis.window.PrismPathPicker, open, fetchSpy };
}

describe('single in-app picker', () => {
  beforeEach(() => { vi.spyOn(console, 'warn').mockImplementation(() => {}); });
  afterEach(() => {
    delete globalThis.window;
    delete globalThis.document;
    delete globalThis.fetch;
    vi.restoreAllMocks();
  });

  it('browseFile / browseFolder open the in-app browser and never call a native dialog endpoint', async () => {
    const { picker, open, fetchSpy } = await load();
    expect(await picker.browseFile({ extensions: '.json', startPath: '/a' })).toBe('/picked');
    expect(await picker.browseFolder({ startPath: '/a' })).toBe('/picked');
    expect(open).toHaveBeenNthCalledWith(1, expect.objectContaining({ mode: 'file', extensions: '.json', startPath: '/a' }));
    expect(open).toHaveBeenNthCalledWith(2, expect.objectContaining({ mode: 'folder', startPath: '/a' }));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('browseSaveFile picks a folder, then joins the typed name', async () => {
    const { picker } = await load();
    expect(await picker.browseSaveFile({ defaultName: 'x.json' })).toBe('/picked/out.json');
  });

  it('starts at the project root unless the caller keeps its own start path', async () => {
    const { picker, open } = await load();
    globalThis.window.currentProjectPath = '/proj';
    await picker.browseFolder({ startPath: '/last' });
    await picker.browseFile({ startPath: '/last', keepStartPath: true });
    globalThis.window.currentProjectPath = '';
    await picker.browseFolder({ startPath: '/last' });
    expect(open).toHaveBeenNthCalledWith(1, expect.objectContaining({ startPath: '/proj' }));
    expect(open).toHaveBeenNthCalledWith(2, expect.objectContaining({ startPath: '/last' }));
    expect(open).toHaveBeenNthCalledWith(3, expect.objectContaining({ startPath: '/last' }));
  });
});
