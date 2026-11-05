/**
 * POST the DataLad save. The backend refuses a dataset with PRISM errors; this asks the user
 * and, on "yes", repeats the request with allow_invalid (the CLI's --allow-invalid). The decision
 * itself stays in the backend: this only relays the user's answer.
 *
 * @param {Function} fetchFn - fetch-compatible (the page's API-fallback fetch)
 * @param {string} message - commit message
 * @param {(text: string) => boolean} confirmFn - asks the user
 * @returns {Promise<{response: Response, data: object}>}
 */
export async function saveDataladSnapshot(fetchFn, message, confirmFn = (text) => window.confirm(text)) {
    const post = async (extra) => {
        const response = await fetchFn('/api/projects/datalad/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, ...extra })
        });
        const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
        return { response, data };
    };

    const result = await post({});
    if (!result.data.validation_blocked) return result;

    const errors = result.data.validation_errors || [];
    const reason = errors.length
        ? `The dataset is not PRISM-valid:\n- ${errors.slice(0, 5).join('\n- ')}${errors.length > 5 ? `\n... and ${errors.length - 5} more` : ''}`
        : result.data.error;
    return confirmFn(`${reason}\n\nSave anyway?`) ? post({ allow_invalid: true }) : result;
}
