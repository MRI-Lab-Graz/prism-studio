/**
 * Projects Module - Metadata
 * Study metadata, dataset description, completeness, and methods generation
 */

import { setButtonLoading, showToast, showTopFeedback, textToArray as _textToArray } from './helpers.js';
import { validateAuthorsBadge, validateRecLocationBadge, validateProjectField, validateRecMethodBadge, validateDateRangeBadge, validateFundingBadge, validateEthicsBadge } from './validation.js';

// ===== AUTHORS =====

function _formatAuthor(firstName, lastName) {
    const first = (firstName || '').trim();
    const last = (lastName || '').trim();
    if (first && last) return `${last}, ${first}`;
    return last || first || '';
}

function _escapeHtmlAttr(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function _isValidWebsiteFormat(value) {
    if (!value) return true;
    try {
        const url = new URL(String(value).trim());
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
        return false;
    }
}

function _isValidEmailFormat(value) {
    if (!value) return true;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value).trim());
}

function _isValidOrcidFormat(value) {
    if (!value) return true;
    return /^https:\/\/orcid\.org\/\d{4}-\d{4}-\d{4}-\d{4}$/i.test(String(value).trim());
}

function _normalizeDoi(value) {
    let doi = String(value || '').trim();
    if (!doi) return '';
    doi = doi.replace(/^https?:\/\/doi\.org\//i, '');
    doi = doi.replace(/^doi:\s*/i, '');
    return doi.trim();
}

function _isValidDoiFormat(value) {
    if (!value) return true;
    const doi = _normalizeDoi(value);
    return /^10\.\d{4,9}\/.+/i.test(doi);
}

function _validateAuthorOptionalFields(row) {
    const websiteInput = row.querySelector('.author-website');
    const orcidInput = row.querySelector('.author-orcid');
    const emailInput = row.querySelector('.author-email');

    if (websiteInput) {
        const isValid = _isValidWebsiteFormat(websiteInput.value);
        websiteInput.classList.toggle('is-invalid', !isValid);
    }

    if (orcidInput) {
        const isValid = _isValidOrcidFormat(orcidInput.value);
        orcidInput.classList.toggle('is-invalid', !isValid);
    }

    if (emailInput) {
        const isValid = _isValidEmailFormat(emailInput.value);
        emailInput.classList.toggle('is-invalid', !isValid);
    }
}

let _draggedAuthorRow = null;

function _clearAuthorDragHighlights() {
    document.querySelectorAll('#metadataAuthorsList .author-row').forEach(row => {
        row.classList.remove('border-primary');
    });
}

function _refreshAuthorMoveButtons() {
    const rows = Array.from(document.querySelectorAll('#metadataAuthorsList .author-row'));
    rows.forEach((row, index) => {
        const upBtn = row.querySelector('.move-author-up');
        const downBtn = row.querySelector('.move-author-down');
        if (upBtn) upBtn.disabled = index === 0;
        if (downBtn) downBtn.disabled = index === rows.length - 1;
    });
}

function _moveAuthorRow(row, direction) {
    const list = document.getElementById('metadataAuthorsList');
    if (!list || !row) return;

    if (direction === 'up') {
        const prev = row.previousElementSibling;
        if (prev) {
            list.insertBefore(row, prev);
        }
    } else if (direction === 'down') {
        const next = row.nextElementSibling;
        if (next) {
            list.insertBefore(next, row);
        }
    }

    _updateAuthorRowLabels();
    _refreshAuthorMoveButtons();
    updateCreateProjectButton();
    validateAuthorsBadge();
}

function _wireAuthorRowDrag(row) {
    const handle = row.querySelector('.author-drag-handle');
    if (!handle) return;

    handle.setAttribute('draggable', 'true');

    handle.addEventListener('dragstart', (event) => {
        _draggedAuthorRow = row;
        row.classList.add('opacity-75');
        if (event.dataTransfer) {
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', 'author-row');
        }
    });

    handle.addEventListener('dragend', () => {
        row.classList.remove('opacity-75');
        _draggedAuthorRow = null;
        _clearAuthorDragHighlights();
    });

    row.addEventListener('dragover', (event) => {
        if (!_draggedAuthorRow || _draggedAuthorRow === row) return;
        event.preventDefault();
        row.classList.add('border-primary');
    });

    row.addEventListener('dragleave', () => {
        row.classList.remove('border-primary');
    });

    row.addEventListener('drop', (event) => {
        if (!_draggedAuthorRow || _draggedAuthorRow === row) return;
        event.preventDefault();

        const list = document.getElementById('metadataAuthorsList');
        if (!list) return;

        const rect = row.getBoundingClientRect();
        const shouldInsertBefore = event.clientY < rect.top + rect.height / 2;

        if (shouldInsertBefore) {
            list.insertBefore(_draggedAuthorRow, row);
        } else {
            list.insertBefore(_draggedAuthorRow, row.nextSibling);
        }

        _clearAuthorDragHighlights();
        _updateAuthorRowLabels();
        _refreshAuthorMoveButtons();
        updateCreateProjectButton();
        validateAuthorsBadge();
    });
}

function _updateAuthorRowLabels() {
    const rows = document.querySelectorAll('#metadataAuthorsList .author-row');
    rows.forEach((row, index) => {
        const num = index + 1;
        const label = row.querySelector('.author-index-label');
        if (label) {
            label.textContent = `Author ${num}`;
        }

        const first = row.querySelector('.author-first');
        const last = row.querySelector('.author-last');
        const website = row.querySelector('.author-website');
        const orcid = row.querySelector('.author-orcid');
        const affiliation = row.querySelector('.author-affiliation');
        const email = row.querySelector('.author-email');

        if (first) first.placeholder = `Author ${num} First`;
        if (last) last.placeholder = `Author ${num} Last`;
        if (website) website.placeholder = `Author ${num} Website (optional)`;
        if (orcid) orcid.placeholder = `Author ${num} ORCID (optional)`;
        if (affiliation) affiliation.placeholder = `Author ${num} Affiliation (optional)`;
        if (email) email.placeholder = `Author ${num} Email (optional)`;
    });
    _refreshAuthorMoveButtons();
}

function _getAuthorOptionalFormatErrors() {
    const errors = [];
    const rows = document.querySelectorAll('#metadataAuthorsList .author-row');

    rows.forEach((row, index) => {
        const label = `Author ${index + 1}`;
        const website = (row.querySelector('.author-website')?.value || '').trim();
        const orcid = (row.querySelector('.author-orcid')?.value || '').trim();
        const email = (row.querySelector('.author-email')?.value || '').trim();

        if (website && !_isValidWebsiteFormat(website)) {
            errors.push(`${label}: Website must start with http:// or https://`);
        }
        if (orcid && !_isValidOrcidFormat(orcid)) {
            errors.push(`${label}: ORCID must match https://orcid.org/0000-0000-0000-0000`);
        }
        if (email && !_isValidEmailFormat(email)) {
            errors.push(`${label}: Email must be a valid address`);
        }
    });

    return errors;
}

function _parseAuthor(author) {
    if (!author) return { first: '', last: '' };
    if (typeof author === 'object') {
        return {
            first: String(author['given-names'] || author.given || author.first || '').trim(),
            last: String(author['family-names'] || author.family || author.last || '').trim(),
            website: String(author.website || '').trim(),
            orcid: String(author.orcid || '').trim(),
            affiliation: String(author.affiliation || '').trim(),
            email: String(author.email || '').trim(),
        };
    }
    const authorText = String(author);
    if (authorText.includes(',')) {
        const parts = authorText.split(',');
        return {
            last: parts[0].trim(),
            first: (parts[1] || '').trim(),
            website: '',
            orcid: '',
            affiliation: '',
            email: '',
        };
    }
    const tokens = authorText.trim().split(/\s+/).filter(Boolean);
    if (tokens.length <= 1) {
        return {
            first: tokens[0] || '',
            last: '',
            website: '',
            orcid: '',
            affiliation: '',
            email: '',
        };
    }
    return {
        first: tokens[0],
        last: tokens.slice(1).join(' '),
        website: '',
        orcid: '',
        affiliation: '',
        email: '',
    };
}

export function addAuthorRow(firstName = '', lastName = '', extras = {}) {
    const list = document.getElementById('metadataAuthorsList');
    if (!list) return;

    const website = _escapeHtmlAttr(extras.website || '');
    const orcid = _escapeHtmlAttr(extras.orcid || '');
    const affiliation = _escapeHtmlAttr(extras.affiliation || '');
    const email = _escapeHtmlAttr(extras.email || '');
    const escapedFirst = _escapeHtmlAttr(firstName);
    const escapedLast = _escapeHtmlAttr(lastName);

    const row = document.createElement('div');
    row.className = 'author-row border rounded p-2 bg-white';
    row.innerHTML = `
        <div class="small text-muted fw-semibold mb-2 author-index-label">Author</div>
        <div class="d-flex gap-2 align-items-center mb-2">
            <button type="button" class="btn btn-outline-secondary btn-sm author-drag-handle" title="Drag to reorder authors" aria-label="Drag to reorder authors">
                <i class="fas fa-grip-vertical"></i>
            </button>
            <input type="text" class="form-control form-control-sm author-first" placeholder="First" value="${escapedFirst}" title="Enter the author's first name." required>
            <input type="text" class="form-control form-control-sm author-last" placeholder="Last" value="${escapedLast}" title="Enter the author's last name." required>
            <button type="button" class="btn btn-outline-secondary btn-sm move-author-up" title="Move author up" aria-label="Move author up">
                <i class="fas fa-arrow-up"></i>
            </button>
            <button type="button" class="btn btn-outline-secondary btn-sm move-author-down" title="Move author down" aria-label="Move author down">
                <i class="fas fa-arrow-down"></i>
            </button>
            <button type="button" class="btn btn-outline-danger btn-sm remove-author">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="row g-2">
            <div class="col-md-6">
                <input type="text" class="form-control form-control-sm author-website" placeholder="Website (optional)" value="${website}">
            </div>
            <div class="col-md-6">
                <input type="text" class="form-control form-control-sm author-orcid" placeholder="ORCID (optional)" value="${orcid}">
            </div>
            <div class="col-md-8">
                <input type="text" class="form-control form-control-sm author-affiliation" placeholder="Affiliation (optional)" value="${affiliation}">
            </div>
            <div class="col-md-4">
                <input type="email" class="form-control form-control-sm author-email" placeholder="Email (optional)" value="${email}">
            </div>
        </div>
    `;

    row.querySelectorAll('input').forEach(input => {
        input.addEventListener('input', () => {
            _validateAuthorOptionalFields(row);
            updateCreateProjectButton();
            validateAuthorsBadge(); // Update badge color when authors change
        });
    });

    row.querySelector('.remove-author').addEventListener('click', () => {
        row.remove();
        if (!document.querySelector('#metadataAuthorsList .author-row')) {
            addAuthorRow();
        }
        updateCreateProjectButton();
        validateAuthorsBadge(); // Update badge color when authors change
        _updateAuthorRowLabels();
    });

    row.querySelector('.move-author-up')?.addEventListener('click', () => {
        _moveAuthorRow(row, 'up');
    });

    row.querySelector('.move-author-down')?.addEventListener('click', () => {
        _moveAuthorRow(row, 'down');
    });

    list.appendChild(row);
    _wireAuthorRowDrag(row);
    _validateAuthorOptionalFields(row);
    _updateAuthorRowLabels();
}

function getAuthorState() {
    const rows = document.querySelectorAll('#metadataAuthorsList .author-row');
    let completeCount = 0;
    let incompleteCount = 0;

    rows.forEach(row => {
        const first = (row.querySelector('.author-first')?.value || '').trim();
        const last = (row.querySelector('.author-last')?.value || '').trim();
        const hasFirst = Boolean(first);
        const hasLast = Boolean(last);

        if (hasFirst && hasLast) {
            completeCount += 1;
        } else if (hasFirst || hasLast) {
            incompleteCount += 1;
        }
    });

    return { completeCount, incompleteCount };
}

export function getAuthorsList() {
    const rows = document.querySelectorAll('#metadataAuthorsList .author-row');
    const authors = [];
    rows.forEach(row => {
        const first = (row.querySelector('.author-first')?.value || '').trim();
        const last = (row.querySelector('.author-last')?.value || '').trim();
        if (!first || !last) return;
        const formatted = _formatAuthor(first, last);
        if (formatted) authors.push(formatted);
    });
    return authors;
}

export function getCitationAuthorsList() {
    const rows = document.querySelectorAll('#metadataAuthorsList .author-row');
    const authors = [];
    rows.forEach(row => {
        const first = (row.querySelector('.author-first')?.value || '').trim();
        const last = (row.querySelector('.author-last')?.value || '').trim();
        if (!first || !last) return;

        const author = {
            'given-names': first,
            'family-names': last,
        };

        const website = (row.querySelector('.author-website')?.value || '').trim();
        const orcid = (row.querySelector('.author-orcid')?.value || '').trim();
        const affiliation = (row.querySelector('.author-affiliation')?.value || '').trim();
        const email = (row.querySelector('.author-email')?.value || '').trim();

        if (website && _isValidWebsiteFormat(website)) author.website = website;
        if (orcid && _isValidOrcidFormat(orcid)) author.orcid = orcid;
        if (affiliation) author.affiliation = affiliation;
        if (email && _isValidEmailFormat(email)) author.email = email;

        authors.push(author);
    });
    return authors;
}

export function hasAtLeastOneAuthor() {
    const authorState = getAuthorState();
    return authorState.completeCount > 0 && authorState.incompleteCount === 0;
}

export function setAuthorsList(authors) {
    const list = document.getElementById('metadataAuthorsList');
    if (!list) return;
    list.innerHTML = '';
    if (!Array.isArray(authors) || authors.length === 0) {
        addAuthorRow();
        return;
    }
    authors.forEach(author => {
        const parsed = _parseAuthor(author);
        addAuthorRow(parsed.first, parsed.last, {
            website: parsed.website,
            orcid: parsed.orcid,
            affiliation: parsed.affiliation,
            email: parsed.email,
        });
    });
    _updateAuthorRowLabels();
}

// ===== RECRUITMENT LOCATIONS =====

function _parseRecLocationValue(value = '') {
    const raw = String(value || '').trim();
    if (!raw) return { city: '', country: '' };
    if (/^online(\s+only)?$/i.test(raw)) return { city: '', country: '' };

    const parts = raw.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length <= 1) {
        return { city: '', country: raw };
    }
    return {
        city: parts.slice(0, -1).join(', '),
        country: parts[parts.length - 1]
    };
}

export function toggleRecLocationInputs() {
    const onlineOnly = document.getElementById('smRecLocationOnlineOnly')?.checked;
    const addBtn = document.getElementById('addRecLocationRow');
    const rows = document.querySelectorAll('#smRecLocationList .rec-location-row');

    if (addBtn) addBtn.disabled = Boolean(onlineOnly);
    rows.forEach(row => {
        row.querySelectorAll('input, button').forEach(el => {
            el.disabled = Boolean(onlineOnly);
        });
    });
    validateRecLocationBadge();
}

export function addRecLocationRow(value = '') {
    const list = document.getElementById('smRecLocationList');
    if (!list) return;

    const parsed = _parseRecLocationValue(value);
    const row = document.createElement('div');
    row.className = 'd-flex gap-2 align-items-center rec-location-row';
    row.innerHTML = `
        <input type="text" class="form-control form-control-sm rec-location-city" placeholder="City (optional)" value="${parsed.city}" title="Enter city name (optional).">
        <input type="text" class="form-control form-control-sm rec-location-country" placeholder="Country (required)" value="${parsed.country}" title="Enter country name (required unless online-only is enabled).">
        <button type="button" class="btn btn-outline-danger btn-sm remove-location">
            <i class="fas fa-times"></i>
        </button>
    `;

    row.querySelector('.rec-location-city').addEventListener('input', () => {
        updateCreateProjectButton();
        validateRecLocationBadge();
    });

    row.querySelector('.rec-location-country').addEventListener('input', () => {
        updateCreateProjectButton();
        validateRecLocationBadge();
    });

    row.querySelector('.remove-location').addEventListener('click', () => {
        row.remove();
        if (!document.querySelector('#smRecLocationList .rec-location-row')) {
            addRecLocationRow();
        }
        updateCreateProjectButton();
        validateRecLocationBadge();
    });

    list.appendChild(row);
    toggleRecLocationInputs();
}

export function getRecLocationList() {
    const onlineOnly = document.getElementById('smRecLocationOnlineOnly')?.checked;
    if (onlineOnly) {
        return ['Online'];
    }

    const rows = document.querySelectorAll('#smRecLocationList .rec-location-row');
    const locations = [];
    rows.forEach(row => {
        const city = (row.querySelector('.rec-location-city')?.value || '').trim();
        const country = (row.querySelector('.rec-location-country')?.value || '').trim();
        if (!country) return;
        locations.push(city ? `${city}, ${country}` : country);
    });
    return locations;
}

export function hasAtLeastOneRecLocation() {
    if (document.getElementById('smRecLocationOnlineOnly')?.checked) {
        return true;
    }
    return getRecLocationList().length > 0;
}

export function setRecLocationList(locations) {
    const list = document.getElementById('smRecLocationList');
    if (!list) return;
    list.innerHTML = '';

    const onlineOnlyInput = document.getElementById('smRecLocationOnlineOnly');
    const values = Array.isArray(locations) ? locations : [];
    const nonOnline = values.filter(loc => !/^online(\s+only)?$/i.test(String(loc || '').trim()));
    if (onlineOnlyInput) {
        onlineOnlyInput.checked = values.some(loc => /^online(\s+only)?$/i.test(String(loc || '').trim()));
    }

    if (nonOnline.length === 0) {
        addRecLocationRow();
        toggleRecLocationInputs();
        // Update badge after checkbox is set
        validateRecLocationBadge();
        return;
    }
    nonOnline.forEach(loc => addRecLocationRow(loc));
    toggleRecLocationInputs();
    // Update badge after locations are set
    validateRecLocationBadge();
}

export function getRecMethodList() {
    const select = document.getElementById('smRecMethod');
    if (!select) return [];
    return Array.from(select.selectedOptions)
        .map(opt => opt.value)
        .filter(v => v && v.trim());
}

export function hasAtLeastOneRecMethod() {
    return getRecMethodList().length > 0;
}

export function setRecMethodList(methods) {
    const select = document.getElementById('smRecMethod');
    if (!select) return;
    const values = Array.isArray(methods) ? methods : [];
    Array.from(select.options).forEach(opt => {
        opt.selected = values.includes(opt.value);
    });
}

export function initYearMonthSelect(yearSelectId, monthSelectId) {
    const yearSelect = document.getElementById(yearSelectId);
    const monthSelect = document.getElementById(monthSelectId);
    if (!yearSelect || !monthSelect) return;

    const now = new Date();
    const currentYear = now.getFullYear();
    const startYear = currentYear - 20;
    const endYear = currentYear;

    yearSelect.innerHTML = '<option value="">Year</option>';
    for (let y = endYear; y >= startYear; y -= 1) {
        const opt = document.createElement('option');
        opt.value = String(y);
        opt.textContent = String(y);
        yearSelect.appendChild(opt);
    }

    monthSelect.innerHTML = '<option value="">Month</option>';
    const currentMonth = now.getMonth() + 1;
    const orderedMonths = [];
    for (let m = currentMonth; m <= 12; m += 1) orderedMonths.push(m);
    for (let m = 1; m < currentMonth; m += 1) orderedMonths.push(m);
    orderedMonths.forEach(m => {
        const value = String(m).padStart(2, '0');
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        monthSelect.appendChild(opt);
    });
}

export function getYearMonthValue(yearSelectId, monthSelectId) {
    const year = document.getElementById(yearSelectId)?.value || '';
    const month = document.getElementById(monthSelectId)?.value || '';
    if (!year || !month) return '';
    return `${year}-${month}`;
}

export function setYearMonthValue(yearSelectId, monthSelectId, value) {
    const yearSelect = document.getElementById(yearSelectId);
    const monthSelect = document.getElementById(monthSelectId);
    if (!value) {
        if (yearSelect) yearSelect.value = '';
        if (monthSelect) monthSelect.value = '';
        return;
    }
    const parts = value.split('-');
    if (parts.length < 2) return;
    const year = parts[0];
    const month = parts[1];
    if (yearSelect) yearSelect.value = year;
    if (monthSelect) monthSelect.value = month;
}

export function hasRecPeriodStart() {
    return Boolean(getYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth'));
}

export function hasRecPeriodEnd() {
    return Boolean(getYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth'));
}

export function getRecPeriodRangeError() {
    const start = getYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth');
    const end = getYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth');
    if (!start || !end) return '';
    if (start > end) {
        return 'Recruitment period start must be before or equal to period end.';
    }
    return '';
}

// ===== MANDATORY METADATA VALIDATION =====

export function validateAllMandatoryFields() {
    const completeness = computeLocalCompleteness();
    const emptyFields = [];
    const invalidFields = [];

    const labels = {
        Basics: {
            Name: 'Dataset Name (min. 3 characters)',
            Authors: 'Authors (at least 1)',
            Keywords: 'Keywords (at least 3)',
            EthicsApprovals: 'Ethics Approvals (select Yes or No)',
            Funding: 'Funding (select Yes or No)'
        },
        Overview: {
            Main: 'Dataset Overview'
        },
        StudyDesign: {
            Type: 'Study Design Type'
        },
        Recruitment: {
            Method: 'Recruitment Method',
            Location: 'Recruitment Location',
            'Period.Start': 'Recruitment Period Start',
            'Period.End': 'Recruitment Period End',
            Compensation: 'Financial Compensation'
        },
        Eligibility: {
            InclusionCriteria: 'Inclusion Criteria',
            ExclusionCriteria: 'Exclusion Criteria'
        },
        Procedure: {
            Overview: 'Procedure Overview'
        }
    };

    Object.entries(completeness.sections || {}).forEach(([sectionName, section]) => {
        (section.fields || []).forEach(field => {
            if (!field.required || field.filled) return;
            const friendlyLabel = labels[sectionName]?.[field.name] || `${sectionName}: ${field.name}`;
            emptyFields.push(friendlyLabel);
        });
    });

    const periodError = getRecPeriodRangeError();
    if (periodError) {
        invalidFields.push(periodError);
    }

    const datasetName = (document.getElementById('metadataName')?.value || '').trim();
    if (datasetName.length > 0 && datasetName.length < 3) {
        invalidFields.push('Dataset Name must be at least 3 characters long.');
    }

    const authorState = getAuthorState();
    if (authorState.completeCount < 1) {
        invalidFields.push('At least one Author with first and last name is required.');
    }
    if (authorState.incompleteCount > 0) {
        invalidFields.push('Each Author entry must include both first and last name.');
    }

    if (!hasEthicsChoice()) {
        invalidFields.push('Please select Ethics Approvals: Yes or No.');
    } else if (!hasValidEthicsResponse()) {
        invalidFields.push('Ethics details are required when Ethics Approvals is set to Yes.');
    }

    if (!hasFundingChoice()) {
        invalidFields.push('Please select Funding: Yes or No.');
    } else if (!hasValidFundingResponse()) {
        invalidFields.push('Funding details are required when Funding is set to Yes.');
    }

    const keywords = (document.getElementById('metadataKeywords')?.value || '')
        .split(',').map(s => s.trim()).filter(s => s);
    if (keywords.length < 3) {
        invalidFields.push('At least 3 Keywords are required (comma-separated).');
    }

    const doiValue = (document.getElementById('metadataDOI')?.value || '').trim();
    if (doiValue && !_isValidDoiFormat(doiValue)) {
        invalidFields.push('Dataset DOI format is invalid (use 10.xxxx/... or https://doi.org/10.xxxx/...).');
    }

    invalidFields.push(..._getAuthorOptionalFormatErrors());

    return {
        isValid: emptyFields.length === 0 && invalidFields.length === 0,
        emptyFields,
        invalidFields
    };
}

function _showRequirementGapWarning() {
    const validation = validateAllMandatoryFields();
    _updateRequirementGapInlineAlert(validation);
    _updateProjectBoxRequirementAlert(validation);
    _updateProjectMetadataStat(validation);
    if (validation.isValid) {
        return;
    }
}

function _updateProjectBoxRequirementAlert(validation) {
    const alertEl = document.getElementById('projectRequirementGapAlert');
    const textEl = document.getElementById('projectRequirementGapText');
    if (!alertEl || !textEl) {
        return;
    }

    if (!validation || validation.isValid) {
        alertEl.classList.add('d-none');
        textEl.textContent = '';
        return;
    }

    const issueCount =
        validation.emptyFields.length + (validation.invalidFields?.length || 0);
    textEl.textContent =
        `Fill out all required fields (${issueCount} remaining). This project was loaded with missing current requirements.`;
    alertEl.classList.remove('d-none');
}

function _updateProjectMetadataStat(validation) {
    const statItem = document.getElementById('projectMetadataStatItem');
    const statValue = document.getElementById('projectMetadataStatValue');
    if (!statItem || !statValue) {
        return;
    }

    const hasIssues = validation && !validation.isValid;
    if (!hasIssues) {
        statItem.classList.remove('border', 'border-danger');
        statValue.classList.remove('text-danger');
        statValue.classList.add('text-success');
        statValue.textContent = '✓';
        return;
    }

    const issueCount =
        validation.emptyFields.length + (validation.invalidFields?.length || 0);
    statItem.classList.add('border', 'border-danger');
    statValue.classList.remove('text-success');
    statValue.classList.add('text-danger');
    statValue.textContent = `${issueCount}`;
}

function _updateRequirementGapInlineAlert(validation) {
    const alertEl = document.getElementById('smRequirementGapAlert');
    const textEl = document.getElementById('smRequirementGapText');
    if (!alertEl || !textEl) {
        return;
    }

    if (!validation || validation.isValid) {
        alertEl.classList.add('d-none');
        textEl.textContent = 'Fill out all required fields.';
        return;
    }

    const missing = validation.emptyFields || [];
    const invalid = validation.invalidFields || [];
    const total = missing.length + invalid.length;
    const firstIssues = [...missing, ...invalid].slice(0, 3);
    const suffix =
        total > firstIssues.length
            ? ` (+${total - firstIssues.length} more)`
            : '';

    textEl.textContent =
        `Fill out all required fields (${total} remaining). `
        + (firstIssues.length ? `Missing: ${firstIssues.join(' • ')}${suffix}` : '');
    alertEl.classList.remove('d-none');
}

export function updateCreateProjectButton() {
    const createBtn = document.getElementById('createProjectSubmitBtn');
    if (!createBtn) return;

    const validation = validateAllMandatoryFields();
    _updateRequirementGapInlineAlert(validation);
    _updateProjectBoxRequirementAlert(validation);
    _updateProjectMetadataStat(validation);

    const createSection = document.getElementById('section-create');
    const createActive = createSection && createSection.classList.contains('active');
    const isCreateMode = Boolean(createActive);
    const actionHint = document.getElementById('metadataActionHint');

    if (!isCreateMode) {
        createBtn.disabled = false;
        createBtn.classList.remove('btn-secondary', 'btn-success');
        createBtn.classList.add('btn-info');
        createBtn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes to Project';
        createBtn.removeAttribute('title');
        if (actionHint) {
            actionHint.innerHTML = '<i class="fas fa-info-circle me-1"></i>Save metadata updates to project.json, dataset_description.json, and README.md.';
        }
        return;
    }

    createBtn.innerHTML = '<i class="fas fa-folder-plus me-2"></i>Create Project';
    createBtn.classList.remove('btn-info');

    if (validation.isValid) {
        createBtn.disabled = false;
        createBtn.classList.remove('btn-secondary');
        createBtn.classList.add('btn-success');
        createBtn.removeAttribute('title');
        if (actionHint) {
            actionHint.innerHTML = '<i class="fas fa-info-circle me-1"></i>All required fields are complete. You can now create the project.';
        }
    } else {
        createBtn.disabled = true;
        createBtn.classList.remove('btn-success');
        createBtn.classList.add('btn-secondary');
        const count = validation.emptyFields.length + (validation.invalidFields?.length || 0);
        createBtn.title = `${count} required item${count > 1 ? 's' : ''} remaining in Study Metadata.`;
        if (actionHint) {
            actionHint.innerHTML = '<i class="fas fa-info-circle me-1"></i>Fill all required fields to enable project creation.';
        }
    }
}

const mandatoryFieldIds = [
    'metadataName',
    'metadataKeywords',
    'smOverviewMain', 'smSDType', 'smRecMethod',
    'smRecPeriodStartYear', 'smRecPeriodStartMonth',
    'smRecPeriodEndYear', 'smRecPeriodEndMonth',
    'smRecLocationOnlineOnly',
    'smRecCompensation',
    'smEligInclusion', 'smEligExclusion',
    'smProcOverview'
];

mandatoryFieldIds.forEach(fieldId => {
    const element = document.getElementById(fieldId);
    if (element) {
        const eventType = element.tagName === 'SELECT' ? 'change' : 'input';
        element.addEventListener(eventType, function() {
            updateCreateProjectButton();
        });
    }
});

// Authors row add button
const addAuthorButton = document.getElementById('addAuthorRow');
if (addAuthorButton) {
    addAuthorButton.addEventListener('click', () => addAuthorRow());
}

// Recruitment location add button
const addRecLocationButton = document.getElementById('addRecLocationRow');
if (addRecLocationButton) {
    addRecLocationButton.addEventListener('click', () => addRecLocationRow());
}

const recLocationOnlineOnly = document.getElementById('smRecLocationOnlineOnly');
if (recLocationOnlineOnly) {
    recLocationOnlineOnly.addEventListener('change', () => {
        toggleRecLocationInputs();
        updateCreateProjectButton();
    });
}

const metadataNameInput = document.getElementById('metadataName');
if (metadataNameInput) {
    metadataNameInput.addEventListener('input', function() {
        updateCreateProjectButton();

        // Auto-populate project name from dataset name (sanitized)
        const datasetName = this.value.trim();
        const projectNameField = document.getElementById('projectName');
        if (!projectNameField) return;

        // Only auto-populate if the project name field is empty
        if (projectNameField.value === '') {
            const sanitizedName = datasetName
                .toLowerCase()
                .replace(/[^a-z0-9_-]/g, '_')
                .replace(/_+/g, '_')
                .replace(/^_|_$/g, '');

            if (sanitizedName) {
                projectNameField.value = sanitizedName;
            }
        }
    });
}

// ===== DATASET DESCRIPTION / METADATA =====

export function buildDraftDatasetDescriptionForValidation() {
    const overviewMain = document.getElementById('smOverviewMain')?.value?.trim() || '';
    const doiValue = document.getElementById('metadataDOI')?.value?.trim() || '';
    const normalizedDoi = _normalizeDoi(doiValue);
    return {
        Name: document.getElementById('metadataName')?.value?.trim() || '',
        Authors: getAuthorsList(),
        License: document.getElementById('metadataLicense')?.value || '',
        Acknowledgements: document.getElementById('metadataAcknowledgements')?.value?.trim() || '',
        DatasetDOI: _isValidDoiFormat(doiValue) ? normalizedDoi : '',
        EthicsApprovals: getEthicsApprovals(),
        Keywords: (document.getElementById('metadataKeywords')?.value || '')
            .split(',').map(s => s.trim()).filter(s => s),
        BIDSVersion: '1.10.1',
        DatasetType: document.getElementById('metadataType')?.value || undefined,
        HowToAcknowledge: document.getElementById('metadataHowToAcknowledge')?.value?.trim() || '',
        Funding: getFundingList(),
        ReferencesAndLinks: (document.getElementById('metadataReferences')?.value || '')
            .split(',').map(s => s.trim()).filter(s => s),
        HEDVersion: document.getElementById('metadataHED')?.value?.trim() || '',
        Description: overviewMain || undefined
    };
}

function buildDraftCitationFieldsForValidation() {
    return {
        Authors: getCitationAuthorsList(),
        License: document.getElementById('metadataLicense')?.value || '',
        HowToAcknowledge: document.getElementById('metadataHowToAcknowledge')?.value?.trim() || '',
        ReferencesAndLinks: (document.getElementById('metadataReferences')?.value || '')
            .split(',').map(s => s.trim()).filter(s => s),
    };
}

let descriptionValidationTimer = null;
export async function validateDatasetDescriptionDraftLive() {
    // Don't validate for new projects (only when editing existing projects)
    if (!window.currentProjectPath) {
        return;
    }
    
    const payload = {
        description: buildDraftDatasetDescriptionForValidation(),
        citation_fields: buildDraftCitationFieldsForValidation(),
    };
    try {
        const response = await fetch('/api/projects/description/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.success) {
            displayMetadataIssues(result.issues || []);
        }
    } catch (error) {
        // Keep UX quiet for transient validation failures
        console.debug('Live description validation failed:', error);
    }
}

export function scheduleLiveDescriptionValidation() {
    if (descriptionValidationTimer) {
        clearTimeout(descriptionValidationTimer);
    }
    descriptionValidationTimer = setTimeout(() => {
        validateDatasetDescriptionDraftLive();
    }, 250);
}

export async function loadDatasetDescriptionFields() {
    if (!window.currentProjectPath) return;

    try {
        const response = await fetch('/api/projects/description');
        const data = await response.json();

        if (data.success && data.description) {
            const desc = data.description;

            document.getElementById('metadataName').value = desc.Name || '';
            setAuthorsList(Array.isArray(desc.Authors) ? desc.Authors : (desc.Authors ? [desc.Authors] : []));
            document.getElementById('metadataLicense').value = desc.License || 'CC0';
            document.getElementById('metadataAcknowledgements').value = desc.Acknowledgements || '';
            document.getElementById('metadataDOI').value = desc.DatasetDOI || '';
            setEthicsApprovals(desc.EthicsApprovals);
            document.getElementById('metadataKeywords').value = Array.isArray(desc.Keywords) ? desc.Keywords.join(', ') : (desc.Keywords || '');
            document.getElementById('metadataType').value = desc.DatasetType || '';
            document.getElementById('metadataHED').value = Array.isArray(desc.HEDVersion) ? desc.HEDVersion.join(', ') : (desc.HEDVersion || '');
            setFundingFromDescription(desc.Funding);
            document.getElementById('metadataHowToAcknowledge').value = desc.HowToAcknowledge || '';
            document.getElementById('metadataReferences').value = Array.isArray(desc.ReferencesAndLinks) ? desc.ReferencesAndLinks.join(', ') : (desc.ReferencesAndLinks || '');

            displayMetadataIssues(data.issues || []);
            
            // Trigger validation on all loaded fields so badges turn green if filled
            setTimeout(() => {
                const fieldsToValidate = [
                    'metadataName', 'metadataLicense', 'metadataAcknowledgements',
                    'metadataDOI', 'metadataType', 'metadataHED', 'metadataKeywords',
                    'metadataHowToAcknowledge', 'metadataReferences'
                ];
                fieldsToValidate.forEach(fieldId => {
                    try {
                        validateProjectField(fieldId);
                    } catch (e) {
                        console.log(`Could not validate ${fieldId}:`, e.message);
                    }
                });
                validateAuthorsBadge();
                validateRecLocationBadge();
                validateEthicsBadge();
                validateFundingBadge();
                _showRequirementGapWarning();
            }, 100);
        }
    } catch (error) {
        console.error('Error loading dataset description:', error);
    }
}

export function displayMetadataIssues(issues) {
    const feedbackDiv = document.getElementById('metadataValidationFeedback');
    if (!feedbackDiv) return;

    if (!issues || issues.length === 0) {
        feedbackDiv.style.display = 'none';
        feedbackDiv.innerHTML = '';
        return;
    }

    feedbackDiv.style.display = 'block';
    let html = `
        <div class="alert alert-danger py-2 mb-0">
            <div class="fw-bold mb-1 small text-uppercase">
                <i class="fas fa-times-circle me-2"></i>Dataset Description Issues (${issues.length})
            </div>
            <ul class="mb-0 ps-3 small">
    `;

    issues.forEach(issue => {
        html += `
            <li class="mb-1">
                <strong>${issue.message}</strong>
                ${issue.fix_hint ? `<div class="text-muted smaller"><i class="fas fa-lightbulb me-1"></i>${issue.fix_hint}</div>` : ''}
            </li>
        `;
    });

    html += `
            </ul>
        </div>
    `;
    feedbackDiv.innerHTML = html;
}

export async function saveDatasetDescription() {
    try {
        const nameField = document.getElementById('metadataName');
        if (!nameField || !nameField.value.trim()) {
            throw new Error('REQUIRED FIELD: Dataset Name is mandatory per BIDS specification');
        }

        const overviewMain = document.getElementById('smOverviewMain');
        const overviewText = overviewMain ? overviewMain.value.trim() : '';
        const doiValue = document.getElementById('metadataDOI').value.trim();
        const normalizedDoi = _normalizeDoi(doiValue);

        const formatErrors = _getAuthorOptionalFormatErrors();
        if (doiValue && !_isValidDoiFormat(doiValue)) {
            formatErrors.push('Dataset DOI format is invalid (use 10.xxxx/... or https://doi.org/10.xxxx/...).');
        }
        if (formatErrors.length) {
            throw new Error(formatErrors.join(' '));
        }

        const description = {
            Name: nameField.value.trim(),
            Authors: getAuthorsList(),
            License: document.getElementById('metadataLicense').value,
            Acknowledgements: document.getElementById('metadataAcknowledgements').value,
            DatasetDOI: normalizedDoi,
            EthicsApprovals: getEthicsApprovals(),
            Keywords: document.getElementById('metadataKeywords').value.split(',').map(s => s.trim()).filter(s => s),
            BIDSVersion: '1.10.1',
            DatasetType: document.getElementById('metadataType').value || undefined,
            HowToAcknowledge: document.getElementById('metadataHowToAcknowledge').value,
            Funding: getFundingList(),
            ReferencesAndLinks: document.getElementById('metadataReferences').value.split(',').map(s => s.trim()).filter(s => s),
            HEDVersion: document.getElementById('metadataHED').value.trim(),
            Description: overviewText || undefined
        };

        const citationFields = {
            Authors: getCitationAuthorsList(),
            License: document.getElementById('metadataLicense').value,
            HowToAcknowledge: document.getElementById('metadataHowToAcknowledge').value,
            ReferencesAndLinks: document.getElementById('metadataReferences').value.split(',').map(s => s.trim()).filter(s => s),
        };

        try {
            const currentResp = await fetch('/api/projects/description');
            const currentData = await currentResp.json();
            if (currentData.success && currentData.description) {
                description.GeneratedBy = currentData.description.GeneratedBy;
                description.SourceDatasets = currentData.description.SourceDatasets;
                description.DatasetLinks = currentData.description.DatasetLinks;
            }
        } catch (e) {
            console.warn('Could not merge with existing description', e);
        }

        const response = await fetch('/api/projects/description', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description, citation_fields: citationFields })
        });

        const result = await response.json();
        if (result.success) {
            displayMetadataIssues(result.issues || []);

            if (description.Name && description.Name !== window.currentProjectName) {
                window.currentProjectName = description.Name;
                if (window.updateNavbarProject && window.currentProjectPath) {
                    window.updateNavbarProject(window.currentProjectName, window.currentProjectPath);
                }
            }
        } else {
            throw new Error(result.error || 'Failed to save metadata');
        }
    } catch (error) {
        console.error('Error saving dataset description:', error);
        throw error;
    }
}

// ===== STUDY METADATA =====

export function showStudyMetadataCard() {
    const card = document.getElementById('studyMetadataCard');
    if (!card) return;
    
    const completenessPanel = document.getElementById('smCompletenessPanel');
    const editingProjectInfo = document.getElementById('smEditingProjectInfo');
    const newProjectInfo = document.getElementById('smNewProjectInfo');
    const bidsInfoAlert = document.getElementById('smBidsInfoAlert');
    const saveSection = document.getElementById('saveStudyMetadataSection');
    const metadataSection = document.getElementById('studyMetadataSection');
    
    const createSection = document.getElementById('section-create');
    const createActive = createSection && createSection.classList.contains('active');
    const isNewProject = createActive && !window.currentProjectPath;
    
    if (window.currentProjectPath || createActive) {
        card.style.display = 'block';
        
        // For new projects: hide info panels and save button, show data
        // For existing projects: show everything
        if (completenessPanel) {
            completenessPanel.style.display = isNewProject ? 'none' : 'block';
        }
        if (editingProjectInfo) {
            editingProjectInfo.style.display = isNewProject ? 'none' : 'block';
        }
        if (newProjectInfo) {
            newProjectInfo.style.display = isNewProject ? 'block' : 'none';
        }
        if (bidsInfoAlert) {
            bidsInfoAlert.style.display = isNewProject ? 'none' : 'block';
        }
        if (saveSection) {
            saveSection.style.display = 'block';
        }

        if (metadataSection && window.bootstrap?.Collapse) {
            window.bootstrap.Collapse.getOrCreateInstance(metadataSection).show();
        }
        
        if (createActive) {
            resetStudyMetadataForm();
        } else if (window.currentProjectPath) {
            loadStudyMetadata();
        }
        updateCreateProjectButton();
        return;
    }
    
    card.style.display = 'none';
}

export function resetStudyMetadataForm() {
    const form = document.getElementById('studyMetadataForm');
    if (!form) return;

    form.querySelectorAll('input, textarea, select').forEach(el => {
        if (el.tagName === 'SELECT') {
            if (el.multiple) {
                Array.from(el.options).forEach(option => {
                    option.selected = false;
                });
            } else {
                el.value = '';
            }
            return;
        }

        if (el.type === 'checkbox' || el.type === 'radio') {
            el.checked = false;
            return;
        }

        el.value = '';
    });

    setAuthorsList([]);
    setRecLocationList([]);
    setRecMethodList([]);
    setEthicsChoice('');
    setFundingChoice('');
    setYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth', '');
    setYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth', '');
    const condType = document.getElementById('smSDConditionType');
    if (condType) condType.value = '';
    _clearAllHintBadges();
    displayMetadataIssues([]);

    const badgeIds = [
        'smBasicsBadge', 'smOverviewBadge', 'smStudyDesignBadge',
        'smRecruitmentBadge', 'smEligibilityBadge',
        'smProcedureBadge', 'smMissingDataBadge', 'smReferencesBadge'
    ];
    badgeIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '';
    });

    updateCompletenessUI(computeLocalCompleteness());
    updateCreateProjectButton();
    
    // Reset all field badges to their original state
    if (window.resetAllBadges) {
        window.resetAllBadges();
    }
}

const _smHintFieldMap = {
    'Recruitment.Period.Start': { el: null, type: 'period-start' },
    'Recruitment.Period.End': { el: null, type: 'period-end' },
    'StudyDesign.Type': { el: 'smSDType', type: 'select' },
    'Conditions.Type': { el: 'smSDConditionType', type: 'select' },
    'Eligibility.ActualSampleSize': { el: 'smEligSampleSize', type: 'input' }
};

function _clearAllHintBadges() {
    document.querySelectorAll('.sm-hint-badge').forEach(b => b.remove());
}

function _applyHintBadge(elementId, hint, type) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const currentVal = type === 'select' ? el.value : el.value.trim();
    if (currentVal) return;

    const existingBadge = el.parentElement.querySelector('.sm-hint-badge');
    if (existingBadge) existingBadge.remove();

    const displayVal = typeof hint.value === 'number' ? hint.value : hint.value;
    const badge = document.createElement('span');
    badge.className = 'sm-hint-badge badge bg-info bg-opacity-75 ms-1 mt-1';
    badge.style.cssText = 'cursor:pointer; font-size:0.7rem; display:inline-block;';
    badge.title = `Detected from ${hint.source} — click to apply`;
    badge.innerHTML = `<i class="fas fa-magic me-1"></i>${displayVal}`;
    badge.addEventListener('click', () => {
        el.value = hint.value;
        badge.remove();
        if (type === 'select') el.dispatchEvent(new Event('change'));
    });

    el.parentElement.appendChild(badge);
}

function _applyHints(hints) {
    _clearAllHintBadges();
    if (!hints || typeof hints !== 'object') return;

    for (const [key, hint] of Object.entries(hints)) {
        const mapping = _smHintFieldMap[key];
        if (!mapping) continue;
        if (mapping.type === 'period-start') {
            setYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth', hint.value);
            continue;
        }
        if (mapping.type === 'period-end') {
            setYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth', hint.value);
            continue;
        }
        if (mapping.type === 'special') continue;
        _applyHintBadge(mapping.el, hint, mapping.type);
    }
}

export async function loadStudyMetadata() {
    try {
        if (!window.currentProjectPath) return;
        await loadDatasetDescriptionFields();

        const response = await fetch('/api/projects/study-metadata');
        const data = await response.json();
        if (!data.success) return;

        const sm = data.study_metadata;

        const overview = sm.Overview || {};
        document.getElementById('smOverviewMain').value = overview.Main || '';
        document.getElementById('smOverviewIV').value = overview.IndependentVariables || '';
        document.getElementById('smOverviewDV').value = overview.DependentVariables || '';
        document.getElementById('smOverviewCV').value = overview.ControlVariables || '';
        document.getElementById('smOverviewQA').value = overview.QualityAssessment || '';

        const sd = sm.StudyDesign || {};
        document.getElementById('smSDType').value = sd.Type || '';
        document.getElementById('smSDConditionType').value = sm.Conditions?.Type || '';
        document.getElementById('smSDTypeDesc').value = sd.TypeDescription || '';
        document.getElementById('smSDBlinding').value = sd.Blinding || '';
        document.getElementById('smSDRandomization').value = sd.Randomization || '';
        document.getElementById('smSDControl').value = sd.ControlCondition || '';
        toggleExperimentalFields();

        const rec = sm.Recruitment || {};
        if (Array.isArray(rec.Method)) {
            setRecMethodList(rec.Method);
        } else if (typeof rec.Method === 'string') {
            setRecMethodList(rec.Method.split(';').map(s => s.trim()).filter(s => s));
        } else {
            setRecMethodList([]);
        }
        if (Array.isArray(rec.Location)) {
            setRecLocationList(rec.Location);
        } else if (typeof rec.Location === 'string') {
            setRecLocationList(rec.Location.split(';').map(s => s.trim()).filter(s => s));
        } else {
            setRecLocationList([]);
        }
        const period = rec.Period || {};
        setYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth', period.Start || '');
        setYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth', period.End || '');
        if (rec.Compensation) {
            const comp = String(rec.Compensation).toLowerCase();
            if (comp.includes('no')) {
                document.getElementById('smRecCompensation').value = 'No financial compensation';
            } else if (comp.includes('financial')) {
                document.getElementById('smRecCompensation').value = 'Financial compensation';
            } else {
                document.getElementById('smRecCompensation').value = rec.Compensation;
            }
        } else {
            document.getElementById('smRecCompensation').value = '';
        }

        const elig = sm.Eligibility || {};
        document.getElementById('smEligInclusion').value = Array.isArray(elig.InclusionCriteria) ? elig.InclusionCriteria.join('\n') : '';
        document.getElementById('smEligExclusion').value = Array.isArray(elig.ExclusionCriteria) ? elig.ExclusionCriteria.join('\n') : '';
        document.getElementById('smEligSampleSize').value = elig.TargetSampleSize || '';
        document.getElementById('smEligPower').value = elig.PowerAnalysis || '';

        const proc = sm.Procedure || {};
        document.getElementById('smProcOverview').value = proc.Overview || '';
        document.getElementById('smProcConsent').value = proc.InformedConsent || '';
        document.getElementById('smProcQC').value = Array.isArray(proc.QualityControl) ? proc.QualityControl.join('\n') : '';
        document.getElementById('smProcMissing').value = proc.MissingDataHandling || '';
        document.getElementById('smProcDebriefing').value = proc.Debriefing || '';

        _applyHints(data.hints || {});

        if (data.completeness) {
            updateCompletenessUI(data.completeness);
        }

        updateCreateProjectButton();
        
        // Trigger validation on all study metadata fields so badges turn green if filled
        setTimeout(() => {
            const studyMetadataFields = [
                'smOverviewMain', 'smOverviewIV', 'smOverviewDV', 'smOverviewCV', 'smOverviewQA',
                'smSDType', 'smSDConditionType', 'smSDTypeDesc', 'smSDBlinding', 'smSDRandomization', 'smSDControl',
                'smRecMethod', 'smRecPeriodStartYear', 'smRecPeriodStartMonth', 'smRecPeriodEndYear', 'smRecPeriodEndMonth', 'smRecCompensation',
                'smEligInclusion', 'smEligExclusion', 'smEligSampleSize', 'smEligPower',
                'smProcOverview', 'smProcConsent', 'smProcQC', 'smProcMissing', 'smProcDebriefing'
            ];
            
            studyMetadataFields.forEach(fieldId => {
                try {
                    const field = document.getElementById(fieldId);
                    if (field && field.value.trim()) {
                        validateProjectField(fieldId);
                    }
                } catch (e) {
                    console.log(`Could not validate ${fieldId}:`, e.message);
                }
            });
            
            // Validate special cases
            validateRecMethodBadge();
            validateRecLocationBadge();
            validateDateRangeBadge('smRecPeriodStartYear', 'smRecPeriodStartMonth', 'Period Start');
            validateDateRangeBadge('smRecPeriodEndYear', 'smRecPeriodEndMonth', 'Period End');
        }, 150);
    } catch (error) {
        console.error('Error loading study metadata:', error);
    }
}

export function toggleExperimentalFields() {
    const sdType = document.getElementById('smSDType').value;
    const experimentalTypes = ['randomized-controlled-trial', 'quasi-experimental', 'case-control'];
    const block = document.getElementById('smExperimentalFields');
    if (block) {
        block.style.display = experimentalTypes.includes(sdType) ? 'block' : 'none';
    }
}

export function toggleEthicsFields() {
    const approvedInput = document.getElementById('metadataEthicsApproved');
    const detailsSection = document.getElementById('ethicsDetailsSection');
    const committee = document.getElementById('metadataEthicsCommittee');
    const votum = document.getElementById('metadataEthicsVotum');

    if (!detailsSection) {
        console.error('ethicsDetailsSection not found');
        return;
    }

    if (!approvedInput) {
        console.warn('Ethics approval input not found, hiding details');
        detailsSection.style.display = 'none';
        detailsSection.classList.add('d-none');
        return;
    }

    const approved = approvedInput.value === 'yes';

    detailsSection.hidden = !approved;
    detailsSection.style.display = approved ? 'block' : 'none';
    detailsSection.classList.toggle('d-none', !approved);

    // Avoid native browser validation errors on hidden controls.
    // These fields are only required when ethics approval is set to "yes".
    if (committee) {
        committee.required = approved;
    }
    if (votum) {
        votum.required = approved;
    }
}

export function setEthicsChoice(choice) {
    const yesBtn = document.getElementById('metadataEthicsYes');
    const noBtn = document.getElementById('metadataEthicsNo');
    const approvedInput = document.getElementById('metadataEthicsApproved');
    if (!yesBtn || !noBtn || !approvedInput) {
        console.warn('Ethics approval inputs not found');
        return;
    }

    const normalized = choice === 'yes' || choice === 'no' ? choice : '';
    const isYes = normalized === 'yes';
    const isNo = normalized === 'no';

    approvedInput.value = normalized;
    yesBtn.classList.toggle('btn-primary', isYes);
    yesBtn.classList.toggle('btn-outline-primary', !isYes);
    noBtn.classList.toggle('btn-primary', isNo);
    noBtn.classList.toggle('btn-outline-primary', !isNo);

    if (!isYes) {
        const committee = document.getElementById('metadataEthicsCommittee');
        const votum = document.getElementById('metadataEthicsVotum');
        if (committee) committee.value = '';
        if (votum) votum.value = '';
    }

    toggleEthicsFields();
    validateEthicsBadge();
    updateCreateProjectButton();
}

function hasEthicsChoice() {
    const approvedInput = document.getElementById('metadataEthicsApproved');
    if (!approvedInput) return false;
    return approvedInput.value === 'yes' || approvedInput.value === 'no';
}

function hasValidEthicsResponse() {
    const approvedInput = document.getElementById('metadataEthicsApproved');
    if (!approvedInput) return false;

    if (approvedInput.value === 'no') return true;
    if (approvedInput.value !== 'yes') return false;

    const committee = (document.getElementById('metadataEthicsCommittee')?.value || '').trim();
    const votum = (document.getElementById('metadataEthicsVotum')?.value || '').trim();
    return Boolean(committee && votum);
}

export function getEthicsApprovals() {
    const approvedInput = document.getElementById('metadataEthicsApproved');
    if (!approvedInput) {
        console.warn('Ethics approval input not found');
        return [];
    }
    if (approvedInput.value !== 'yes') {
        return [];
    }
    const committee = document.getElementById('metadataEthicsCommittee');
    const votum = document.getElementById('metadataEthicsVotum');
    if (!committee || !votum) {
        console.warn('Ethics committee or votum fields not found');
        return [];
    }
    const committeeValue = committee.value.trim();
    const votumValue = votum.value.trim();
    const approval = [];
    if (committeeValue) {
        approval.push(committeeValue + (votumValue ? ', ' + votumValue : ''));
    }
    return approval;
}

export function toggleFundingFields() {
    const declaredInput = document.getElementById('metadataFundingDeclared');
    const detailsSection = document.getElementById('fundingDetailsSection');

    if (!declaredInput || !detailsSection) return;

    const showDetails = declaredInput.value === 'yes';
    detailsSection.hidden = !showDetails;
    detailsSection.style.display = showDetails ? 'block' : 'none';
    detailsSection.classList.toggle('d-none', !showDetails);
}

export function setFundingChoice(choice) {
    const yesBtn = document.getElementById('metadataFundingYes');
    const noBtn = document.getElementById('metadataFundingNo');
    const declaredInput = document.getElementById('metadataFundingDeclared');
    const fundingField = document.getElementById('metadataFunding');

    if (!yesBtn || !noBtn || !declaredInput) return;

    const normalized = choice === 'yes' || choice === 'no' ? choice : '';
    const isYes = normalized === 'yes';
    const isNo = normalized === 'no';

    declaredInput.value = normalized;
    yesBtn.classList.toggle('btn-primary', isYes);
    yesBtn.classList.toggle('btn-outline-primary', !isYes);
    noBtn.classList.toggle('btn-primary', isNo);
    noBtn.classList.toggle('btn-outline-primary', !isNo);

    if (normalized !== 'yes' && fundingField) {
        fundingField.value = '';
    }

    toggleFundingFields();
    validateFundingBadge();
    updateCreateProjectButton();
}

function hasFundingChoice() {
    const declaredInput = document.getElementById('metadataFundingDeclared');
    if (!declaredInput) return false;
    return declaredInput.value === 'yes' || declaredInput.value === 'no';
}

export function getFundingList() {
    const declaredInput = document.getElementById('metadataFundingDeclared');
    const fundingField = document.getElementById('metadataFunding');
    if (!declaredInput) return [];

    if (declaredInput.value !== 'yes') return [];

    return (fundingField?.value || '')
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
}

function hasValidFundingResponse() {
    const declaredInput = document.getElementById('metadataFundingDeclared');
    if (!declaredInput) return false;

    if (declaredInput.value === 'no') return true;
    if (declaredInput.value === 'yes') return getFundingList().length > 0;
    return false;
}

function setFundingFromDescription(fundingValues) {
    const fundingField = document.getElementById('metadataFunding');
    if (!fundingField) return;

    const values = Array.isArray(fundingValues)
        ? fundingValues
        : (fundingValues ? [fundingValues] : []);
    const cleaned = values.map(v => String(v || '').trim()).filter(Boolean);

    if (cleaned.length > 0) {
        fundingField.value = cleaned.join(', ');
        setFundingChoice('yes');
    } else {
        fundingField.value = '';
        setFundingChoice('no');
    }
}

export function setEthicsApprovals(ethicsArray) {
    const committeeField = document.getElementById('metadataEthicsCommittee');
    const votumField = document.getElementById('metadataEthicsVotum');

    if (!committeeField || !votumField) {
        console.warn('Ethics approval form elements not found');
        return;
    }

    if (!ethicsArray || ethicsArray.length === 0) {
        committeeField.value = '';
        votumField.value = '';
        setEthicsChoice('no');
        return;
    }

    const ethicsStr = Array.isArray(ethicsArray) ? ethicsArray[0] : ethicsArray;
    const parts = String(ethicsStr || '').split(',').map(s => s.trim());

    committeeField.value = parts[0] || '';
    votumField.value = parts[1] || '';

    setEthicsChoice('yes');
}

let lastCompleteness = null;

export function computeLocalCompleteness() {
    const experimentalTypes = ['randomized-controlled-trial', 'quasi-experimental', 'case-control'];
    const sdType = document.getElementById('smSDType')?.value || '';
    const isExperimental = experimentalTypes.includes(sdType);

    const sections = {};
    let filledFields = 0;
    let totalFields = 0;

    const requiredFields = {
        Basics: new Set(['Name', 'Authors', 'Keywords', 'EthicsApprovals', 'Funding']),
        Overview: new Set(['Main']),
        StudyDesign: new Set(['Type']),
        Recruitment: new Set(['Method', 'Location', 'Period.Start', 'Period.End', 'Compensation']),
        Eligibility: new Set(['InclusionCriteria', 'ExclusionCriteria']),
        Procedure: new Set(['Overview'])
    };

    const addField = (section, name, isFilled) => {
        const isRequired = requiredFields[section]?.has(name) || false;
        if (!sections[section]) {
            sections[section] = {
                fields: [],
                filled: 0,
                total: 0,
                weight_filled: 0,
                weight_total: 0,
                required_filled: 0,
                required_total: 0,
                optional_filled: 0,
                optional_total: 0,
                read_only: section === 'SessionsTasks'
            };
        }
        sections[section].fields.push({ name, filled: isFilled, priority: 1, hint: '', required: isRequired });
        sections[section].total += 1;
        sections[section].weight_total += 1;
        if (isRequired) {
            sections[section].required_total += 1;
        } else {
            sections[section].optional_total += 1;
        }
        totalFields += 1;
        if (isFilled) {
            sections[section].filled += 1;
            sections[section].weight_filled += 1;
            if (isRequired) {
                sections[section].required_filled += 1;
            } else {
                sections[section].optional_filled += 1;
            }
            filledFields += 1;
        }
    };

    const textFilled = (value) => Boolean((value || '').trim());

    const keywordList = document.getElementById('metadataKeywords')?.value
        .split(',').map(s => s.trim()).filter(s => s) || [];

    const datasetName = (document.getElementById('metadataName')?.value || '').trim();
    addField('Basics', 'Name', datasetName.length >= 3);
    addField('Basics', 'Authors', hasAtLeastOneAuthor());
    addField('Basics', 'Description', textFilled(document.getElementById('smOverviewMain')?.value));
    addField('Basics', 'EthicsApprovals', hasValidEthicsResponse());
    addField('Basics', 'Funding', hasValidFundingResponse());
    addField('Basics', 'License', textFilled(document.getElementById('metadataLicense')?.value));
    addField('Basics', 'Keywords', keywordList.length >= 3);
    addField('Basics', 'Acknowledgements', textFilled(document.getElementById('metadataAcknowledgements')?.value));
    addField('Basics', 'DatasetDOI', textFilled(document.getElementById('metadataDOI')?.value));
    addField('Basics', 'DatasetType', textFilled(document.getElementById('metadataType')?.value));
    addField('Basics', 'HEDVersion', textFilled(document.getElementById('metadataHED')?.value));
    addField('Basics', 'HowToAcknowledge', textFilled(document.getElementById('metadataHowToAcknowledge')?.value));
    addField('Basics', 'ReferencesAndLinks', textFilled(document.getElementById('metadataReferences')?.value));

    addField('Overview', 'Main', textFilled(document.getElementById('smOverviewMain')?.value));
    addField('Overview', 'IndependentVariables', textFilled(document.getElementById('smOverviewIV')?.value));
    addField('Overview', 'DependentVariables', textFilled(document.getElementById('smOverviewDV')?.value));
    addField('Overview', 'ControlVariables', textFilled(document.getElementById('smOverviewCV')?.value));
    addField('Overview', 'QualityAssessment', textFilled(document.getElementById('smOverviewQA')?.value));

    addField('StudyDesign', 'Type', textFilled(sdType));
    addField('StudyDesign', 'ConditionType', textFilled(document.getElementById('smSDConditionType')?.value));
    addField('StudyDesign', 'TypeDescription', textFilled(document.getElementById('smSDTypeDesc')?.value));
    if (isExperimental) {
        addField('StudyDesign', 'Blinding', textFilled(document.getElementById('smSDBlinding')?.value));
        addField('StudyDesign', 'Randomization', textFilled(document.getElementById('smSDRandomization')?.value));
        addField('StudyDesign', 'ControlCondition', textFilled(document.getElementById('smSDControl')?.value));
    }

    addField('Recruitment', 'Method', hasAtLeastOneRecMethod());
    addField('Recruitment', 'Location', hasAtLeastOneRecLocation());
    addField('Recruitment', 'Period.Start', hasRecPeriodStart());
    addField('Recruitment', 'Period.End', hasRecPeriodEnd());
    addField('Recruitment', 'Compensation', textFilled(document.getElementById('smRecCompensation')?.value));

    addField('Eligibility', 'InclusionCriteria', textFilled(document.getElementById('smEligInclusion')?.value));
    addField('Eligibility', 'ExclusionCriteria', textFilled(document.getElementById('smEligExclusion')?.value));

    addField('Procedure', 'Overview', textFilled(document.getElementById('smProcOverview')?.value));

    const score = totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0;

    return {
        score,
        filled_fields: filledFields,
        total_fields: totalFields,
        sections
    };
}

export function updateCompletenessUI(completeness) {
    if (!completeness) return;
    lastCompleteness = completeness;
    const score = completeness.score || 0;

    let colorClass;
    if (score < 25) colorClass = 'bg-danger';
    else if (score < 50) colorClass = 'bg-primary';
    else if (score < 80) colorClass = 'bg-warning';
    else colorClass = 'bg-success';

    const headerBar = document.getElementById('smHeaderProgressBar');
    if (headerBar) {
        headerBar.style.width = score + '%';
        headerBar.className = 'progress-bar ' + colorClass;
    }
    const headerBadge = document.getElementById('smHeaderBadge');
    if (headerBadge) {
        headerBadge.textContent = score + '%';
        headerBadge.className = 'badge ' + colorClass;
    }

    const mainBar = document.getElementById('smMainProgressBar');
    if (mainBar) {
        mainBar.style.width = score + '%';
        mainBar.className = 'progress-bar ' + colorClass;
    }
    const mainScore = document.getElementById('smMainScore');
    if (mainScore) mainScore.textContent = score + '%';

    const dotsDiv = document.getElementById('smSectionDots');
    if (!dotsDiv) return;

    const sections = completeness.sections || {};
    const sectionOrder = [
        'Basics', 'Overview', 'StudyDesign', 'Recruitment', 'Eligibility',
        'Procedure', 'SessionsTasks'
    ];
    const sectionLabels = {
        Basics: 'Basics (BIDS)',
        Overview: 'Overview',
        StudyDesign: 'Study Design',
        Recruitment: 'Recruitment',
        Eligibility: 'Eligibility',
        Procedure: 'Procedure',
        SessionsTasks: 'Sessions & Tasks'
    };

    let html = '';
    for (const key of sectionOrder) {
        const sec = sections[key];
        if (!sec) continue;
        const reqTotal = sec.required_total || 0;
        const reqFilled = sec.required_filled || 0;
        const optTotal = sec.optional_total || 0;
        const optFilled = sec.optional_filled || 0;
        const baseTotal = reqTotal > 0 ? reqTotal : sec.total;
        const baseFilled = reqTotal > 0 ? reqFilled : sec.filled;
        const pct = baseTotal > 0 ? Math.round(baseFilled / baseTotal * 100) : 0;
        let dotClass = 'empty';
        if (pct === 100) dotClass = 'full';
        else if (pct > 0) dotClass = 'partial';

        const autoLabel = sec.read_only ? ' <span class="text-muted small">(auto)</span>' : '';
        html += `<div class="section-completeness-row">
            <span class="section-label">${sectionLabels[key] || key}${autoLabel}</span>
            <span class="completeness-dot ${dotClass}" title="${pct}%"></span>
            <span class="section-badge text-muted">Required ${reqFilled}/${reqTotal} • FAIR ${optFilled}/${optTotal}</span>
        </div>`;

        const badgeEl = document.getElementById('sm' + key + 'Badge');
        if (badgeEl) {
            const reqDone = reqTotal > 0 && reqFilled === reqTotal;
            const optDone = optTotal > 0 && optFilled === optTotal;
            const reqClass = reqDone ? 'bg-success' : 'bg-danger';
            const optClass = optDone ? 'bg-primary' : 'bg-secondary';
            badgeEl.innerHTML = `
                <span class="badge ${reqClass} bg-opacity-75">Required ${reqFilled}/${reqTotal}</span>
                <span class="badge ${optClass} bg-opacity-50">FAIR ${optFilled}/${optTotal}</span>
            `;
        }
    }
    dotsDiv.innerHTML = html;
}

const studyMetadataForm = document.getElementById('studyMetadataForm');
if (studyMetadataForm) {
    const refreshCompleteness = () => {
        updateCompletenessUI(computeLocalCompleteness());
        updateCreateProjectButton();
        scheduleLiveDescriptionValidation();
    };
    studyMetadataForm.addEventListener('input', refreshCompleteness);
    studyMetadataForm.addEventListener('change', refreshCompleteness);
}

const ethicsCommitteeInput = document.getElementById('metadataEthicsCommittee');
if (ethicsCommitteeInput) {
    ethicsCommitteeInput.addEventListener('input', () => {
        validateEthicsBadge();
        updateCreateProjectButton();
    });
}

const ethicsVotumInput = document.getElementById('metadataEthicsVotum');
if (ethicsVotumInput) {
    ethicsVotumInput.addEventListener('input', () => {
        validateEthicsBadge();
        updateCreateProjectButton();
    });
}

const createProjectForm = document.getElementById('createProjectForm');
if (createProjectForm) {
    createProjectForm.addEventListener('input', scheduleLiveDescriptionValidation);
    createProjectForm.addEventListener('change', scheduleLiveDescriptionValidation);
}

studyMetadataForm?.addEventListener('submit', async function(e) {
    e.preventDefault();

    const requiredValidation = validateAllMandatoryFields();
    if (!requiredValidation.isValid) {
        const issueCount =
            requiredValidation.emptyFields.length
            + (requiredValidation.invalidFields?.length || 0);
        showTopFeedback(
            `Fill out all required fields (${issueCount} remaining).`,
            'warning'
        );
        window.scrollTo({ top: 0, behavior: 'smooth' });
        updateCreateProjectButton();
        return;
    }

    if (!this.checkValidity()) {
        const firstInvalid = this.querySelector(':invalid');
        showTopFeedback('Please complete the required Study Metadata fields before saving.', 'warning');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        if (typeof this.reportValidity === 'function') {
            this.reportValidity();
        }
        if (firstInvalid && firstInvalid.scrollIntoView) {
            firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }

    const periodError = getRecPeriodRangeError();
    if (periodError) {
        showToast(periodError, 'danger');
        showTopFeedback(periodError, 'danger');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
    }

    const btn = this.querySelector('button[type="submit"]')
        || document.getElementById('createProjectSubmitBtn');
    const originalText = btn ? setButtonLoading(btn, true, 'Saving...') : null;

    try {
        const payload = {
            Overview: {
                Main: document.getElementById('smOverviewMain').value || undefined,
                IndependentVariables: document.getElementById('smOverviewIV').value || undefined,
                DependentVariables: document.getElementById('smOverviewDV').value || undefined,
                ControlVariables: document.getElementById('smOverviewCV').value || undefined,
                QualityAssessment: document.getElementById('smOverviewQA').value || undefined,
            },
            StudyDesign: {
                Type: document.getElementById('smSDType').value || undefined,
                TypeDescription: document.getElementById('smSDTypeDesc').value || undefined,
                Blinding: document.getElementById('smSDBlinding').value || undefined,
                Randomization: document.getElementById('smSDRandomization').value || undefined,
                ControlCondition: document.getElementById('smSDControl').value || undefined,
            },
            Conditions: {
                Type: document.getElementById('smSDConditionType').value || undefined,
            },
            Recruitment: {
                Method: (function() {
                    const list = getRecMethodList();
                    if (!list.length) return undefined;
                    return list.join('; ');
                })(),
                Location: (function() {
                    const list = getRecLocationList();
                    if (!list.length) return undefined;
                    return list.join('; ');
                })(),
                Period: {
                    Start: getYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth') || undefined,
                    End: getYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth') || undefined,
                },
                Compensation: document.getElementById('smRecCompensation').value || undefined,
            },
            Eligibility: {
                InclusionCriteria: _textToArray(document.getElementById('smEligInclusion').value) || undefined,
                ExclusionCriteria: _textToArray(document.getElementById('smEligExclusion').value) || undefined,
                TargetSampleSize: parseInt(document.getElementById('smEligSampleSize').value) || undefined,
                PowerAnalysis: document.getElementById('smEligPower').value || undefined,
            },
            Procedure: {
                Overview: document.getElementById('smProcOverview').value || undefined,
                InformedConsent: document.getElementById('smProcConsent').value || undefined,
                QualityControl: _textToArray(document.getElementById('smProcQC').value) || undefined,
                MissingDataHandling: document.getElementById('smProcMissing').value || undefined,
                Debriefing: document.getElementById('smProcDebriefing').value || undefined,
                AdditionalData: document.getElementById('smProcAdditionalData').value || undefined,
                Notes: document.getElementById('smProcNotes').value || undefined,
            },
            MissingData: {
                Description: document.getElementById('smMissingDesc').value || undefined,
                MissingFiles: document.getElementById('smMissingFiles').value || undefined,
                KnownIssues: document.getElementById('smKnownIssues').value || undefined,
            },
            References: document.getElementById('smReferences').value || undefined,
        };

        function cleanUndefined(obj) {
            if (Array.isArray(obj)) return obj.length > 0 ? obj : undefined;
            if (obj && typeof obj === 'object') {
                const cleaned = {};
                for (const [k, v] of Object.entries(obj)) {
                    const cv = cleanUndefined(v);
                    if (cv !== undefined) cleaned[k] = cv;
                }
                return Object.keys(cleaned).length > 0 ? cleaned : undefined;
            }
            return obj;
        }

        const cleanPayload = {};
        for (const [k, v] of Object.entries(payload)) {
            const cv = cleanUndefined(v);
            cleanPayload[k] = cv || {};
        }

        const response = await fetch('/api/projects/study-metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cleanPayload)
        });

        const result = await response.json();
        if (result.success) {
            // Show visual success feedback on button
            if (btn) {
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Saved Successfully!';
                btn.classList.add('btn-success');
                btn.classList.remove('btn-info');
                btn.disabled = false;
            }

            // Show toast and top feedback
            showToast('Study metadata saved successfully', 'success');
            showTopFeedback('Study metadata saved successfully.', 'success');

            // Always scroll to top and briefly highlight stats grid
            window.scrollTo({ top: 0, behavior: 'smooth' });
            const statsGrid = document.querySelector('.stats-grid');
            if (statsGrid) {
                statsGrid.classList.add('highlight-success');
                setTimeout(() => statsGrid.classList.remove('highlight-success'), 1200);
            }

            if (result.completeness) {
                updateCompletenessUI(result.completeness);
            }
            await saveDatasetDescription();
            showToast('Dataset description saved', 'success');
            // Generate README silently in background (don't break save flow on error)
            generateReadmeSilent().catch(err => {
                console.error('README generation failed:', err);
                // Silently fail - save was already successful
            });

            // Reset button to original state after 2 seconds
            setTimeout(() => {
                if (!btn) return;
                setButtonLoading(btn, false, null, originalText);
                btn.classList.remove('btn-success');
                btn.classList.add('btn-info');
            }, 2000);
        } else {
            showToast('Failed to save: ' + result.error, 'danger');
            showTopFeedback('Failed to save study metadata: ' + (result.error || 'Unknown error'), 'danger');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'danger');
        showTopFeedback('Error while saving study metadata: ' + error.message, 'danger');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
        if (btn) {
            setButtonLoading(btn, false, null, originalText);
        }
    }
});

// ===== GENERATE METHODS SECTION =====

export function showMethodsCard() {
    const card = document.getElementById('methodsSectionCard');
    if (!card) return;
    card.style.display = window.currentProjectPath ? 'block' : 'none';
}

let _methodsMd = '';
let _methodsHtml = '';
let _methodsFilenameBase = 'methods_section_en';

export async function generateMethodsSection() {
    const btn = document.getElementById('generateMethodsBtn');
    const originalText = setButtonLoading(btn, true, 'Generating...');

    const resultDiv = document.getElementById('methodsResult');
    const errorDiv = document.getElementById('methodsError');
    resultDiv.style.display = 'none';
    errorDiv.style.display = 'none';

    const lang = document.getElementById('methodsLanguage').value;
    const detailLevel = document.getElementById('methodsDetailLevel').value;
    const continuous = document.getElementById('methodsContinuous').checked;

    try {
        const response = await fetch('/api/projects/generate-methods', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: lang, detail_level: detailLevel, continuous: continuous })
        });
        const data = await response.json();

        if (!data.success) {
            errorDiv.style.display = 'block';
            errorDiv.innerHTML = `
                <div class="alert alert-warning py-2">
                    <i class="fas fa-info-circle me-2"></i>${data.error}
                </div>`;
            return;
        }

        _methodsMd = data.md;
        _methodsHtml = data.html;
        _methodsFilenameBase = data.filename_base;

        const badgesDiv = document.getElementById('methodsSectionsBadges');
        badgesDiv.innerHTML = (data.sections_used || []).map(
            s => `<span class="badge bg-success bg-opacity-75 me-1">${s}</span>`
        ).join('');

        const parser = new DOMParser();
        const doc = parser.parseFromString(data.html, 'text/html');
        document.getElementById('methodsPreview').innerHTML = doc.body.innerHTML;
        resultDiv.style.display = 'block';
    } catch (error) {
        errorDiv.style.display = 'block';
        errorDiv.innerHTML = `
            <div class="alert alert-danger py-2">
                <i class="fas fa-exclamation-circle me-2"></i>${error.message}
            </div>`;
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

export function downloadMethods(format) {
    const content = format === 'md' ? _methodsMd : _methodsHtml;
    const mimeType = format === 'md' ? 'text/markdown' : 'text/html';
    const ext = format === 'md' ? '.md' : '.html';
    const blob = new Blob([content], { type: mimeType + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = _methodsFilenameBase + ext;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// ===== README GENERATION =====

/**
 * Generate README silently without confirmation (for auto-generation during save)
 * @private
 */
async function generateReadmeSilent() {
    if (!window.currentProjectPath) {
        return;
    }

    try {
        const response = await fetch('/api/projects/generate-readme', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            console.log('README.md generated in background');
            // Optionally show subtle notification
            showToast('README.md auto-generated', 'success');
        } else {
            console.warn('README generation failed:', data.error);
        }
    } catch (error) {
        console.error('README generation error:', error);
        // Don't show error to avoid cluttering the save success feedback
    }
}

/**
 * Generate README with user confirmation (for manual generation)
 */
export async function generateReadme() {
    if (!window.currentProjectPath) {
        showToast('No project selected', 'warning');
        return;
    }

    if (!confirm('Generate README.md from study metadata?\n\nThis will overwrite any existing README.md file.')) {
        return;
    }

    try {
        const response = await fetch('/api/projects/generate-readme', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            showToast('README.md generated successfully! Check your project folder.', 'success');
        } else {
            showToast(`Failed to generate README: ${data.error}`, 'danger');
        }
    } catch (error) {
        showToast(`Error: ${error.message}`, 'danger');
    }
}

// ===== INIT =====

document.addEventListener('DOMContentLoaded', function() {
    if (!document.querySelector('#metadataAuthorsList .author-row')) {
        addAuthorRow();
    }
    if (!document.querySelector('#smRecLocationList .rec-location-row')) {
        addRecLocationRow();
    }
    toggleRecLocationInputs();
    initYearMonthSelect('smRecPeriodStartYear', 'smRecPeriodStartMonth');
    initYearMonthSelect('smRecPeriodEndYear', 'smRecPeriodEndMonth');
    updateCreateProjectButton();

    const datasetTypeSelect = document.getElementById('metadataType');
    if (datasetTypeSelect) {
        datasetTypeSelect.value = '';
    }

    const studyDesignTypeSelect = document.getElementById('smSDType');
    if (studyDesignTypeSelect) {
        studyDesignTypeSelect.addEventListener('change', toggleExperimentalFields);
    }

    const ethicsYesBtn = document.getElementById('metadataEthicsYes');
    if (ethicsYesBtn) {
        ethicsYesBtn.addEventListener('click', () => setEthicsChoice('yes'));
    }

    const ethicsNoBtn = document.getElementById('metadataEthicsNo');
    if (ethicsNoBtn) {
        ethicsNoBtn.addEventListener('click', () => setEthicsChoice('no'));
    }

    const fundingYesBtn = document.getElementById('metadataFundingYes');
    if (fundingYesBtn) {
        fundingYesBtn.addEventListener('click', () => setFundingChoice('yes'));
    }

    const fundingNoBtn = document.getElementById('metadataFundingNo');
    if (fundingNoBtn) {
        fundingNoBtn.addEventListener('click', () => setFundingChoice('no'));
    }

    const generateMethodsBtn = document.getElementById('generateMethodsBtn');
    if (generateMethodsBtn) {
        generateMethodsBtn.addEventListener('click', () => {
            generateMethodsSection();
        });
    }

    const downloadMethodsMdBtn = document.getElementById('downloadMethodsMdBtn');
    if (downloadMethodsMdBtn) {
        downloadMethodsMdBtn.addEventListener('click', () => {
            downloadMethods('md');
        });
    }

    const downloadMethodsHtmlBtn = document.getElementById('downloadMethodsHtmlBtn');
    if (downloadMethodsHtmlBtn) {
        downloadMethodsHtmlBtn.addEventListener('click', () => {
            downloadMethods('html');
        });
    }

    setEthicsChoice(document.getElementById('metadataEthicsApproved')?.value || '');
    setFundingChoice(document.getElementById('metadataFundingDeclared')?.value || '');
    
    // Initial badge validation
    setTimeout(() => {
        validateAuthorsBadge();
        validateRecLocationBadge();
        validateEthicsBadge();
        validateFundingBadge();
    }, 200);
});

// Expose key functions for inline handlers and legacy code
window.addAuthorRow = addAuthorRow;
window.getAuthorsList = getAuthorsList;
window.setAuthorsList = setAuthorsList;
window.addRecLocationRow = addRecLocationRow;
window.getRecLocationList = getRecLocationList;
window.setRecLocationList = setRecLocationList;
window.getRecMethodList = getRecMethodList;
window.setRecMethodList = setRecMethodList;
window.getYearMonthValue = getYearMonthValue;
window.setYearMonthValue = setYearMonthValue;
window.validateAllMandatoryFields = validateAllMandatoryFields;
window.validateDatasetDescriptionDraftLive = validateDatasetDescriptionDraftLive;
window.showStudyMetadataCard = showStudyMetadataCard;
window.resetStudyMetadataForm = resetStudyMetadataForm;
window.showMethodsCard = showMethodsCard;
window.generateMethodsSection = generateMethodsSection;
window.downloadMethods = downloadMethods;
window.toggleExperimentalFields = toggleExperimentalFields;
window.toggleEthicsFields = toggleEthicsFields;
window.setEthicsChoice = setEthicsChoice;
window.getEthicsApprovals = getEthicsApprovals;
window.setEthicsApprovals = setEthicsApprovals;
window.toggleFundingFields = toggleFundingFields;
window.setFundingChoice = setFundingChoice;
window.getFundingList = getFundingList;
window.validateAuthorsBadge = validateAuthorsBadge;
window.validateRecLocationBadge = validateRecLocationBadge;
window.toggleRecLocationInputs = toggleRecLocationInputs;
