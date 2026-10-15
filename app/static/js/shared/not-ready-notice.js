// Any tool-page request answered with 409 project_not_ready gets a visible
// notice with a link back to the Projects page (the backend supplies the text).
export function isNotReadyResponse(status, body) {
    return status === 409 && !!body && body.code === 'project_not_ready';
}

export function installNotReadyNotice() {
    if (typeof window === 'undefined' || window.__prismNotReadyNoticeInstalled) return;
    window.__prismNotReadyNoticeInstalled = true;
    const original = window.fetch.bind(window);
    window.fetch = async (...args) => {
        const response = await original(...args);
        if (response.status === 409 && !location.pathname.startsWith('/projects')) {
            response.clone().json().then((body) => {
                if (!isNotReadyResponse(response.status, body)) return;
                const box = document.createElement('div');
                box.className = 'alert alert-warning position-fixed top-0 start-50 translate-middle-x mt-2';
                box.style.zIndex = 2000;
                box.append(`${body.error} `);
                const link = document.createElement('a');
                link.href = '/projects';
                link.textContent = 'Open the Projects page';
                box.append(link);
                document.body.appendChild(box);
            }).catch(() => {});
        }
        return response;
    };
}
