/**
 * Shared job-status polling helper for async converter tasks.
 */

/**
 * Poll an async status endpoint until completion with timeout + retry handling.
 *
 * @param {Object} options
 * @param {(cursor:number)=>Promise<Object>} options.fetchStatus - Fetch one status payload.
 * @param {(logs:Array, status:Object)=>void} [options.onLogs] - Consume incremental logs.
 * @param {(status:Object)=>void} [options.onPollData] - Hook for progress updates.
 * @param {(ctx:{attempt:number,maxAttempts:number,error:any})=>void} [options.onRetryWarning]
 * @param {number} [options.initialCursor=0]
 * @param {number} [options.intervalMs=500]
 * @param {number} [options.timeoutMs=300000]
 * @param {number} [options.maxConsecutiveErrors=4]
 * @param {string} [options.timeoutErrorMessage='Job status timed out.']
 * @param {string} [options.statusFailureMessage='Failed to retrieve job status after multiple attempts.']
 * @param {(status:Object)=>Array} [options.getLogs]
 * @param {(status:Object,cursor:number,logs:Array)=>number} [options.getNextCursor]
 * @param {(status:Object)=>boolean} [options.isDone]
 * @param {(status:Object)=>boolean} [options.isSuccess]
 * @param {(status:Object)=>string} [options.getFailureError]
 * @returns {Promise<Object>} Final successful status payload.
 */
export async function pollJobStatus(options) {
    const {
        fetchStatus,
        onLogs,
        onPollData,
        onRetryWarning,
        initialCursor = 0,
        intervalMs = 500,
        timeoutMs = 300000,
        maxConsecutiveErrors = 4,
        timeoutErrorMessage = 'Job status timed out.',
        statusFailureMessage = 'Failed to retrieve job status after multiple attempts.',
        getLogs = (status) => (Array.isArray(status && status.logs) ? status.logs : []),
        getNextCursor = (status, cursor, logs) => (
            Number.isInteger(status && status.next_cursor)
                ? status.next_cursor
                : cursor + logs.length
        ),
        isDone = (status) => Boolean(status && status.done),
        isSuccess = (status) => Boolean(status && status.success),
        getFailureError = (status) => (status && status.error) || 'Job failed.',
    } = options || {};

    if (typeof fetchStatus !== 'function') {
        throw new Error('pollJobStatus requires a fetchStatus callback.');
    }

    let cursor = Number.isInteger(initialCursor) ? initialCursor : 0;
    let consecutiveErrors = 0;
    const startedAt = Date.now();

    while (true) {
        if (Date.now() - startedAt > timeoutMs) {
            throw new Error(timeoutErrorMessage);
        }

        await new Promise((resolve) => setTimeout(resolve, intervalMs));

        let statusData = null;
        try {
            statusData = await fetchStatus(cursor);
            consecutiveErrors = 0;
        } catch (error) {
            consecutiveErrors += 1;
            if (typeof onRetryWarning === 'function') {
                onRetryWarning({
                    attempt: consecutiveErrors,
                    maxAttempts: maxConsecutiveErrors,
                    error,
                });
            }
            if (consecutiveErrors >= maxConsecutiveErrors) {
                throw new Error(statusFailureMessage);
            }
            continue;
        }

        const logs = getLogs(statusData);
        if (typeof onLogs === 'function' && logs.length > 0) {
            onLogs(logs, statusData);
        }

        cursor = getNextCursor(statusData, cursor, logs);

        if (typeof onPollData === 'function') {
            onPollData(statusData);
        }

        if (!isDone(statusData)) {
            continue;
        }

        if (!isSuccess(statusData)) {
            throw new Error(getFailureError(statusData));
        }

        return statusData;
    }
}
