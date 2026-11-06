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
import { initDataladSetupCheck } from './datalad_setup_check.js';
import { initSessionMapCard } from './session-map-card.js';
import {
    clearGlobalLibrary,
    initBackendMonitoringToggle,
    initDataladForNewProjectsToggle,
    initWcagEnhancedViewToggle,
    initGitIdentityForm,
    initDedicatedTerminalToggle,
    initProjectSettingsForm,
    initStudyApplicationImportToggle,
    loadGlobalSettings,
    loadLibraryInfo,
    useDefaultLibrary,
} from './settings.js';
import { initProjectPathPickers } from './path-pickers.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import * as rsyncServerModule from './rsync_server.js';
import * as metadata from './metadata.js?v=20260515-4';

// Re-export project modules for direct access
export { helpers, validation, core, exportModule, rsyncServerModule, metadata };

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
export const { showRsyncServerCard, initRsyncServerSection } = rsyncServerModule;
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
    initSessionMapCard({ fetchWithApiFallback });
}

// Share & Archive is its own page (export, rsync backup) so these don't compete with project creation/metadata
// authoring on the same scroll. See templates/share.html. DataLad has its own page (templates/datalad.html).
export function initializeSharePage() {
    initializeProjectsExport();
    initRsyncServerSection();
}

// Settings is its own page (help, DataLad default, libraries, advanced).
// See templates/settings.html. Every action behind it is
// `prism_tools.py settings show|set` (src/settings_update.py).
export function initializeSettingsPage() {
    const noop = () => {};
    initProjectPathPickers({ fetchWithApiFallback, validateProjectField: noop, clearCreateResult: noop });
    initDataladForNewProjectsToggle();
    initWcagEnhancedViewToggle();
    initGitIdentityForm();
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

