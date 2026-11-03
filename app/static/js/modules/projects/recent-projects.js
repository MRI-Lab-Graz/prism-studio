import { isSameProjectPath } from '../../shared/project-state.js';

const recentProjectsKey = 'prism_recent_projects';
const recentProjectStatusCache = new Map();
const recentShown = 5;
const recentStoredMax = 20;

/** The first five recent projects get a button each; the rest go into the "older" pull-down. */
export function splitRecent(list) {
    return { shown: list.slice(0, recentShown), older: list.slice(recentShown) };
}

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
    function syncRecentProjectsToServer(body) {
        fetchWithApiFallback('/api/projects/recent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
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

    function cacheRecentProjects(list) {
        const limited = (Array.isArray(list) ? list : [])
            .map((entry) => normalizeRecentProjectEntry(entry, resolveProjectIconClass))
            .filter(Boolean)
            .slice(0, recentStoredMax);
        try {
            localStorage.setItem(recentProjectsKey, JSON.stringify(limited));
        } catch (err) {
            console.warn('Could not save recent projects', err);
        }
        return limited;
    }

    // Replaces the stored list on the server: only for clearing it. Adding sends one project.
    function saveRecentProjects(list) {
        syncRecentProjectsToServer({ projects: cacheRecentProjects(list) });
    }

    function addRecentProject(name, path, icon = '') {
        if (!path) return;
        const safeName = name && name.trim() ? name.trim() : path.split(/[\\/]/).pop();
        const safeIcon = resolveProjectIconClass(icon || getCurrentProjectIcon());
        const list = getRecentProjects().filter((project) => !isSameProjectPath(project.path, path));
        const project = { name: safeName, path, icon: safeIcon };
        list.unshift(project);
        recentProjectStatusCache.delete(path);
        cacheRecentProjects(list);
        syncRecentProjectsToServer({ project });
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
        const olderEl = document.getElementById('recentProjectsOlder');
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
            // An unavailable folder is only hidden: the server keeps it for when the drive is back.
            const availableProjects = results
                .filter(({ available }) => available !== false)
                .map(({ project }) => project);

            if (!availableProjects.length) {
                block.style.display = 'none';
                listEl.innerHTML = '';
                if (olderEl) olderEl.classList.add('d-none');
                return;
            }

            const { shown, older } = splitRecent(availableProjects);
            block.style.display = 'block';
            listEl.innerHTML = shown.map((project, index) => {
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

            if (olderEl) {
                olderEl.classList.toggle('d-none', !older.length);
                olderEl.innerHTML = `<option value="">Older projects (${older.length})…</option>` + older.map((project) => (
                    `<option value="${escapeHtml(project.path || '')}" title="${escapeHtml(project.path || '')}">${escapeHtml(project.name || project.path)}</option>`
                )).join('');
            }
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
                localStorage.setItem(recentProjectsKey, JSON.stringify(data.projects.slice(0, recentStoredMax)));
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