// Any tool-page request answered with 409 project_not_ready gets a visible
// notice with a link back to the Projects page (the backend supplies the text).
export function isNotReadyResponse(status, body) {
    return status === 409 && !!body && body.code === 'project_not_ready';
}

/** Shows the notice for a blocked response (at most one); resolves true when a notice is on the page.
 *  Called from api.js (every fetchWithApiFallback request) and from the window.fetch wrapper below. */
export async function showNotReadyNotice(response, env = {}) {
    const doc = env.document || (typeof document !== 'undefined' ? document : null);
    const pathname = env.pathname ?? (typeof location !== 'undefined' ? location.pathname : '');
    if (!doc || response.status !== 409 || pathname.startsWith('/projects')) return false;
    let body;
    try {
        body = await response.clone().json();
    } catch (_error) {
        return false;
    }
    if (!isNotReadyResponse(response.status, body)) return false;
    if (doc.getElementById('prismNotReadyNotice')) return true;
    const box = doc.createElement('div');
    box.id = 'prismNotReadyNotice';
    box.className = 'alert alert-warning position-fixed top-0 start-50 translate-middle-x mt-2';
    box.style.zIndex = 2000;
    box.append(`${body.error} `);
    const link = doc.createElement('a');
    link.href = '/projects';
    link.textContent = 'Open the Projects page';
    box.append(link);
    doc.body.appendChild(box);
    return true;
}

// Plain fetch() calls on pages that do not go through api.js.
export function installNotReadyNotice() {
    if (typeof window === 'undefined' || window.__prismNotReadyNoticeInstalled) return;
    window.__prismNotReadyNoticeInstalled = true;
    const original = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const response = await original(...args);
        showNotReadyNotice(response);
        return response;
    };
}
