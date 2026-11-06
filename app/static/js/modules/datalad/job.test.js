import { describe, expect, it, vi } from 'vitest';

import { openFromServer, runJob, takeOpenedMessage } from './job.js';

const reply = (body, ok = true) => ({ ok, json: async () => body });
const STATUS = '/api/projects/datalad-server/sync/j1/status';

// A fetch that answers the start route with job "j1", then each status poll with the next of `statuses`.
function fakeFetch(statuses, extra = {}) {
  const queue = [...statuses];
  return vi.fn(async (url, options = {}) => {
    if (extra[url]) return extra[url];
    if (url === STATUS) return reply(queue.shift());
    if (url.endsWith('/cancel')) return reply({ cancelled: true });
    if (options.method === 'POST') return reply({ job_id: 'j1' });
    throw new Error(`unexpected ${url}`);
  });
}

function fakeUi() {
  return { start: vi.fn(), progress: vi.fn(), result: vi.fn(), errors: vi.fn(), end: vi.fn() };
}

const now = async () => {};
const posts = (fetchFn, url) => fetchFn.mock.calls.filter(([u, o]) => u === url && o?.method === 'POST');

describe('openFromServer', () => {
  it('opens the copy with POST /api/projects/current when the job is complete', async () => {
    const fetchFn = fakeFetch(
      [{ status: 'complete', percent: 100, message: 'done', result: { success: true, path: '/data/study', message: 'Copied.' } }],
      { '/api/projects/current': reply({ success: true }) },
    );
    const reload = vi.fn();
    await openFromServer(fetchFn, 'host:/srv/study', '/data/study', { ui: fakeUi(), reload, sleep: now });
    const opened = posts(fetchFn, '/api/projects/current');
    expect(opened).toHaveLength(1);
    expect(JSON.parse(opened[0][1].body)).toEqual({ path: '/data/study' });
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('keeps the success text ("Use Get data...") across the reload, shown once', async () => {
    const fetchFn = fakeFetch(
      [{ status: 'complete', percent: 100, result: { success: true, path: '/data/study', message: 'Opened. Use Get data.' } }],
      { '/api/projects/current': reply({ success: true }) },
    );
    const kept = new Map();
    const storage = { setItem: (k, v) => kept.set(k, v), getItem: (k) => kept.get(k) ?? null, removeItem: (k) => kept.delete(k) };
    await openFromServer(fetchFn, 'host:/srv/study', '/data/study', { ui: fakeUi(), reload: vi.fn(), sleep: now, storage });
    expect(takeOpenedMessage(storage)).toBe('Opened. Use Get data.');
    expect(takeOpenedMessage(storage)).toBe('');  // once
    expect(kept.size).toBe(0);
  });

  it('does not open anything when the job ends in an error, even if its result carries a path', async () => {
    const fetchFn = fakeFetch([{ status: 'error', error: 'clone failed', result: { success: false, path: '/data/study' } }]);
    const ui = fakeUi();
    const reload = vi.fn();
    await openFromServer(fetchFn, 'host:/srv/study', '/data/study', { ui, reload, sleep: now });
    expect(posts(fetchFn, '/api/projects/current')).toHaveLength(0);
    expect(reload).not.toHaveBeenCalled();
    expect(ui.result).toHaveBeenCalledWith('danger', 'clone failed');
  });
});

describe('runJob', () => {
  for (const route of ['/api/projects/datalad-server/sync/start', '/api/projects/datalad/put-on-server']) {
    it(`on validation errors lists them; Send anyway re-posts ${route} with allow_invalid, never by itself`, async () => {
      const stopped = { status: 'error', error: '2 errors', result: { success: false, reason: 'validation_errors', errors: ['a', 'b'] } };
      const fetchFn = fakeFetch([stopped, { status: 'complete', percent: 100, result: { message: 'sent' } }]);
      const ui = fakeUi();
      const body = { project_path: '/p', location: 'host:/srv' };

      await runJob(fetchFn, route, body, { ui, sleep: now });

      expect(posts(fetchFn, route)).toHaveLength(1);  // nothing repeated automatically
      expect(ui.errors).toHaveBeenCalledTimes(1);
      const [result, sendAnyway] = ui.errors.mock.calls[0];
      expect(result.errors).toEqual(['a', 'b']);

      await sendAnyway();

      const sent = posts(fetchFn, route);
      expect(sent).toHaveLength(2);
      expect(JSON.parse(sent[1][1].body)).toEqual({ ...body, allow_invalid: true });
      expect(fetchFn.mock.calls.every(([u]) => u === route || u.startsWith('/api/projects/datalad-server/sync/j1/'))).toBe(true);
    });
  }

  it('Cancel of a running job says so honestly, stays busy and keeps polling until the job ends', async () => {
    const fetchFn = fakeFetch([
      { status: 'running', percent: 10 },
      { status: 'running', percent: 50 },
      { status: 'complete', percent: 100, result: { message: 'Sent.' } },
    ]);
    const ui = fakeUi();
    let polls = 0;
    const sleep = async () => {
      polls += 1;
      if (polls === 2) {
        ui.start.mock.calls[0][0]();  // the user clicks Cancel during the second wait, the job is running
        expect(ui.end).not.toHaveBeenCalled();  // the page stays busy
      }
    };

    await runJob(fetchFn, '/api/projects/datalad-server/sync/start', { project_path: '/p' }, { ui, sleep });

    const deletes = fetchFn.mock.calls.filter(([, o]) => o?.method === 'DELETE');
    expect(deletes.map(([u]) => u)).toEqual(['/api/projects/datalad-server/sync/j1/cancel']);
    expect(fetchFn.mock.calls.filter(([u]) => u === STATUS)).toHaveLength(3);  // polled to the end
    expect(ui.result).toHaveBeenCalledWith(
      'warning', 'Cancel requested. The job is already running and will finish in the background.',
    );
    expect(ui.result).not.toHaveBeenCalledWith('warning', 'Cancelled.');
    expect(ui.result.mock.calls.at(-1)).toEqual(['success', 'Sent.']);
    expect(ui.end).toHaveBeenCalledTimes(1);
  });

  it('a Cancel before the job started ends as Cancelled', async () => {
    const fetchFn = fakeFetch([{ status: 'cancelled', percent: 0 }]);
    const ui = fakeUi();
    ui.start.mockImplementation((cancel) => cancel());  // clicked before the start route answered

    await runJob(fetchFn, '/api/projects/datalad-server/sync/start', { project_path: '/p' }, { ui, sleep: now });

    const deletes = fetchFn.mock.calls.filter(([, o]) => o?.method === 'DELETE');
    expect(deletes).toHaveLength(1);
    expect(ui.result.mock.calls.at(-1)).toEqual(['warning', 'Cancelled.']);
    expect(ui.end).toHaveBeenCalledTimes(1);
  });
});
