export function initProjectsPageBootstrap({
    initProjectFieldHints,
    initBeginnerHelpMode,
    initBackendMonitoringToggle,
    initDedicatedTerminalToggle,
    loadGlobalSettings,
    loadLibraryInfo,
    showStudyMetadataCard,
    showExportCard,
    showMethodsCard,
    renderRecentProjects,
    loadRecentProjectsFromServer,
    ensureOpenSectionVisibleForLoadedProject,
    getCurrentProjectState,
    addRecentProject,
    fixAllIssues,
    fixIssue,
    runProjectValidation,
    getOpenProjectActionPath,
    submitOpenProjectPath,
    clearRecentProjects,
    initProjectSelectionUi,
    clearCurrentProject,
    useDefaultLibrary,
    clearGlobalLibrary,
}) {
    const isWindows = navigator.platform.toUpperCase().indexOf('WIN') > -1;
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') > -1;
    const existingPathInput = document.getElementById('existingPath');
    const projectPathInput = document.getElementById('projectPath');
    const pathHelpTooltip = document.getElementById('pathHelpTooltip');

    if (existingPathInput) {
        if (isWindows) {
            existingPathInput.placeholder = 'C:\\Users\\YourName\\MyProject\\project.json';
        } else if (isMac) {
            existingPathInput.placeholder = '/Users/YourName/MyProject/project.json';
        } else {
            existingPathInput.placeholder = '/home/username/MyProject/project.json';
        }
    }

    if (projectPathInput) {
        if (isWindows) {
            projectPathInput.placeholder = 'C:\\Users\\YourName\\Documents';
        } else if (isMac) {
            projectPathInput.placeholder = '/Users/YourName/Documents';
        } else {
            projectPathInput.placeholder = '/home/username/Documents';
        }
    }

    if (pathHelpTooltip) {
        const osExample = isWindows ? 'C:\\Users\\YourName\\Documents\\MyProject\\project.json' :
            isMac ? '/Users/YourName/Documents/MyProject/project.json' :
            '/home/username/Documents/MyProject/project.json';
        const tooltipTitle = `Type the full path to your project folder or <code>project.json</code> file (e.g., <code>${osExample}</code>), or click Browse to select it.`;

        pathHelpTooltip.setAttribute('title', tooltipTitle);
        pathHelpTooltip.setAttribute('data-bs-original-title', tooltipTitle);

        if (window.bootstrap && typeof window.bootstrap.Tooltip === 'function') {
            window.bootstrap.Tooltip.getOrCreateInstance(pathHelpTooltip);
        }
    }

    initProjectFieldHints();
    initBeginnerHelpMode();
    initBackendMonitoringToggle();
    initDedicatedTerminalToggle();

    loadGlobalSettings();
    loadLibraryInfo();
    showStudyMetadataCard();
    showExportCard();
    showMethodsCard();
    renderRecentProjects();
    loadRecentProjectsFromServer();
    ensureOpenSectionVisibleForLoadedProject();

    const currentProjectState = getCurrentProjectState();
    if (currentProjectState.path) {
        addRecentProject(currentProjectState.name, currentProjectState.path, currentProjectState.icon);
    }

    const sections = [
        { element: 'openProjectSection', chevron: 'openProjectChevron' },
        { element: 'studyMetadataSection', chevron: 'studyMetadataChevron' },
        { element: 'methodsSectionBody', chevron: 'methodsSectionChevron' },
        { element: 'exportSection', chevron: 'exportChevron' },
        { element: 'settingsSection', chevron: 'settingsChevron' }
    ];

    sections.forEach((section) => {
        const el = document.getElementById(section.element);
        const chevron = document.getElementById(section.chevron);
        if (el && chevron) {
            el.addEventListener('shown.bs.collapse', function() {
                chevron.classList.replace('fa-chevron-down', 'fa-chevron-up');
            });
            el.addEventListener('hidden.bs.collapse', function() {
                chevron.classList.replace('fa-chevron-up', 'fa-chevron-down');
            });
        }
    });

    document.querySelectorAll('.card-header[data-bs-toggle="collapse"][role="button"]').forEach((header) => {
        if (!header.hasAttribute('tabindex')) {
            header.setAttribute('tabindex', '0');
        }
        header.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                header.click();
            }
        });
    });

    const validationResultDiv = document.getElementById('validationResult');
    if (validationResultDiv) {
        validationResultDiv.addEventListener('click', (event) => {
            const fixAllBtn = event.target.closest('[data-action="fix-all"]');
            if (fixAllBtn) { fixAllIssues(fixAllBtn.dataset.path); return; }
            const fixOneBtn = event.target.closest('[data-action="fix-issue"]');
            if (fixOneBtn) { fixIssue(fixOneBtn.dataset.path, fixOneBtn.dataset.code); return; }
        });
    }

    const recentList = document.getElementById('recentProjectsList');
    if (recentList) {
        recentList.addEventListener('click', (event) => {
            const btn = event.target.closest('.recent-project-btn');
            if (!btn) return;
            const path = btn.getAttribute('data-path');
            if (path) {
                submitOpenProjectPath(path);
            }
        });
    }

    const clearRecentBtn = document.getElementById('clearRecentProjectsBtn');
    if (clearRecentBtn) {
        clearRecentBtn.addEventListener('click', () => {
            if (!confirm('Clear recent projects list?')) return;
            clearRecentProjects();
        });
    }

    initProjectSelectionUi();

    const clearCurrentProjectBtn = document.getElementById('clearCurrentProjectBtn');
    if (clearCurrentProjectBtn) {
        clearCurrentProjectBtn.addEventListener('click', () => {
            clearCurrentProject();
        });
    }

    const useDefaultLibraryBtn = document.getElementById('useDefaultLibraryBtn');
    if (useDefaultLibraryBtn) {
        useDefaultLibraryBtn.addEventListener('click', () => {
            useDefaultLibrary();
        });
    }

    const clearGlobalLibraryBtn = document.getElementById('clearGlobalLibraryBtn');
    if (clearGlobalLibraryBtn) {
        clearGlobalLibraryBtn.addEventListener('click', () => {
            clearGlobalLibrary();
        });
    }
}