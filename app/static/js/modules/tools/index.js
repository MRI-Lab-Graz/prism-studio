/**
 * Tools Module Aggregator
 * Centralizes all tool functionality
 */

// Export all shared utilities that tools module needs
export { apiGet, apiPost, apiPut, apiDelete, apiUpload } from '../../shared/api.js';
export { 
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
    show, 
    hide, 
    addClass, 
    removeClass, 
    setText, 
    getText,
    setHtml,
    scrollIntoView,
    focus
} from '../../shared/dom.js';
export { getLocalStorage, setLocalStorage, removeLocalStorage } from '../../shared/storage.js';

// Import and re-export tool-specific modules
// (Will be populated as individual tool files are converted to modules)
// export * from './file-mgmt.js';
// export * from './recipes.js';
// export * from './results.js';
// export * from './template-editor.js';
// export * from './json-editor.js';

console.log('Tools module loaded');
