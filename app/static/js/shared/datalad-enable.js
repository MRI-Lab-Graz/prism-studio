/**
 * Switch DataLad on for the current project (POST /api/projects/datalad/enable, the CLI's `datalad enable`).
 * Each backend call registers as many nested datasets as fit in its time budget and says how many are left, so this
 * repeats the call until none is left. A call that converts nothing and reports a failure is a stall; three in a row
 * stop with that failure instead of grinding on for hours.
 *
 * @param {Function} fetchFn - fetch-compatible (the page's API-fallback fetch)
 * @param {{askIdentity: () => Promise<boolean>, onProgress?: (text: string) => void}} options
 *        askIdentity asks for the name and email (git-identity-dialog.js) when the backend needs them
 * @returns {Promise<object>} the last backend answer
 */
const MAX_CALLS = 500;
const MAX_CONSECUTIVE_STALLS = 3;

export async function enableDatalad(fetchFn, { askIdentity, onProgress = () => {} }) {
    let stalls = 0;
    for (let call = 1; ; call += 1) {
        const response = await fetchFn('/api/projects/datalad/enable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirmed: true }),
        });
        const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
        if (data.needs_git_identity) {
            if (await askIdentity()) continue;
            throw new Error('DataLad was not enabled: this project needs a name and email first.');
        }
        if (!response.ok || !data.success) {
            throw new Error(data.error || data.message || 'Could not enable DataLad.');
        }

        const remaining = Number.parseInt(String(data.datalad?.subdatasets_remaining_count ?? 0), 10) || 0;
        if (remaining <= 0 || call >= MAX_CALLS) return data;

        const failures = data.datalad?.subdataset_failures ?? [];
        stalls = (data.datalad?.subdatasets_created?.length ?? 0) === 0 && failures.length > 0 ? stalls + 1 : 0;
        if (stalls >= MAX_CONSECUTIVE_STALLS) {
            throw new Error(`Registration is stuck on the same nested dataset after ${stalls} attempts and made no further progress: ${failures[0]}`);
        }
        onProgress(`${remaining} nested dataset(s) remaining. Continuing with ${data.datalad?.next_missing_subdataset || 'the next nested dataset'}...`);
    }
}
