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
import * as metadata from './metadata.js';

// Re-export project modules for direct access
export { helpers, validation, core, exportModule, metadata };

// Export individual functions for backward compatibility
export const { setButtonLoading, showAlert, showToast, showTopFeedback, textToArray } = helpers;
export const { validateProjectField, initProjectValidation } = validation;
export const { 
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
export const { showExportCard, initExportForm, initAndExport } = exportModule;
export const {
    addAuthorRow,
    getAuthorsList,
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

console.log('Projects module loaded with ES6 imports');

