/**
 * Projects Module - Validation
 * Real-time validation for project creation fields
 */

import { getById, addClass, removeClass } from '../../shared/dom.js';

const DATE_RANGE_BADGE_IDS = {
    'Period Start': 'smRecPeriodStartRequiredBadge',
    'Period End': 'smRecPeriodEndRequiredBadge'
};

const METADATA_VALIDATION_FIELDS = [
    'metadataSchemaVersion',
    'metadataName',
    'metadataLicense',
    'metadataAcknowledgements',
    'metadataDOI',
    'metadataType',
    'metadataHED',
    'metadataKeywords',
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
    'smEligExclusion',
    'smProcOverview'
];

let _validationInitialized = false;
let _validationObserver = null;
const PROJECTS_VALIDATION_DEBUG = Boolean(window.PRISM_DEBUG_PROJECTS_VALIDATION);

function debugLog(...args) {
    if (PROJECTS_VALIDATION_DEBUG) {
        console.log(...args);
    }
}

function debugWarn(...args) {
    if (PROJECTS_VALIDATION_DEBUG) {
        console.warn(...args);
    }
}

/**
 * Validate recruitment method (special case - multi-select)
 */
export function validateRecMethodBadge() {
    const select = getById('smRecMethod');
    if (!select) return;
    
    const hasSelection = Array.from(select.selectedOptions)
        .some(opt => opt.value && opt.value.trim());

    const badge = getById('smRecMethodRequiredBadge') || findBadgeByText('Method') || findBadgeByText('Recruitment Method');
    if (badge) {
        updateBadgeColor(badge, hasSelection);
    }
}

/**
 * Validate recruitment location badge (special case - dynamic list)
 */
export function validateRecLocationBadge() {
    const locationBadge = getById('smRecLocationRequiredBadge') || findBadgeByText('Location') || findBadgeByText('Recruitment Location');

    // Check if online-only is checked
    const onlineCheckbox = getById('smRecLocationOnlineOnly');
    if (onlineCheckbox && onlineCheckbox.checked) {
        if (locationBadge) {
            updateBadgeColor(locationBadge, true);
        }
        return;
    }

    // Check if there's at least one location with a country
    const locationRows = document.querySelectorAll('#smRecLocationList .rec-location-row');
    const hasAddedLocation = Array.from(locationRows)
        .some(row => String(row.dataset.location || '').trim());

    const hasLocation = hasAddedLocation;

    if (locationBadge) {
        updateBadgeColor(locationBadge, hasLocation);
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
    const badge = getById(DATE_RANGE_BADGE_IDS[badgeText] || '') || findBadgeByText(badgeText);
    if (badge) {
        updateBadgeColor(badge, hasValue);
    }

    // Update border feedback on both selects in the pair
    for (const field of [yearField, monthField]) {
        if (hasValue) {
            removeClass(field, 'required-field-empty');
            addClass(field, 'required-field-filled');
        } else {
            removeClass(field, 'required-field-filled');
            addClass(field, 'required-field-empty');
        }
    }
}

/**
 * Validate the Authors badge (special case - no single input field)
 */
export function validateAuthorsBadge() {
    // Valid only if at least one complete author exists and no incomplete rows remain
    const authorRows = document.querySelectorAll('#metadataAuthorsList .author-row');
    debugLog(`validateAuthorsBadge: Found ${authorRows.length} author rows`);
    
    let completeCount = 0;
    let incompleteCount = 0;
    
    authorRows.forEach((row, idx) => {
        const first = row.querySelector('.author-first')?.value || '';
        const last = row.querySelector('.author-last')?.value || '';
        const hasFirst = Boolean(first.trim());
        const hasLast = Boolean(last.trim());
        const isComplete = hasFirst && hasLast;
        const isIncomplete = hasFirst !== hasLast;
        debugLog(`  Row ${idx}: first="${first}", last="${last}", complete=${isComplete}, incomplete=${isIncomplete}`);
        if (isComplete) {
            completeCount += 1;
        }
        if (isIncomplete) {
            incompleteCount += 1;
        }
    });

    const hasCorresponding = Array.from(authorRows).some(
        row => row.querySelector('.author-corresponding')?.checked
    );
    const hasValidAuthors = completeCount > 0 && incompleteCount === 0 && hasCorresponding;
    debugLog(`validateAuthorsBadge: complete=${completeCount}, incomplete=${incompleteCount}, corresponding=${hasCorresponding}, valid=${hasValidAuthors}`);

    const badge = getById('metadataAuthorsRequiredBadge') || findBadgeByText('Authors');
    if (badge) {
        debugLog(`Found Authors badge: "${badge.textContent.trim()}"`);
        updateBadgeColor(badge, hasValidAuthors);
    } else {
        debugWarn('Could not find Authors badge');
    }
}

/**
 * Validate Funding badge (required explicit yes/no; details required if yes)
 */
export function validateFundingBadge() {
    const badge = getById('metadataFundingRequiredBadge') || findBadgeByText('Funding');
    if (!badge) return;

    const declaredInput = getById('metadataFundingDeclared');
    const fundingField = getById('metadataFunding');
    if (!declaredInput) {
        updateBadgeColor(badge, false);
        return;
    }

    const choice = declaredInput.value;
    if (choice === 'no') {
        updateBadgeColor(badge, true);
        return;
    }

    if (choice === 'yes') {
        const hasDetails = Boolean((fundingField?.value || '').trim());
        updateBadgeColor(badge, hasDetails);
        return;
    }

    updateBadgeColor(badge, false);
}

/**
 * Validate Ethics badge (required explicit yes/no; details required if yes)
 */
export function validateEthicsBadge() {
    const badge = getById('metadataEthicsRequiredBadge') || findBadgeByText('Ethics Approvals');
    if (!badge) return;

    const approvedInput = getById('metadataEthicsApproved');
    const committeeField = getById('metadataEthicsCommittee');
    const votumField = getById('metadataEthicsVotum');
    if (!approvedInput) {
        updateBadgeColor(badge, false);
        return;
    }

    const choice = approvedInput.value;
    if (choice === 'no') {
        updateBadgeColor(badge, true);
        return;
    }

    if (choice === 'yes') {
        const hasCommittee = Boolean((committeeField?.value || '').trim());
        const hasVotum = Boolean((votumField?.value || '').trim());
        updateBadgeColor(badge, hasCommittee && hasVotum);
        return;
    }

    updateBadgeColor(badge, false);
}

/**
 * Helper function to find badge for a field by searching nearby elements
 * @param {string} searchText - Text to search for in label
 * @returns {HTMLElement|null} - Badge element or null
 */
function findBadgeByText(searchText) {
    const labels = document.querySelectorAll('label, .form-label, [class*="badge"]');
    debugLog(`findBadgeByText("${searchText}"): Searching ${labels.length} elements`);
    
    for (const label of labels) {
        if (label.textContent && label.textContent.includes(searchText)) {
            const badge = label.querySelector('.badge');
            if (badge) {
                debugLog(`  Found badge containing "${searchText}"`);
                return badge;
            }
        }
    }
    
    debugWarn(`  No badge found for "${searchText}"`);
    return null;
}
function updateBadgeColor(badge, isFilled) {
    if (!badge) {
        debugWarn('Badge element is null');
        return;
    }
    
    const badgeText = badge.textContent.trim();
    debugLog(`updateBadgeColor: "${badgeText}" isFilled=${isFilled}`);
    
    if (isFilled) {
        removeClass(badge, 'bg-danger');
        removeClass(badge, 'bg-warning');
        removeClass(badge, 'bg-secondary');
        removeClass(badge, 'text-dark');
        addClass(badge, 'bg-success');
        debugLog(`Badge "${badgeText}" turned GREEN`);
    } else {
        removeClass(badge, 'bg-success');
        const text = badge.textContent.trim();
        if (text === 'REQUIRED') {
            addClass(badge, 'bg-danger');
            debugLog(`Badge "${badgeText}" turned RED`);
        } else if (text === 'RECOMMENDED') {
            addClass(badge, 'bg-warning');
            addClass(badge, 'text-dark');
            debugLog(`Badge "${badgeText}" turned YELLOW`);
        } else if (text === 'OPTIONAL') {
            addClass(badge, 'bg-secondary');
            debugLog(`Badge "${badgeText}" turned GRAY`);
        }
    }
}

function refreshValidationState() {
    METADATA_VALIDATION_FIELDS.forEach(fieldId => {
        const field = getById(fieldId);
        if (!field) return;
        validateProjectField(fieldId);
    });

    validateAuthorsBadge();
    validateRecMethodBadge();
    validateRecLocationBadge();
    validateDateRangeBadge('smRecPeriodStartYear', 'smRecPeriodStartMonth', 'Period Start');
    validateDateRangeBadge('smRecPeriodEndYear', 'smRecPeriodEndMonth', 'Period End');
    validateEthicsBadge();
    validateFundingBadge();
}

/**
 * Validate a project field and update UI
 * @param {string} fieldId - ID of the field to validate
 */
export function validateProjectField(fieldId) {
    const field = getById(fieldId);
    if (!field) {
        debugWarn(`Field not found: ${fieldId}`);
        return;
    }
    
    const pairFieldValidity = (yearId, monthId) => {
        const yearValue = getById(yearId)?.value?.trim() || '';
        const monthValue = getById(monthId)?.value?.trim() || '';
        return yearValue !== '' && monthValue !== '';
    };

    let isValid;
    if (fieldId === 'smRecPeriodStartYear' || fieldId === 'smRecPeriodStartMonth') {
        isValid = pairFieldValidity('smRecPeriodStartYear', 'smRecPeriodStartMonth');
    } else if (fieldId === 'smRecPeriodEndYear' || fieldId === 'smRecPeriodEndMonth') {
        isValid = pairFieldValidity('smRecPeriodEndYear', 'smRecPeriodEndMonth');
    } else {
        isValid = field.value.trim() !== '';
    }
    debugLog(`validateProjectField("${fieldId}"): isValid=${isValid}`);
    
    let isPatternValid = true;

    // For projectName, also validate pattern
    if (fieldId === 'projectName' && isValid) {
        isPatternValid = /^[a-zA-Z0-9_-]+$/.test(field.value.trim());
        if (!isPatternValid) {
            debugWarn(`Pattern validation failed for ${fieldId}`);
            removeClass(field, 'required-field-filled');
            addClass(field, 'required-field-empty');
        }
    }

    // For metadataKeywords, require at least 2 commas (=> at least 3 comma-separated entries)
    if (fieldId === 'metadataKeywords' && isValid) {
        const commaCount = (field.value.match(/,/g) || []).length;
        isPatternValid = commaCount >= 2;
        if (!isPatternValid) {
            debugWarn(`Pattern validation failed for ${fieldId}: needs at least 2 commas`);
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
        return;
    }
    
    const badge = label.querySelector('.badge');
    if (!badge) {
        return;
    }
    
    debugLog(`Found badge for ${fieldId}, updating color...`);
    updateBadgeColor(badge, isValid && isPatternValid);
}

/**
 * Initialize validation listeners
 * Called automatically when DOM is ready
 */
export function initProjectValidation() {
    if (_validationInitialized) {
        refreshValidationState();
        return;
    }
    _validationInitialized = true;

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
    METADATA_VALIDATION_FIELDS.forEach(fieldId => {
        const field = getById(fieldId);
        if (field) {
            attachValidationListeners(fieldId);
        }
    });

    // Set up a MutationObserver to attach validation to fields that appear later
    _validationObserver = new MutationObserver(() => {
        METADATA_VALIDATION_FIELDS.forEach(fieldId => {
            const field = getById(fieldId);
            if (field && !field.hasAttribute('data-validation-attached')) {
                attachValidationListeners(fieldId);
            }
        });
    });
    
    if (document.body) {
        _validationObserver.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: false
        });
    }

    // Add listener for recruitment location checkbox
    const onlineCheckbox = getById('smRecLocationOnlineOnly');
    if (onlineCheckbox) {
        onlineCheckbox.addEventListener('change', () => {
            validateRecLocationBadge();
        });
    }

    refreshValidationState();
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
    debugLog('Resetting all badges to original state');
    
    const scopedBadges = [];
    ['createProjectForm', 'studyMetadataForm'].forEach(formId => {
        const form = getById(formId);
        if (!form) return;
        form.querySelectorAll('label .badge').forEach(badge => scopedBadges.push(badge));
    });
    const badges = scopedBadges.length > 0 ? scopedBadges : Array.from(document.querySelectorAll('label .badge'));

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
    
    debugLog(`Reset ${badges.length} badges to original state`);
}

// Expose validation functions for use in other modules
window.validateProjectField = validateProjectField;
window.validateAuthorsBadge = validateAuthorsBadge;
window.validateRecMethodBadge = validateRecMethodBadge;
window.validateRecLocationBadge = validateRecLocationBadge;
window.validateDateRangeBadge = validateDateRangeBadge;
window.validateEthicsBadge = validateEthicsBadge;
window.validateFundingBadge = validateFundingBadge;
window.resetAllBadges = resetAllBadges;
