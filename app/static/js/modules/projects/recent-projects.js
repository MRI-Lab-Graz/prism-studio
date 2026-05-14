const recentProjectsKey = 'prism_recent_projects';
const recentProjectStatusCache = new Map();

function normalizeRecentProjectEntry(entry, resolveProjectIconClass) {
    if (!entry || typeof entry !== 'object') return null;

    const path = String(entry.path || '').trim();
    if (!path) return null;

    const name = String(entry.name || '').trim() || path.split(/[\\/]/).pop() || path;
    const icon = resolveProjectIconClass(entry.icon);

    return { path, name, icon };
}

export function createRecentProjectsController({
    fetchWithApiFallback,
    escapeHtml,
    resolveProjectIconClass,
    getCurrentProjectIcon,
}) {
    function syncRecentProjectsToServer(list) {
        fetchWithApiFallback('/api/projects/recent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ projects: list })
        }).catch(() => {
            // localStorage remains fallback source
        });
    }

    function getRecentProjects() {
        try {
            const raw = localStorage.getItem(recentProjectsKey);
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return [];
            return parsed
                .map((entry) => normalizeRecentProjectEntry(entry, resolveProjectIconClass))
                .filter(Boolean);
        } catch (err) {
            console.warn('Could not read recent projects', err);
            return [];
        }
    }

    function saveRecentProjects(list) {
        const limited = (Array.isArray(list) ? list : [])
            .map((entry) => normalizeRecentProjectEntry(entry, resolveProjectIconClass))
            .filter(Boolean)
            .slice(0, 5);
        try {
            localStorage.setItem(recentProjectsKey, JSON.stringify(limited));
        } catch (err) {
            console.warn('Could not save recent projects', err);
        }
        syncRecentProjectsToServer(limited);
    }

    function addRecentProject(name, path, icon = '') {
        if (!path) return;
        const safeName = name && name.trim() ? name.trim() : path.split(/[\\/]/).pop();
        const safeIcon = resolveProjectIconClass(icon || getCurrentProjectIcon());
        const list = getRecentProjects().filter((project) => project.path !== path);
        list.unshift({ name: safeName, path, icon: safeIcon });
        recentProjectStatusCache.delete(path);
        saveRecentProjects(list);
        renderRecentProjects();
    }

    function clearRecentProjects() {
        recentProjectStatusCache.clear();
        saveRecentProjects([]);
        renderRecentProjects();
    }

    async function isRecentProjectAvailable(path) {
        if (!path) return false;
        if (recentProjectStatusCache.has(path)) {
            return recentProjectStatusCache.get(path);
        }

        const statusPromise = fetchWithApiFallback('/api/projects/path-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        })
            .then(response => response.json().catch(() => null))
            .then((data) => {
                if (!data || data.success !== true) {
                    return null;
                }
                return Boolean(data.available);
            })
            .catch(() => null);

        recentProjectStatusCache.set(path, statusPromise);
        return statusPromise;
    }

    function renderRecentProjects() {
        const block = document.getElementById('recentProjectsBlock');
        const listEl = document.getElementById('recentProjectsList');
        if (!block || !listEl) return;

        const list = getRecentProjects();
        if (!list.length) {
            block.style.display = 'none';
            listEl.innerHTML = '';
            return;
        }

        Promise.all(list.map(async (project) => ({
            project,
            available: await isRecentProjectAvailable(project.path)
        }))).then((results) => {
            const availableProjects = results
                .filter(({ available }) => available !== false)
                .map(({ project }) => project);

            const unavailableProjects = results.filter(({ available }) => available === false);
            if (unavailableProjects.length > 0) {
                results
                    .filter(({ available }) => available === false)
                    .forEach(({ project }) => recentProjectStatusCache.delete(project.path));
                saveRecentProjects(availableProjects);
            }

            if (!availableProjects.length) {
                block.style.display = 'none';
                listEl.innerHTML = '';
                return;
            }

            block.style.display = 'block';
            listEl.innerHTML = availableProjects.map((project, index) => {
                const label = project.name || project.path;
                const iconClass = resolveProjectIconClass(project.icon);
                const safeLabel = escapeHtml(label);
                const safePath = escapeHtml(project.path || '');
                const safeIconClass = escapeHtml(iconClass);
                return `
                    <button type="button" class="btn btn-outline-secondary btn-sm recent-project-btn" data-path="${safePath}" data-name="${safeLabel}" data-icon="${safeIconClass}" data-recent-id="${index}" title="${safePath}">
                        <span class="me-1" aria-hidden="true">${safeIconClass}</span>${safeLabel}
                    </button>`;
            }).join('');
        }).catch(() => {
            block.style.display = 'none';
            listEl.innerHTML = '';
        });
    }

    function loadRecentProjectsFromServer() {
        fetchWithApiFallback('/api/projects/recent')
            .then(response => response.json())
            .then((data) => {
                if (!data || !data.success || !Array.isArray(data.projects)) return;
                localStorage.setItem(recentProjectsKey, JSON.stringify(data.projects.slice(0, 5)));
                renderRecentProjects();
            })
            .catch(() => {
                // keep local fallback
            });
    }

    return {
        getRecentProjects,
        saveRecentProjects,
        addRecentProject,
        clearRecentProjects,
        renderRecentProjects,
        loadRecentProjectsFromServer,
    };
}