/**
 * Shared session registration utility
 */

/**
 * Create a registerSessionInProject function bound to a specific populateSessionPickers callback.
 * Both converter-bootstrap.js and survey-convert.js share the same POST logic; only
 * the post-register refresh callback differs per call site.
 *
 * @param {function} populateSessionPickers - Callback to refresh session picker UI after registration
 * @returns {function} registerSessionInProject(sessionId, tasks, modality, sourceFile, converter)
 */
export function createSessionRegistrar(populateSessionPickers) {
    return function registerSessionInProject(sessionId, tasks, modality, sourceFile, converter) {
        if (!sessionId || !tasks || !tasks.length) return;
        fetch('/api/projects/sessions/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                tasks,
                modality,
                source_file: sourceFile || '',
                converter: converter || 'manual',
            }),
        })
            .then((r) => r.json())
            .then(() => { populateSessionPickers(); })
            .catch(() => {});
    };
}
