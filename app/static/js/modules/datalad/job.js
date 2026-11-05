/**
 * Run one DataLad job route (sync, put on server, open from server, get data): start it, poll its status, show the
 * progress, let the user cancel. Every decision is the backend's; this only relays. `ui` draws it (page.js):
 *   start(cancel)                 progress shown; `cancel()` is what the Cancel button calls. The backend honours a
 *                                 cancel only before the job starts: a running job is polled to its end.
 *   progress(percent, message)    one status poll
 *   result(kind, text)            the outcome as a plain message
 *   errors(result, sendAnyway)    the job stopped on validation errors; `sendAnyway()` repeats it acknowledged
 *   end()                         progress hidden, buttons free again
 */

const JOB_ROUTE = '/api/projects/datalad-server/sync';  // status and cancel of every DataLad job
const POLL_MS = 800;
const MAX_POLLS = 2250;  // ~30 minutes
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const STILL_RUNNING = 'Cancel requested. The job is already running and will finish in the background.';

export async function runJob(fetchFn, route, body, options) {
    const { ui, onComplete = null, askIdentity = async () => false, sleep = wait } = options;
    const jobUrl = (jobId, action) => `${JOB_ROUTE}/${encodeURIComponent(jobId)}/${action}`;
    let jobId = null;
    let cancelRequested = false;
    let running = false;

    ui.start(() => {
        if (cancelRequested) return;
        cancelRequested = true;
        if (jobId) fetchFn(jobUrl(jobId, 'cancel'), { method: 'DELETE' }).catch(() => {});
        ui.result('warning', running ? STILL_RUNNING : 'Cancel requested.');
    });

    try {
        const start = await fetchFn(route, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const started = await start.json().catch(() => ({}));
        if (!start.ok || !started.job_id) throw new Error(started.error || 'Could not start.');
        jobId = started.job_id;
        if (cancelRequested) await fetchFn(jobUrl(jobId, 'cancel'), { method: 'DELETE' }).catch(() => {});

        for (let i = 0; i < MAX_POLLS; i += 1) {
            await sleep(POLL_MS);
            const response = await fetchFn(jobUrl(jobId, 'status'));
            if (!response.ok) throw new Error('Lost track of the job.');
            const status = await response.json();
            ui.progress(status.percent || 0, status.message || '');
            if (status.status === 'running' && !running) {
                running = true;
                if (cancelRequested) ui.result('warning', STILL_RUNNING);  // the cancel came too late
            }

            if (status.status === 'complete') {
                ui.result('success', (status.result && status.result.message) || status.message || 'Done.');
                if (onComplete) await onComplete(status.result || {});
                return;
            }
            if (status.status === 'cancelled') {
                ui.result('warning', 'Cancelled.');
                return;
            }
            if (status.status === 'error') {
                const result = status.result || {};
                if (result.reason === 'validation_errors') {
                    ui.errors(result, () => runJob(fetchFn, route, { ...body, allow_invalid: true }, options));
                } else if (result.reason === 'no_identity' && await askIdentity()) {
                    ui.end();
                    await runJob(fetchFn, route, body, options);
                } else {
                    ui.result('danger', status.error || 'The job failed.');
                }
                return;
            }
        }
        throw new Error('Gave up waiting after 30 minutes.');
    } catch (error) {
        ui.result('danger', error.message || 'The job failed.');
    } finally {
        ui.end();
    }
}

/** Open from server: run the job, and only when it is complete open the copy (POST /api/projects/current). */
export function openFromServer(fetchFn, location, target, { reload, ...options }) {
    return runJob(fetchFn, '/api/projects/datalad/open-from-server', { location, target }, {
        ...options,
        onComplete: async (result) => {
            const response = await fetchFn('/api/projects/current', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: result.path }),
            });
            const data = await response.json().catch(() => ({}));
            if (response.ok && data.success) {
                reload();
            } else {
                options.ui.result('warning', `The project was copied to ${result.path}, but could not be opened: ${data.error || 'unknown error'}`);
            }
        },
    });
}
