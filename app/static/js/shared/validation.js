/**
 * Shared validation utilities
 * Used across forms and data validation
 */

/**
 * Validate project/folder name (alphanumerics, hyphens, underscores only)
 * @param {string} name - The name to validate
 * @returns {boolean} True if valid
 */
export function isValidProjectName(name) {
    if (!name) return false;
    return /^[a-zA-Z0-9_-]+$/.test(name);
}

/**
 * Validate email address
 * @param {string} email - The email to validate
 * @returns {boolean} True if valid
 */
export function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Validate URL
 * @param {string} url - The URL to validate
 * @returns {boolean} True if valid
 */
export function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

/**
 * Validate file path
 * @param {string} path - The file path to validate
 * @returns {boolean} True if path is not empty
 */
export function isValidPath(path) {
    return path && path.trim().length > 0;
}

/**
 * Check if a form control is required but empty
 * @param {HTMLElement} element - The form element
 * @returns {boolean} True if required and empty
 */
export function isRequiredFieldEmpty(element) {
    if (!element || !element.hasAttribute('required')) {
        return false;
    }
    
    const value = element.value ? element.value.trim() : '';
    return value.length === 0;
}

/**
 * Validate all required fields in a form
 * @param {HTMLFormElement} formElement - The form to validate
 * @returns {boolean} True if all required fields are filled
 */
export function validateRequiredFields(formElement) {
    if (!formElement) return false;
    
    const requiredFields = formElement.querySelectorAll('[required]');
    let allValid = true;
    
    requiredFields.forEach(field => {
        if (isRequiredFieldEmpty(field)) {
            allValid = false;
            field.classList.add('is-invalid');
        } else {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
        }
    });
    
    return allValid;
}

/**
 * Clear validation styles from form
 * @param {HTMLFormElement} formElement - The form to clear
 */
export function clearFormValidation(formElement) {
    if (!formElement) return;
    
    const fields = formElement.querySelectorAll('.is-invalid, .is-valid');
    fields.forEach(field => {
        field.classList.remove('is-invalid', 'is-valid');
    });
}

/**
 * Show validation error message
 * @param {HTMLElement} container - Container for error message
 * @param {string} message - Error message text
 */
export function showValidationError(container, message) {
    if (!container) return;
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger alert-dismissible fade show';
    errorDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    container.innerHTML = '';
    container.appendChild(errorDiv);
}

/**
 * Clear validation error messages
 * @param {HTMLElement} container - Container with error messages
 */
export function clearValidationErrors(container) {
    if (container) {
        container.innerHTML = '';
    }
}
