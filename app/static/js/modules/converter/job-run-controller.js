/**
 * Shared conversion run controller.
 * Prevents duplicate submits and tracks one active backend job per tab runner.
 */

export function createJobRunController() {
    let runActive = false;
    let activeJobId = '';
    let cancelRequested = false;

    return {
        tryStartRun() {
            if (runActive) {
                return false;
            }
            runActive = true;
            return true;
        },
        finishRun() {
            runActive = false;
            activeJobId = '';
            cancelRequested = false;
        },
        setActiveJobId(jobId) {
            activeJobId = String(jobId || '').trim();
            cancelRequested = false;
        },
        hasActiveJob() {
            return Boolean(activeJobId);
        },
        async cancelActiveJob({ buildCancelUrl }) {
            if (!activeJobId || cancelRequested) {
                return false;
            }

            cancelRequested = true;
            try {
                const response = await fetch(buildCancelUrl(activeJobId), { method: 'POST' });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(payload.error || 'Failed to cancel conversion');
                }
                return true;
            } catch (error) {
                cancelRequested = false;
                throw error;
            }
        },
    };
}
