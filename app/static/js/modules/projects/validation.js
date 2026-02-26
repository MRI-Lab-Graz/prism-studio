/**
 * Projects Module - Validation
 * Real-time validation for project creation fields
 */

import { getById, querySelect, addClass, removeClass } from '../../shared/dom.js';

/**
 * Validate a project field and update UI
 * @param {string} fieldId - ID of the field to validate
 */
export function validateProjectField(fieldId) {
    const field = getById(fieldId);
    if (!field) return;
    
    const isValid = field.value.trim() !== '';
    
    let isPatternValid = true;

    // For projectName, also validate pattern
    if (fieldId === 'projectName' && isValid) {
        isPatternValid = /^[a-zA-Z0-9_-]+$/.test(field.value.trim());
        if (!isPatternValid) {
            removeClass(field, 'required-field-filled');
            addClass(field, 'required-field-empty');
        }
    }
    
    if (isValid && isPatternValid) {
        removeClass(field, 'required-field-empty');
        addClass(field, 'required-field-filled');
    } else {
        removeClass(field, 'required-field-filled');
        addClass(field, 'required-field-empty');
    }

    const label = querySelect(`label[for="${fieldId}"]`);
    const badge = label ? label.querySelector('.badge') : null;
    if (badge) {
        if (isValid && isPatternValid) {
            removeClass(badge, 'bg-danger');
            addClass(badge, 'bg-success');
        } else {
            removeClass(badge, 'bg-success');
            addClass(badge, 'bg-danger');
        }
    }
}

/**
 * Initialize validation listeners
 * Called automatically when DOM is ready
 */
export function initProjectValidation() {
    // Add event listeners for real-time validation
    const projectNameField = getById('projectName');
    const projectPathField = getById('projectPath');
    
    if (projectNameField) {
        projectNameField.addEventListener('input', function() {
            validateProjectField('projectName');
        });
        projectNameField.addEventListener('blur', function() {
            validateProjectField('projectName');
        });
        validateProjectField('projectName');
    }
    
    if (projectPathField) {
        projectPathField.addEventListener('input', function() {
            validateProjectField('projectPath');
        });
        projectPathField.addEventListener('blur', function() {
            validateProjectField('projectPath');
        });
        validateProjectField('projectPath');
    }
    
    // Update validation after browse button click
    const browseProjectPathBtn = getById('browseProjectPath');
    if (browseProjectPathBtn) {
        browseProjectPathBtn.addEventListener('click', function() {
            setTimeout(() => {
                validateProjectField('projectPath');
            }, 100);
        });
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initProjectValidation);
