import { afterEach, describe, expect, it } from 'vitest';

import { getProgressEls, setStatusBadge } from './helpers.js';

function stubDocument(elements) {
  globalThis.document = {
    getElementById: (id) => elements[id] || null,
  };
}

describe('getProgressEls', () => {
  afterEach(() => {
    delete globalThis.document;
  });

  it('looks up progress elements by prefix', () => {
    const els = {
      dataladServerProgress: { id: 'progressDiv' },
      dataladServerProgressBar: { id: 'progressBar' },
      dataladServerProgressText: { id: 'progressText' },
      dataladServerStatusText: { id: 'statusText' },
      dataladServerResult: { id: 'resultDiv' },
      dataladServerCancelBtn: { id: 'cancelBtn' },
    };
    stubDocument(els);

    expect(getProgressEls('dataladServer')).toEqual({
      progressDiv: els.dataladServerProgress,
      progressBar: els.dataladServerProgressBar,
      progressText: els.dataladServerProgressText,
      statusText: els.dataladServerStatusText,
      resultDiv: els.dataladServerResult,
      cancelBtn: els.dataladServerCancelBtn,
    });
  });

  it('uses a different prefix for a different caller without collision', () => {
    stubDocument({ rsyncServerProgress: { id: 'rsync-progress' } });

    const els = getProgressEls('rsyncServer');
    expect(els.progressDiv).toEqual({ id: 'rsync-progress' });
    expect(els.progressBar).toBeNull();
  });
});

describe('setStatusBadge', () => {
  afterEach(() => {
    delete globalThis.document;
  });

  it('sets the badge tone class and text for the given prefix', () => {
    const badge = { className: '', textContent: '' };
    stubDocument({ dataladServerStatusBadge: badge });

    setStatusBadge('dataladServer', 'Connected', 'info');

    expect(badge.className).toBe('badge bg-info');
    expect(badge.textContent).toBe('Connected');
  });

  it('defaults to the secondary tone', () => {
    const badge = { className: '', textContent: '' };
    stubDocument({ rsyncServerStatusBadge: badge });

    setStatusBadge('rsyncServer', 'Checking...');

    expect(badge.className).toBe('badge bg-secondary');
  });

  it('does nothing when the badge element is missing', () => {
    stubDocument({});
    expect(() => setStatusBadge('dataladServer', 'x')).not.toThrow();
  });
});
