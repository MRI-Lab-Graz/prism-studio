/**
 * Shared polling lifecycle helper for converter tabs.
 * Keeps project-change cancellation behavior consistent across modalities.
 */

function buildAbortError(message) {
    if (typeof DOMException === 'function') {
        return new DOMException(message, 'AbortError');
    }
    const error = new Error(message);
    error.name = 'AbortError';
    return error;
}

export function isPollingAbortError(error) {
    return Boolean(error && error.name === 'AbortError');
}

export function createPollingRunState() {
    let activeController = null;

    return {
        start() {
            if (activeController) {
                activeController.abort(buildAbortError('Superseded by a new conversion run.'));
            }
            activeController = new AbortController();
            return activeController;
        },
        abortActive(message = 'Polling aborted due to project change.') {
            if (!activeController) {
                return false;
            }
            activeController.abort(buildAbortError(message));
            activeController = null;
            return true;
        },
        clear(controller) {
            if (controller && activeController === controller) {
                activeController = null;
            }
        },
    };
}
