/**
 * Survey Module Aggregator
 * Centralizes all survey functionality
 */

// Export all shared utilities that survey module needs
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

// Import and re-export survey-specific modules
// (Will be populated as survey-*.js files are converted to modules)
// export * from './customizer.js';
// export * from './generator.js';

console.log('Survey module loaded');
