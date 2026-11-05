/**
 * Ask the backend to get the latest saved changes from the server (the CLI's `datalad update`). Every decision
 * (is there a server, are there unsaved changes, can it fast-forward) is the backend's; this only relays the answer.
 *
 * @param {Function} fetchFn - fetch-compatible (the page's API-fallback fetch)
 * @returns {Promise<{data: object, notice: {text: string, kind: string, label: string} | null}>}
 *          notice is null when there is nothing to tell the user (no server yet, or already up to date)
 */
export async function getLatestFromServer(fetchFn) {
    const response = await fetchFn('/api/projects/datalad/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}'
    });
    const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
    if (!data.success) {
        return { data, notice: { text: data.error || 'Could not get the latest changes.', kind: 'danger', label: 'Not updated' } };
    }
    if (data.skipped || !data.updated) return { data, notice: null };
    return { data, notice: { text: data.message || 'Got the latest changes from the server.', kind: 'success', label: 'Updated' } };
}
