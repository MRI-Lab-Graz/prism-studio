/**
 * Converter Module Aggregator
 * Centralizes all converter functionality
 */

// Export all shared utilities that converter module needs
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

function initConverterModules() {
    const isConverterPage = document.getElementById('converterTabs');
    if (!isConverterPage) {
        return;
    }

    if (window.__prismConverterBootstrapLoadedViaAggregator) {
        return;
    }
    window.__prismConverterBootstrapLoadedViaAggregator = true;

    import('../../converter-bootstrap.js');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConverterModules);
} else {
    initConverterModules();
}
