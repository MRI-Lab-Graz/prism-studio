/**
 * Shared session registration utility
 */

import { resolveCurrentProjectPath } from './project-state.js';

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
        const currentProjectPath = resolveCurrentProjectPath();
        fetch('/api/projects/sessions/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                tasks,
                modality,
                source_file: sourceFile || '',
                converter: converter || 'manual',
                project_path: currentProjectPath,
            }),
        })
            .then(async (response) => ({
                ok: response.ok,
                data: await response.json().catch(() => ({})),
            }))
            .then(({ ok, data }) => {
                if (!ok || (data && data.success === false)) {
                    throw new Error((data && data.error) || 'Failed to register session in project metadata.');
                }
                populateSessionPickers(currentProjectPath);
            })
            .catch((error) => {
                const errorMessage = (error && error.message) ? error.message : 'Failed to register session.';
                console.warn('Session registration warning:', errorMessage);
                window.dispatchEvent(new CustomEvent('prism-session-register-failed', {
                    detail: {
                        error: errorMessage,
                        sessionId,
                        modality,
                        sourceFile: sourceFile || '',
                        converter: converter || 'manual',
                    },
                }));
            });
    };
}
