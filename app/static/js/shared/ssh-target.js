/**
 * Trivial client-side check backing UI routing only (which alert/picker to
 * show) -- never used to decide anything the backend also decides. The
 * actual `[user@]host:/path` parsing lives in exactly one place,
 * server-side (`rsync_execution.is_remote_target`/`split_remote_target`),
 * so the remote folder picker sends the raw field value to the backend
 * rather than duplicating that parsing here.
 */
export function isRiaUrl(raw) {
    return String(raw || '').trim().toLowerCase().startsWith('ria+');
}
