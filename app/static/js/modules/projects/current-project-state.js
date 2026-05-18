export function createProjectsCurrentStateController({
    getProjectStateSnapshot,
    setProjectStateSnapshot,
}) {
    let currentProjectPath = '';
    let currentProjectName = '';
    let currentProjectIcon = '';

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

    function setGlobalProjectState(path, name, icon = '') {
        setProjectStateSnapshot(path, name, icon);
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
        };
    }

    function applyCurrentProject(project) {
        currentProjectPath = (project && project.path) ? String(project.path).trim() : '';
        currentProjectName = (project && project.name) ? String(project.name).trim() : '';
        const incomingIcon = normalizeProjectIconClass(project && project.icon);
        currentProjectIcon = currentProjectPath
            ? resolveProjectIconClass(incomingIcon || currentProjectIcon)
            : '';

        const existingPathInput = document.getElementById('existingPath');
        if (existingPathInput && currentProjectPath) {
            existingPathInput.value = currentProjectPath;
        }

        updateProjectTypeSelectionVisibility();

        if (window.updateNavbarProject) {
            window.updateNavbarProject(currentProjectName, currentProjectPath, currentProjectIcon);
            return;
        }

        setGlobalProjectState(currentProjectPath, currentProjectName, currentProjectIcon);
    }

    const globalProjectState = getProjectStateSnapshot();
    const globalProjectPath = String(globalProjectState.path || '').trim();
    const globalProjectName = String(globalProjectState.name || '').trim();
    const globalProjectIcon = normalizeProjectIconClass(globalProjectState.icon);

    if (projectsRoot) {
        currentProjectPath = projectsRoot.dataset.currentProjectPath || globalProjectPath || '';
        currentProjectName = projectsRoot.dataset.currentProjectName || globalProjectName || '';
        currentProjectIcon = currentProjectPath
            ? resolveProjectIconClass(projectsRoot.dataset.currentProjectIcon || globalProjectIcon)
            : '';
    } else {
        currentProjectPath = globalProjectPath;
        currentProjectName = globalProjectName;
        currentProjectIcon = currentProjectPath ? resolveProjectIconClass(globalProjectIcon) : '';
    }

    setGlobalProjectState(currentProjectPath, currentProjectName, currentProjectIcon);
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

        currentProjectPath = nextPath;
        currentProjectName = nextName;
        currentProjectIcon = nextPath ? resolveProjectIconClass(nextIcon || currentProjectIcon) : '';
        updateProjectTypeSelectionVisibility();
    });

    return {
        getCurrentProjectState,
        applyCurrentProject,
        resolveProjectIconClass,
        shouldHideProjectTypeSelectionWhenLoaded,
    };
}