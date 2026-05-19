export function createProjectsCurrentStateController({
    getProjectStateSnapshot,
    setProjectStateSnapshot,
}) {
    let currentProjectPath = '';
    let currentProjectName = '';
    let currentProjectIcon = '';
    let currentProjectDatalad = null;

    const allowedProjectIcons = [
        '🧪',
        '🔬',
        '🧬',
        '🧠',
        '⚗️',
        '🩺',
        '📊',
        '🧫',
        '🔭',
        '🧲',
    ];

    const projectsRoot = document.getElementById('projectsRoot');

    function normalizeProjectIconClass(iconClass) {
        const icon = String(iconClass || '').trim();
        if (!icon) return '';
        return allowedProjectIcons.includes(icon) ? icon : '';
    }

    function resolveProjectIconClass(iconClass) {
        return normalizeProjectIconClass(iconClass) || '🧪';
    }

    function normalizeDataladState(dataladState, fallbackPath = '') {
        if (!dataladState || typeof dataladState !== 'object' || Array.isArray(dataladState)) {
            return {
                enabled: false,
                available: false,
                annexAvailable: false,
                canSave: false,
                canEnable: false,
                message: fallbackPath ? 'Current project is not a DataLad dataset.' : 'Load a project to see DataLad status.',
                path: fallbackPath,
            };
        }

        const resolvedPath = (typeof dataladState.path === 'string' ? dataladState.path.trim() : '') || fallbackPath;
        return {
            enabled: Boolean(dataladState.enabled),
            available: Boolean(dataladState.available),
            annexAvailable: Boolean(dataladState.annex_available ?? dataladState.annexAvailable),
            canSave: Boolean(dataladState.can_save ?? dataladState.canSave),
            canEnable: Boolean(dataladState.can_enable ?? dataladState.canEnable),
            message: typeof dataladState.message === 'string' && dataladState.message.trim()
                ? dataladState.message.trim()
                : (resolvedPath ? 'Current project is not a DataLad dataset.' : 'Load a project to see DataLad status.'),
            path: resolvedPath,
        };
    }

    function setGlobalProjectState(pathOrState, name, icon = '', datalad = undefined) {
        if (pathOrState && typeof pathOrState === 'object' && !Array.isArray(pathOrState)) {
            setProjectStateSnapshot(pathOrState);
            return;
        }

        setProjectStateSnapshot(pathOrState, name, icon, datalad);
    }

    function shouldHideProjectTypeSelectionWhenLoaded() {
        if (!projectsRoot) {
            return false;
        }

        return String(projectsRoot.dataset.hideProjectOptionsOnLoaded || '').trim().toLowerCase() === 'true';
    }

    function updateProjectTypeSelectionVisibility() {
        const projectTypeSelectionRow = document.getElementById('projectTypeSelectionRow');
        const openProjectFlowStrip = document.getElementById('openProjectFlowStrip');
        if (!projectTypeSelectionRow) {
            if (!openProjectFlowStrip) {
                return;
            }
        }

        const shouldHide = shouldHideProjectTypeSelectionWhenLoaded() && Boolean(String(currentProjectPath || '').trim());
        projectTypeSelectionRow?.classList.toggle('d-none', shouldHide);
        openProjectFlowStrip?.classList.toggle('d-none', shouldHide);
    }

    function getCurrentProjectState() {
        return {
            path: currentProjectPath,
            name: currentProjectName,
            icon: currentProjectIcon,
            datalad: currentProjectDatalad,
        };
    }

    function applyCurrentProject(project) {
        currentProjectPath = (project && project.path) ? String(project.path).trim() : '';
        currentProjectName = (project && project.name) ? String(project.name).trim() : '';
        const incomingIcon = normalizeProjectIconClass(project && project.icon);
        currentProjectIcon = currentProjectPath
            ? resolveProjectIconClass(incomingIcon || currentProjectIcon)
            : '';
        currentProjectDatalad = normalizeDataladState(project && project.datalad, currentProjectPath);

        const existingPathInput = document.getElementById('existingPath');
        if (existingPathInput && currentProjectPath) {
            existingPathInput.value = currentProjectPath;
        }

        updateProjectTypeSelectionVisibility();

        if (window.updateNavbarProject) {
            window.updateNavbarProject(currentProjectName, currentProjectPath, currentProjectIcon, currentProjectDatalad);
            return;
        }

        setGlobalProjectState({
            path: currentProjectPath,
            name: currentProjectName,
            icon: currentProjectIcon,
            datalad: currentProjectDatalad,
        });
    }

    const globalProjectState = getProjectStateSnapshot();
    const globalProjectPath = String(globalProjectState.path || '').trim();
    const globalProjectName = String(globalProjectState.name || '').trim();
    const globalProjectIcon = normalizeProjectIconClass(globalProjectState.icon);
    const globalProjectDatalad = normalizeDataladState(globalProjectState.datalad, globalProjectPath);

    if (projectsRoot) {
        currentProjectPath = projectsRoot.dataset.currentProjectPath || globalProjectPath || '';
        currentProjectName = projectsRoot.dataset.currentProjectName || globalProjectName || '';
        currentProjectIcon = currentProjectPath
            ? resolveProjectIconClass(projectsRoot.dataset.currentProjectIcon || globalProjectIcon)
            : '';
        currentProjectDatalad = normalizeDataladState(globalProjectDatalad, currentProjectPath);
    } else {
        currentProjectPath = globalProjectPath;
        currentProjectName = globalProjectName;
        currentProjectIcon = currentProjectPath ? resolveProjectIconClass(globalProjectIcon) : '';
        currentProjectDatalad = normalizeDataladState(globalProjectDatalad, currentProjectPath);
    }

    setGlobalProjectState({
        path: currentProjectPath,
        name: currentProjectName,
        icon: currentProjectIcon,
        datalad: currentProjectDatalad,
    });
    updateProjectTypeSelectionVisibility();

    window.addEventListener('prism-project-changed', function(event) {
        const eventState = event && event.detail ? event.detail : null;
        const fallbackState = getProjectStateSnapshot();
        const nextPath = eventState && typeof eventState.path === 'string'
            ? eventState.path.trim()
            : String(fallbackState.path || '').trim();
        const nextName = eventState && typeof eventState.name === 'string'
            ? eventState.name.trim()
            : String(fallbackState.name || '').trim();
        const nextIcon = eventState && typeof eventState.icon === 'string'
            ? eventState.icon.trim()
            : String(fallbackState.icon || '').trim();
        const nextDatalad = normalizeDataladState(
            eventState && eventState.datalad,
            nextPath || String(fallbackState.path || '').trim()
        );

        currentProjectPath = nextPath;
        currentProjectName = nextName;
        currentProjectIcon = nextPath ? resolveProjectIconClass(nextIcon || currentProjectIcon) : '';
        currentProjectDatalad = nextDatalad;
        updateProjectTypeSelectionVisibility();
    });

    return {
        getCurrentProjectState,
        applyCurrentProject,
        resolveProjectIconClass,
        shouldHideProjectTypeSelectionWhenLoaded,
    };
}