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

import { initLimeSurveyQuickImport } from './survey.js';

function initConverterModules() {
    const isConverterPage = document.getElementById('converterTabs');
    if (!isConverterPage) {
        return;
    }

    initLimeSurveyQuickImport();

    import('../../converter-bootstrap.js');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConverterModules);
} else {
    initConverterModules();
}
