/**
 * Converter Module Aggregator
 * Centralizes all converter functionality
 */

// Export all shared utilities that converter module needs
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
    setHtml
} from '../../shared/dom.js';
export { getLocalStorage, setLocalStorage, removeLocalStorage } from '../../shared/storage.js';

// Import and re-export converter-specific modules
// (Will be populated as converter.js is split into modality-specific modules)
// export * from './core.js';
// export * from './biometrics.js';
// export * from './eyetracking.js';
// export * from './participants.js';
// export * from './physio.js';
// export * from './survey.js';

console.log('Converter module loaded');
