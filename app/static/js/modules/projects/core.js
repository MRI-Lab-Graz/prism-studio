/**
 * Projects Module - Core
 * Main project management logic: create, open, load, validate projects
 */

import { setButtonLoading, textToArray as _textToArray } from './helpers.js';
import { initCreateProjectController } from './create-project.js';
import { initCreatePreflightController } from './create-preflight.js';
import { createProjectsCurrentStateController } from './current-project-state.js';
import { initProjectInitOnBidsController } from './init-on-bids.js';
import { initOpenProjectController } from './open-project.js';
import { initProjectsPageBootstrap } from './page-bootstrap.js';
import {
    initBeginnerHelpMode,
    initProjectFieldHints,
} from './project-hints.js';
import { initProjectPathPickers } from './path-pickers.js';
import { initProjectSelectionController } from './project-selection.js';
import { createProjectMaintenanceActions } from './maintenance-actions.js';
import { createRecentProjectsController } from './recent-projects.js';
import {
    clearGlobalLibrary,
    initBackendMonitoringToggle,
    initDedicatedTerminalToggle,
    initProjectSettingsForm,
    loadGlobalSettings,
    loadLibraryInfo,
    useDefaultLibrary,
} from './settings.js';
import { validateProjectField } from './validation.js';
import { initProjectFileBrowser } from './file-browser.js';
import {
    hasUnsavedStudyMetadataChanges,
    isStudyMetadataBusy,
    validateAllMandatoryFields,
    validateDatasetDescriptionDraftLive,
    bindProjectBoxActionButtons,
    getCitationAuthorsList,
    getEthicsApprovals,
    getFundingList,
    getRecMethodList,
    getRecLocationList,
    getYearMonthValue,
    resetStudyMetadataForm,
    saveProjectSchemaConfig,
    showStudyMetadataCard,
    showMethodsCard,
    updateCreateProjectButton
} from './metadata.js?v=20260515-4';
import {
    getProjectStateSnapshot,
    setProjectStateSnapshot,
} from '../../shared/project-state.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { escapeHtml } from '../../shared/dom.js';

let projectsPageInitialized = false;

function setCreateResultHtml(html, scope = 'server') {
    const resultDiv = document.getElementById('createResult');
    if (!resultDiv) return;

    resultDiv.dataset.scope = scope;
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = html;
}

function clearCreateResult(scope = null) {
    const resultDiv = document.getElementById('createResult');
    if (!resultDiv) return;
    if (scope && resultDiv.dataset.scope !== scope) return;

    resultDiv.style.display = 'none';
    resultDiv.innerHTML = '';
    delete resultDiv.dataset.scope;
}

function joinProjectTargetPath(projectPath, projectName) {
    const parentPath = String(projectPath || '').trim();
    const name = String(projectName || '').trim();
    if (!parentPath || !name) return '';

    if (parentPath.endsWith('/') || parentPath.endsWith('\\')) {
        return parentPath + name;
    }

    const separator = parentPath.includes('/') ? '/' : '\\';
    return parentPath + separator + name;
}

const currentProjectStateController = createProjectsCurrentStateController({
    getProjectStateSnapshot,
    setProjectStateSnapshot,
});

const getCurrentProjectState = currentProjectStateController.getCurrentProjectState;
const applyCurrentProject = currentProjectStateController.applyCurrentProject;
const resolveProjectIconClass = currentProjectStateController.resolveProjectIconClass;
const shouldHideProjectTypeSelectionWhenLoaded = currentProjectStateController.shouldHideProjectTypeSelectionWhenLoaded;

const recentProjectsController = createRecentProjectsController({
    fetchWithApiFallback,
    escapeHtml,
    resolveProjectIconClass,
    getCurrentProjectIcon: () => getCurrentProjectState().icon,
});

const getRecentProjects = recentProjectsController.getRecentProjects;
const saveRecentProjects = recentProjectsController.saveRecentProjects;
const addRecentProject = recentProjectsController.addRecentProject;
const clearRecentProjects = recentProjectsController.clearRecentProjects;
const renderRecentProjects = recentProjectsController.renderRecentProjects;
const loadRecentProjectsFromServer = recentProjectsController.loadRecentProjectsFromServer;

export { getRecentProjects, saveRecentProjects, addRecentProject, renderRecentProjects };

async function ensureOpenSectionVisibleForLoadedProject() {
    const path = String(getCurrentProjectState().path || '').trim();
    if (!path || !shouldHideProjectTypeSelectionWhenLoaded()) {
        return;
    }

    const openSection = document.getElementById('section-open');
    if (openSection && !openSection.classList.contains('active')) {
        selectProjectType('open');
    }

    const existingPathInput = document.getElementById('existingPath');
    if (existingPathInput && !String(existingPathInput.value || '').trim()) {
        existingPathInput.value = path;
    }

    await loadProjectWithoutValidation(path, null, { skipContextGuard: true });
}

initProjectPathPickers({
    fetchWithApiFallback,
    validateProjectField,
    clearCreateResult,
});

initProjectSettingsForm();

const createPreflightController = initCreatePreflightController({
    fetchWithApiFallback,
    escapeHtml,
    clearCreateResult,
    setCreateResultHtml,
    joinProjectTargetPath,
    getSelectProjectType: () => selectProjectType,
});

const resetCreateTargetStatusChecks = createPreflightController.resetCreateTargetStatusChecks;
const checkCreateTargetStatus = createPreflightController.checkCreateTargetStatus;
const submitOpenProjectPath = createPreflightController.submitOpenProjectPath;

const projectSelectionController = initProjectSelectionController({
    fetchWithApiFallback,
    getCurrentProjectState,
    applyCurrentProject,
    hasUnsavedStudyMetadataChanges,
    isStudyMetadataBusy,
    clearCreateResult,
    resetCreateTargetStatusChecks,
    resetStudyMetadataForm,
    showStudyMetadataCard,
});

const confirmProjectContextChange = projectSelectionController.confirmProjectContextChange;
const selectProjectType = projectSelectionController.selectProjectType;

export { selectProjectType };

// ── Init PRISM on existing BIDS dataset ─────────────────────────────────────

initProjectInitOnBidsController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    showMethodsCard,
});

initProjectFileBrowser({ fetchWithApiFallback });

initCreateProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    textToArray: _textToArray,
    getProjectStateSnapshot,
    setCreateResultHtml,
    joinProjectTargetPath,
    resetCreateTargetStatusChecks,
    checkCreateTargetStatus,
    validateAllMandatoryFields,
    validateDatasetDescriptionDraftLive,
    getCitationAuthorsList,
    getEthicsApprovals,
    getFundingList,
    getRecMethodList,
    getRecLocationList,
    getYearMonthValue,
    saveProjectSchemaConfig,
    applyCurrentProject,
    getCurrentProjectState,
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showMethodsCard,
});

const openProjectController = initOpenProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    resolveProjectIconClass,
    getCurrentProjectState,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showMethodsCard,
    bindProjectBoxActionButtons,
});

const getOpenProjectActionPath = openProjectController.getOpenProjectActionPath;
const loadProjectWithoutValidation = openProjectController.loadProjectWithoutValidation;

const projectMaintenanceActions = createProjectMaintenanceActions({
    fetchWithApiFallback,
    reloadProject: (path) => loadProjectWithoutValidation(path, null, { skipContextGuard: true }),
    onCurrentProjectCleared: () => window.location.reload(),
});

const fixIssue = projectMaintenanceActions.fixIssue;
const fixAllIssues = projectMaintenanceActions.fixAllIssues;
const clearCurrentProject = projectMaintenanceActions.clearCurrentProject;

export { fixIssue, fixAllIssues, clearCurrentProject };

// ===== INITIALIZATION =====

export function initProjectsPage() {
    if (projectsPageInitialized) {
        return;
    }
    projectsPageInitialized = true;

    initProjectsPageBootstrap({
        initProjectFieldHints,
        initBeginnerHelpMode,
        initBackendMonitoringToggle,
        initDedicatedTerminalToggle,
        loadGlobalSettings,
        loadLibraryInfo,
        showStudyMetadataCard,
        showMethodsCard,
        renderRecentProjects,
        loadRecentProjectsFromServer,
        ensureOpenSectionVisibleForLoadedProject,
        getCurrentProjectState,
        addRecentProject,
        fixAllIssues,
        fixIssue,
        getOpenProjectActionPath,
        submitOpenProjectPath,
        clearRecentProjects,
        initProjectSelectionUi: () => projectSelectionController.initProjectSelectionUi(),
        clearCurrentProject,
        useDefaultLibrary,
        clearGlobalLibrary,
    });
}

// Expose for inline handlers and legacy code
window.selectProjectType = selectProjectType;
window.fixIssue = fixIssue;
window.fixAllIssues = fixAllIssues;
window.clearCurrentProject = clearCurrentProject;
window.useDefaultLibrary = useDefaultLibrary;
window.clearGlobalLibrary = clearGlobalLibrary;
