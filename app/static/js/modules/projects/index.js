/**
 * Projects Module Aggregator
 * Centralizes all project management functionality
 * 
 * Exports:
 * - Shared utilities (api, validation, dom, storage)
 * - Project-specific modules (helpers, validation, core, export, metadata)
 */

// Export all shared utilities
export { apiGet, apiPost, apiPut, apiDelete, apiUpload } from '../../shared/api.js';
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
export { getLocalStorage, setLocalStorage, removeLocalStorage } from '../../shared/storage.js';

// Import project-specific modules
import * as helpers from './helpers.js';
import * as validation from './validation.js';
import * as core from './core.js';
import * as exportModule from './export.js';
import * as dataladServerModule from './datalad_server.js';
import * as rsyncServerModule from './rsync_server.js';
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
    loadGlobalSettings, 
    loadLibraryInfo, 
    selectProjectType,
    useDefaultLibrary,
    clearGlobalLibrary 
} = core;
export const { showExportCard, initExportForm, initAndExport, initOpenMindsExport, loadExportPreferences, initializeProjectsExport } = exportModule;
export const { showDataladServerCard, initDataladServerSection } = dataladServerModule;
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
    initializeProjectsExport();
    initDataladServerSection();
    initRsyncServerSection();
}

console.log('Projects module loaded with ES6 imports');

