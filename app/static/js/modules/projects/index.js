/**
 * Projects Module Aggregator
 * Centralizes all project management functionality
 * 
 * Exports:
 * - Shared utilities (api, validation, dom, storage)
 * - Project-specific modules (helpers, validation, core, export, metadata)
 */

// Export all shared utilities
export {
    isValidProjectName, 
    validateRequiredFields, 
    clearFormValidation, 
    showValidationError, 
    clearValidationErrors 
} from '../../shared/validation.js';
export { 
    getById, 
    querySelect, 
    querySelectAll, 
    addEvent, 
    removeEvent, 
    show, 
    hide, 
    addClass, 
    removeClass, 
    setText, 
    getText 
} from '../../shared/dom.js';

// Import project-specific modules
import * as helpers from './helpers.js';
import * as validation from './validation.js';
import * as core from './core.js';
import * as exportModule from './export.js';
import * as dataladServerModule from './datalad_server.js';
import { initDataladSetupCheck } from './datalad_setup_check.js';
import {
    clearGlobalLibrary,
    initBackendMonitoringToggle,
    initDataladForNewProjectsToggle,
    initDedicatedTerminalToggle,
    initProjectSettingsForm,
    initStudyApplicationImportToggle,
    loadGlobalSettings,
    loadLibraryInfo,
    useDefaultLibrary,
} from './settings.js';
import { initProjectPathPickers } from './path-pickers.js';
import { createDataladCard } from './datalad-card.js';
import { createProjectsCurrentStateController } from './current-project-state.js';
import { getProjectStateSnapshot, setProjectStateSnapshot } from '../../shared/project-state.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import * as rsyncServerModule from './rsync_server.js';
import * as pushServerToggleModule from './push_server_toggle.js';
import * as metadata from './metadata.js?v=20260515-4';

// Re-export project modules for direct access
export { helpers, validation, core, exportModule, dataladServerModule, rsyncServerModule, metadata };

// Export individual functions for backward compatibility
export const { setButtonLoading, showAlert, showToast, showTopFeedback, textToArray } = helpers;
export const { validateProjectField, initProjectValidation } = validation;
export const { 
    initProjectsPage,
    getRecentProjects, 
    saveRecentProjects, 
    addRecentProject, 
    renderRecentProjects, 
    selectProjectType
} = core;
export const { showExportCard, initExportForm, initAndExport, initOpenMindsExport, loadExportPreferences, initializeProjectsExport } = exportModule;
export const { showDataladServerCard, initDataladServerSection } = dataladServerModule;
export const { showRsyncServerCard, initRsyncServerSection } = rsyncServerModule;
export const { initPushServerToggle } = pushServerToggleModule;
export const {
    addAuthorRow,
    getAuthorsList,
    getCitationAuthorsList,
    setAuthorsList,
    addRecLocationRow,
    getRecLocationList,
    setRecLocationList,
    getRecMethodList,
    setRecMethodList,
    getYearMonthValue,
    setYearMonthValue,
    validateAllMandatoryFields,
    validateDatasetDescriptionDraftLive,
    showStudyMetadataCard,
    resetStudyMetadataForm,
    showMethodsCard,
    generateMethodsSection,
    downloadMethods
} = metadata;

export function initializeProjectsPage() {
    initProjectsPage();
    initProjectValidation();
    initDataladSetupCheck();
}

// Share & Archive is its own page (export, DataLad server push, rsync
// backup) so these don't compete with project creation/metadata authoring
// on the same scroll. See templates/share.html.
export function initializeSharePage() {
    initializeProjectsExport();
    initDataladServerSection();
    initRsyncServerSection();
    // Runs after both destination sections so its show/hide of the merged
    // "Push to Server" card and its DataLad-vs-rsync toggle win last.
    initPushServerToggle();
}

// Settings is its own page (help, DataLad default, libraries, advanced).
// See templates/settings.html. Every action behind it is
// `prism_tools.py settings show|set` (src/settings_update.py).
export function initializeSettingsPage() {
    const noop = () => {};
    initProjectPathPickers({ fetchWithApiFallback, validateProjectField: noop, clearCreateResult: noop });
    initDataladForNewProjectsToggle();
    const projectState = createProjectsCurrentStateController({ getProjectStateSnapshot, setProjectStateSnapshot });
    createDataladCard({
        fetchWithApiFallback,
        getCurrentProjectState: projectState.getCurrentProjectState,
        applyCurrentProject: projectState.applyCurrentProject,
    }).showDataladCard();
    initBackendMonitoringToggle();
    initDedicatedTerminalToggle();
    initStudyApplicationImportToggle();
    initProjectSettingsForm();
    loadGlobalSettings();
    loadLibraryInfo();
    document.getElementById('useDefaultLibraryBtn')?.addEventListener('click', () => useDefaultLibrary());
    document.getElementById('clearGlobalLibraryBtn')?.addEventListener('click', () => clearGlobalLibrary());
}

console.log('Projects module loaded with ES6 imports');

