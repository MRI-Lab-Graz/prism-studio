/**
 * Projects Module - Validation
 * Real-time validation for project creation fields
 */

import { getById, addClass, removeClass } from '../../shared/dom.js';

/**
 * Validate recruitment method (special case - multi-select)
 */
export function validateRecMethodBadge() {
    const select = getById('smRecMethod');
    if (!select) return;
    
    const hasSelection = Array.from(select.selectedOptions)
        .some(opt => opt.value && opt.value.trim());

    const badge = findBadgeByText('Recruitment Method');
    if (badge) {
        updateBadgeColor(badge, hasSelection);
    }
}

/**
 * Validate recruitment location badge (special case - dynamic list)
 */
export function validateRecLocationBadge() {
    // Check if online-only is checked
    const onlineCheckbox = getById('smRecLocationOnlineOnly');
    if (onlineCheckbox && onlineCheckbox.checked) {
        const badge = findBadgeByText('Recruitment Location');
        if (badge) {
            updateBadgeColor(badge, true);
        }
        return;
    }

    // Check if there's at least one location with a country
    const locationRows = document.querySelectorAll('#smRecLocationList .rec-location-row');
    let hasLocation = false;
    
    locationRows.forEach(row => {
        const country = row.querySelector('.rec-location-country')?.value || '';
        if (country.trim()) {
            hasLocation = true;
        }
    });

    const badge = findBadgeByText('Recruitment Location');
    if (badge) {
        updateBadgeColor(badge, hasLocation);
    }
}

/**
 * Validate date range fields (special case - two selects make one field)
 */
export function validateDateRangeBadge(yearId, monthId, badgeText) {
    const yearField = getById(yearId);
    const monthField = getById(monthId);
    
    if (!yearField || !monthField) return;
    
    const hasValue = yearField.value && monthField.value;
    const badge = findBadgeByText(badgeText);
    if (badge) {
        updateBadgeColor(badge, hasValue);
    }
}

/**
 * Validate the Authors badge (special case - no single input field)
 */
export function validateAuthorsBadge() {
    // Check if there's at least one author with a value
    const authorRows = document.querySelectorAll('#metadataAuthorsList .author-row');
    console.log(`validateAuthorsBadge: Found ${authorRows.length} author rows`);
    
    let hasAuthor = false;
    
    authorRows.forEach((row, idx) => {
        const first = row.querySelector('.author-first')?.value || '';
        const last = row.querySelector('.author-last')?.value || '';
        const hasValue = first.trim() || last.trim();
        console.log(`  Row ${idx}: first="${first}", last="${last}", hasValue=${hasValue}`);
        if (hasValue) {
            hasAuthor = true;
        }
    });

    console.log(`validateAuthorsBadge: hasAuthor=${hasAuthor}`);

    const badge = findBadgeByText('Authors');
    if (badge) {
        console.log(`Found Authors badge: "${badge.textContent.trim()}"`);
        updateBadgeColor(badge, hasAuthor);
    } else {
        console.warn('Could not find Authors badge');
    }
}

/**
 * Helper function to find badge for a field by searching nearby elements
 * @param {string} searchText - Text to search for in label
 * @returns {HTMLElement|null} - Badge element or null
 */
function findBadgeByText(searchText) {
    const labels = document.querySelectorAll('label, .form-label, [class*="badge"]');
    console.log(`findBadgeByText("${searchText}"): Searching ${labels.length} elements`);
    
    for (const label of labels) {
        if (label.textContent && label.textContent.includes(searchText)) {
            const badge = label.querySelector('.badge');
            if (badge) {
                console.log(`  Found badge containing "${searchText}"`);
                return badge;
            }
        }
    }
    
    console.warn(`  No badge found for "${searchText}"`);
    return null;
}
function updateBadgeColor(badge, isFilled) {
    if (!badge) {
        console.warn('Badge element is null');
        return;
    }
    
    const badgeText = badge.textContent.trim();
    console.log(`updateBadgeColor: "${badgeText}" isFilled=${isFilled}`);
    
    if (isFilled) {
        removeClass(badge, 'bg-danger');
        removeClass(badge, 'bg-warning');
        removeClass(badge, 'bg-secondary');
        removeClass(badge, 'text-dark');
        addClass(badge, 'bg-success');
        console.log(`✓ Badge "${badgeText}" turned GREEN`);
    } else {
        removeClass(badge, 'bg-success');
        const text = badge.textContent.trim();
        if (text === 'REQUIRED') {
            addClass(badge, 'bg-danger');
            console.log(`✗ Badge "${badgeText}" turned RED`);
        } else if (text === 'RECOMMENDED') {
            addClass(badge, 'bg-warning');
            addClass(badge, 'text-dark');
            console.log(`✗ Badge "${badgeText}" turned YELLOW`);
        } else if (text === 'OPTIONAL') {
            addClass(badge, 'bg-secondary');
            console.log(`✗ Badge "${badgeText}" turned GRAY`);
        }
    }
}

/**
 * Validate a project field and update UI
 * @param {string} fieldId - ID of the field to validate
 */
export function validateProjectField(fieldId) {
    const field = getById(fieldId);
    if (!field) {
        console.warn(`Field not found: ${fieldId}`);
        return;
    }
    
    const isValid = field.value.trim() !== '';
    console.log(`validateProjectField("${fieldId}"): isValid=${isValid}, value="${field.value.substring(0, 20)}"`);
    
    let isPatternValid = true;

    // For projectName, also validate pattern
    if (fieldId === 'projectName' && isValid) {
        isPatternValid = /^[a-zA-Z0-9_-]+$/.test(field.value.trim());
        if (!isPatternValid) {
            console.warn(`Pattern validation failed for ${fieldId}`);
            removeClass(field, 'required-field-filled');
            addClass(field, 'required-field-empty');
        }
    }

    // For metadataKeywords, require at least 2 commas (=> at least 3 comma-separated entries)
    if (fieldId === 'metadataKeywords' && isValid) {
        const commaCount = (field.value.match(/,/g) || []).length;
        isPatternValid = commaCount >= 2;
        if (!isPatternValid) {
            console.warn(`Pattern validation failed for ${fieldId}: needs at least 2 commas`);
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

    // Find the label - could be a sibling, parent, or ancestor
    let label = document.querySelector(`label[for="${fieldId}"]`);
    
    // If not found with for attribute, search for label among siblings or nearby elements
    if (!label && field.parentElement) {
        // Check siblings and parent
        label = field.parentElement.querySelector('label');
        if (!label) {
            // Check grandparent (in case field is in a wrapper)
            const container = field.parentElement.parentElement;
            if (container) {
                label = container.querySelector('label');
            }
        }
    }
    
    if (!label) {
        console.warn(`Label not found for field: ${fieldId}`);
        return;
    }
    
    const badge = label.querySelector('.badge');
    if (!badge) {
        console.warn(`Badge not found in label for field: ${fieldId}`);
        return;
    }
    
    console.log(`Found badge for ${fieldId}, updating color...`);
    updateBadgeColor(badge, isValid && isPatternValid);
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
        projectPathField.addEventListener('change', function() {
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

    // Add validation for all metadata fields with badges
    const metadataFields = [
        'metadataName',
        'metadataLicense',
        'metadataAcknowledgements',
        'metadataDOI',
        'metadataType',
        'metadataHED',
        'metadataKeywords',
        'metadataFunding',
        'metadataHowToAcknowledge',
        'metadataReferences',
        'smOverviewMain',
        'smOverviewIV',
        'smOverviewDV',
        'smOverviewCV',
        'smOverviewQA',
        'smSDType',
        'smSDConditionType',
        'smSDTypeDesc',
        'smSDBlinding',
        'smSDRandomization',
        'smSDControl',
        'smRecMethod',
        'smRecPeriodStartYear',
        'smRecPeriodStartMonth',
        'smRecPeriodEndYear',
        'smRecPeriodEndMonth',
        'smRecCompensation',
        'smEligInclusion',
        'smEligExclusion'
    ];

    metadataFields.forEach(fieldId => {
        const field = getById(fieldId);
        if (field) {
            attachValidationListeners(fieldId);
        }
    });

    // Set up a MutationObserver to attach validation to fields that appear later
    const observer = new MutationObserver((mutations) => {
        metadataFields.forEach(fieldId => {
            const field = getById(fieldId);
            if (field && !field.hasAttribute('data-validation-attached')) {
                attachValidationListeners(fieldId);
                field.setAttribute('data-validation-attached', 'true');
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: false
    });

    // Check every 500ms for new fields (fallback for complex renders)
    setInterval(() => {
        metadataFields.forEach(fieldId => {
            const field = getById(fieldId);
            if (field && !field.hasAttribute('data-validation-attached')) {
                attachValidationListeners(fieldId);
                field.setAttribute('data-validation-attached', 'true');
            }
        });
    }, 500);

    // Add listener for recruitment location checkbox
    const onlineCheckbox = getById('smRecLocationOnlineOnly');
    if (onlineCheckbox) {
        onlineCheckbox.addEventListener('change', () => {
            validateRecLocationBadge();
        });
    }
}

/**
 * Helper function to attach validation listeners to a field
 * @param {string} fieldId - ID of the field to attach listeners to
 */
function attachValidationListeners(fieldId) {
    const field = getById(fieldId);
    if (!field) return;
    
    // Prevent duplicate attachment
    if (field.hasAttribute('data-validation-attached')) return;
    field.setAttribute('data-validation-attached', 'true');
    
    field.addEventListener('input', function() {
        validateProjectField(fieldId);
        // Special handling for date fields
        if (fieldId === 'smRecPeriodStartYear' || fieldId === 'smRecPeriodStartMonth') {
            validateDateRangeBadge('smRecPeriodStartYear', 'smRecPeriodStartMonth', 'Period Start');
        }
        if (fieldId === 'smRecPeriodEndYear' || fieldId === 'smRecPeriodEndMonth') {
            validateDateRangeBadge('smRecPeriodEndYear', 'smRecPeriodEndMonth', 'Period End');
        }
    });
    field.addEventListener('blur', function() {
        validateProjectField(fieldId);
    });
    // Also trigger on change for select elements
    if (field.tagName === 'SELECT') {
        field.addEventListener('change', function() {
            validateProjectField(fieldId);
            // Special handling for recruitment method multi-select
            if (fieldId === 'smRecMethod') {
                validateRecMethodBadge();
            }
            // Special handling for date fields
            if (fieldId === 'smRecPeriodStartYear' || fieldId === 'smRecPeriodStartMonth') {
                validateDateRangeBadge('smRecPeriodStartYear', 'smRecPeriodStartMonth', 'Period Start');
            }
            if (fieldId === 'smRecPeriodEndYear' || fieldId === 'smRecPeriodEndMonth') {
                validateDateRangeBadge('smRecPeriodEndYear', 'smRecPeriodEndMonth', 'Period End');
            }
        });
    }
    // Initial validation
    setTimeout(() => {
        validateProjectField(fieldId);
        if (fieldId === 'smRecMethod') {
            validateRecMethodBadge();
        }
        if (fieldId === 'smRecPeriodStartYear' || fieldId === 'smRecPeriodStartMonth') {
            validateDateRangeBadge('smRecPeriodStartYear', 'smRecPeriodStartMonth', 'Period Start');
        }
        if (fieldId === 'smRecPeriodEndYear' || fieldId === 'smRecPeriodEndMonth') {
            validateDateRangeBadge('smRecPeriodEndYear', 'smRecPeriodEndMonth', 'Period End');
        }
    }, 100);
}

/**
 * Reset all badges to their original state (REQUIRED=red, RECOMMENDED=yellow, OPTIONAL=gray)
 */
export function resetAllBadges() {
    console.log('Resetting all badges to original state');
    
    const badges = document.querySelectorAll('.badge');
    badges.forEach(badge => {
        const badgeText = badge.textContent.trim();
        
        // Remove all color classes
        removeClass(badge, 'bg-danger');
        removeClass(badge, 'bg-warning');
        removeClass(badge, 'bg-secondary');
        removeClass(badge, 'bg-success');
        removeClass(badge, 'text-dark');
        
        // Re-apply original color based on badge type
        if (badgeText === 'REQUIRED') {
            addClass(badge, 'bg-danger');
        } else if (badgeText === 'RECOMMENDED') {
            addClass(badge, 'bg-warning');
            addClass(badge, 'text-dark');
        } else if (badgeText === 'OPTIONAL') {
            addClass(badge, 'bg-secondary');
        }
    });
    
    console.log(`Reset ${badges.length} badges to original state`);
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initProjectValidation, 100);
    });
} else {
    // DOM already loaded
    setTimeout(initProjectValidation, 100);
}

// Expose validation functions for use in other modules
window.validateProjectField = validateProjectField;
window.validateAuthorsBadge = validateAuthorsBadge;
window.validateRecMethodBadge = validateRecMethodBadge;
window.validateRecLocationBadge = validateRecLocationBadge;
window.validateDateRangeBadge = validateDateRangeBadge;
window.resetAllBadges = resetAllBadges;
