/**
 * Switch DataLad on for the current project (POST /api/projects/datalad/enable, the CLI's `datalad enable`).
 * One backend call registers as many nested datasets as fit in its time budget; the backend says
 * (`enable_continue`) whether another call is needed, and reports a stuck registration as a failure. This only
 * repeats the call while it asks for that, as the CLI does.
 *
 * @param {Function} fetchFn - fetch-compatible (the page's API-fallback fetch)
 * @param {{askIdentity: () => Promise<boolean>, onProgress?: (text: string) => void}} options
 *        askIdentity asks for the name and email (git-identity-dialog.js) when the backend needs them
 * @returns {Promise<object>} the last backend answer
 */
export async function enableDatalad(fetchFn, { askIdentity, onProgress = () => {} }) {
    for (;;) {
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
        if (!data.enable_continue) return data;
        const remaining = data.datalad?.subdatasets_remaining_count ?? 0;
        onProgress(`${remaining} nested dataset(s) remaining. Continuing with ${data.datalad?.next_missing_subdataset || 'the next nested dataset'}...`);
    }
}
