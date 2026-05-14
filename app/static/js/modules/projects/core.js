/**
 * Projects Module - Core
 * Main project management logic: create, open, load, validate projects
 */

import { setButtonLoading, textToArray as _textToArray } from './helpers.js';
import { initCreateProjectController } from './create-project.js';
import { initProjectInitOnBidsController } from './init-on-bids.js';
import { initOpenProjectController } from './open-project.js';
import { initProjectPathPickers } from './path-pickers.js';
import { validateProjectField } from './validation.js';
import { initProjectFileBrowser } from './file-browser.js';
import {
    hasUnsavedStudyMetadataChanges,
    isStudyMetadataBusy,
    validateAllMandatoryFields,
    validateDatasetDescriptionDraftLive,
    getCitationAuthorsList,
    getEthicsApprovals,
    getFundingList,
    getRecMethodList,
    getRecLocationList,
    getYearMonthValue,
    resetStudyMetadataForm,
    saveProjectSchemaConfig,
    showStudyMetadataCard,
    showMethodsCard,
    updateCreateProjectButton
} from './metadata.js';
import { showExportCard } from './export.js';
import {
    getProjectStateSnapshot,
    setProjectStateSnapshot,
} from '../../shared/project-state.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { escapeHtml } from '../../shared/dom.js';
import { prefersServerPicker } from '../../shared/path-picker.js';

// Global state
let currentProjectPath = '';
let currentProjectName = '';
let currentProjectIcon = '';
let projectsPageInitialized = false;
const recentProjectsKey = 'prism_recent_projects';
const beginnerHelpModeKey = 'prism_beginner_help_mode';
const recentProjectStatusCache = new Map();
let createTargetStatusRequestToken = 0;
let createTargetStatusDebounceTimer = null;

const allowedProjectIcons = [
    '🧪',
    '🔬',
    '🧬',
    '🧠',
    '⚗️',
    '🩺',
    '📊',
    '🧫',
    '🔭',
    '🧲',
];

function normalizeProjectIconClass(iconClass) {
    const icon = String(iconClass || '').trim();
    if (!icon) return '';
    return allowedProjectIcons.includes(icon) ? icon : '';
}

function resolveProjectIconClass(iconClass) {
    return normalizeProjectIconClass(iconClass) || '🧪';
}

function setCreateResultHtml(html, scope = 'server') {
    const resultDiv = document.getElementById('createResult');
    if (!resultDiv) return;

    resultDiv.dataset.scope = scope;
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = html;
}

function clearCreateResult(scope = null) {
    const resultDiv = document.getElementById('createResult');
    if (!resultDiv) return;
    if (scope && resultDiv.dataset.scope !== scope) return;

    resultDiv.style.display = 'none';
    resultDiv.innerHTML = '';
    delete resultDiv.dataset.scope;
}

function joinProjectTargetPath(projectPath, projectName) {
    const parentPath = String(projectPath || '').trim();
    const name = String(projectName || '').trim();
    if (!parentPath || !name) return '';

    if (parentPath.endsWith('/') || parentPath.endsWith('\\')) {
        return parentPath + name;
    }

    const separator = parentPath.includes('/') ? '/' : '\\';
    return parentPath + separator + name;
}

function resetCreateTargetStatusChecks() {
    if (createTargetStatusDebounceTimer) {
        window.clearTimeout(createTargetStatusDebounceTimer);
        createTargetStatusDebounceTimer = null;
    }
    createTargetStatusRequestToken += 1;
}

function setGlobalProjectState(path, name, icon = '') {
    setProjectStateSnapshot(path, name, icon);
}

function shouldHideProjectTypeSelectionWhenLoaded() {
    if (!projectsRoot) {
        return false;
    }

    return String(projectsRoot.dataset.hideProjectOptionsOnLoaded || '').trim().toLowerCase() === 'true';
}

function updateProjectTypeSelectionVisibility() {
    const projectTypeSelectionRow = document.getElementById('projectTypeSelectionRow');
    const openProjectFlowStrip = document.getElementById('openProjectFlowStrip');
    if (!projectTypeSelectionRow) {
        if (!openProjectFlowStrip) {
            return;
        }
    }

    const shouldHide = shouldHideProjectTypeSelectionWhenLoaded() && Boolean(String(currentProjectPath || '').trim());
    projectTypeSelectionRow?.classList.toggle('d-none', shouldHide);
    openProjectFlowStrip?.classList.toggle('d-none', shouldHide);
}

function applyCurrentProject(project) {
    currentProjectPath = (project && project.path) ? String(project.path).trim() : '';
    currentProjectName = (project && project.name) ? String(project.name).trim() : '';
    const incomingIcon = normalizeProjectIconClass(project && project.icon);
    currentProjectIcon = currentProjectPath
        ? resolveProjectIconClass(incomingIcon || currentProjectIcon)
        : '';

    const existingPathInput = document.getElementById('existingPath');
    if (existingPathInput && currentProjectPath) {
        existingPathInput.value = currentProjectPath;
    }

    updateProjectTypeSelectionVisibility();
    updateQuickValidateButtonState();

    if (window.updateNavbarProject) {
        window.updateNavbarProject(currentProjectName, currentProjectPath, currentProjectIcon);
        return;
    }

    setGlobalProjectState(currentProjectPath, currentProjectName, currentProjectIcon);
}

function requestStudyMetadataSaveFromProjectBox(submitIntent = 'standard') {
    const studyMetadataForm = document.getElementById('studyMetadataForm');
    if (!studyMetadataForm) return;

    const primarySubmitButton = document.getElementById('createProjectSubmitBtn');
    studyMetadataForm.dataset.submitIntent = submitIntent;
    const active = document.activeElement;
    if (active instanceof HTMLElement && studyMetadataForm.contains(active) && typeof active.blur === 'function') {
        active.blur();
    }

    window.requestAnimationFrame(() => {
        if (typeof studyMetadataForm.requestSubmit === 'function' && primarySubmitButton) {
            studyMetadataForm.requestSubmit(primarySubmitButton);
            return;
        }
        studyMetadataForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });
}

function bindProjectBoxActionButtons() {
    const actionButtons = [
        document.getElementById('projectBoxSaveBtn'),
        document.getElementById('projectBoxPreliminarySaveBtn')
    ].filter(Boolean);

    if (!actionButtons.length) {
        return;
    }

    actionButtons.forEach(button => {
        if (button.dataset.bound === '1') {
            return;
        }
        button.dataset.bound = '1';

        // Mirror the primary save button behavior so first pointer interaction
        // cannot be consumed by blur/change processing before submit is issued.
        button.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) {
                return;
            }
            event.preventDefault();
            button.dataset.pointerTriggeredSubmit = '1';
            requestStudyMetadataSaveFromProjectBox(
                button.id === 'projectBoxPreliminarySaveBtn' ? 'preliminary' : 'standard'
            );
        });

        button.addEventListener('click', (event) => {
            event.preventDefault();

            if (button.dataset.pointerTriggeredSubmit === '1') {
                button.dataset.pointerTriggeredSubmit = '0';
                return;
            }

            requestStudyMetadataSaveFromProjectBox(
                button.id === 'projectBoxPreliminarySaveBtn' ? 'preliminary' : 'standard'
            );
        });
    });
}

function syncRecentProjectsToServer(list) {
    fetchWithApiFallback('/api/projects/recent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projects: list })
    }).catch(() => {
        // localStorage remains fallback source
    });
}

function loadRecentProjectsFromServer() {
    fetchWithApiFallback('/api/projects/recent')
        .then(response => response.json())
        .then(data => {
            if (!data || !data.success || !Array.isArray(data.projects)) return;
            localStorage.setItem(recentProjectsKey, JSON.stringify(data.projects.slice(0, 5)));
            renderRecentProjects();
        })
        .catch(() => {
            // keep local fallback
        });
}

const projectsRoot = document.getElementById('projectsRoot');
const globalProjectState = getProjectStateSnapshot();
const globalProjectPath = globalProjectState.path;
const globalProjectName = globalProjectState.name;
const globalProjectIcon = normalizeProjectIconClass(globalProjectState.icon);

if (projectsRoot) {
    currentProjectPath = projectsRoot.dataset.currentProjectPath || globalProjectPath || '';
    currentProjectName = projectsRoot.dataset.currentProjectName || globalProjectName || '';
    currentProjectIcon = currentProjectPath
        ? resolveProjectIconClass(projectsRoot.dataset.currentProjectIcon || globalProjectIcon)
        : '';
} else {
    currentProjectPath = globalProjectPath;
    currentProjectName = globalProjectName;
    currentProjectIcon = currentProjectPath ? resolveProjectIconClass(globalProjectIcon) : '';
}

setGlobalProjectState(currentProjectPath, currentProjectName, currentProjectIcon);
updateProjectTypeSelectionVisibility();

window.addEventListener('prism-project-changed', function(event) {
    const eventState = event && event.detail ? event.detail : null;
    const fallbackState = getProjectStateSnapshot();
    const nextPath = eventState && typeof eventState.path === 'string' ? eventState.path.trim() : fallbackState.path;
    const nextName = eventState && typeof eventState.name === 'string' ? eventState.name.trim() : fallbackState.name;
    const nextIcon = eventState && typeof eventState.icon === 'string'
        ? eventState.icon.trim()
        : String(fallbackState.icon || '').trim();

    currentProjectPath = nextPath;
    currentProjectName = nextName;
    currentProjectIcon = nextPath ? resolveProjectIconClass(nextIcon || currentProjectIcon) : '';
    updateProjectTypeSelectionVisibility();
    updateQuickValidateButtonState();
});

function normalizeRecentProjectEntry(entry) {
    if (!entry || typeof entry !== 'object') return null;

    const path = String(entry.path || '').trim();
    if (!path) return null;

    const name = String(entry.name || '').trim() || path.split(/[\\/]/).pop() || path;
    const icon = resolveProjectIconClass(entry.icon);

    return { path, name, icon };
}

export function getRecentProjects() {
    try {
        const raw = localStorage.getItem(recentProjectsKey);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed
            .map(normalizeRecentProjectEntry)
            .filter(Boolean);
    } catch (err) {
        console.warn('Could not read recent projects', err);
        return [];
    }
}

export function saveRecentProjects(list) {
    const limited = (Array.isArray(list) ? list : [])
        .map(normalizeRecentProjectEntry)
        .filter(Boolean)
        .slice(0, 5);
    try {
        localStorage.setItem(recentProjectsKey, JSON.stringify(limited));
    } catch (err) {
        console.warn('Could not save recent projects', err);
    }
    syncRecentProjectsToServer(limited);
}

export function addRecentProject(name, path, icon = '') {
    if (!path) return;
    const safeName = name && name.trim() ? name.trim() : path.split(/[\\/]/).pop();
    const safeIcon = resolveProjectIconClass(icon || currentProjectIcon);
    const list = getRecentProjects().filter(p => p.path !== path);
    list.unshift({ name: safeName, path: path, icon: safeIcon });
    recentProjectStatusCache.delete(path);
    saveRecentProjects(list);
    renderRecentProjects();
}

function normalizeValidationRecord(record, fallbackCode, defaultMessage) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) {
        const message = String(record || '').trim();
        return {
            code: fallbackCode,
            message: message || defaultMessage,
            filePath: '',
            fixHint: '',
            fixable: false,
        };
    }

    const code = String(record.code || '').trim() || fallbackCode;
    const message = String(record.message || '').trim() || defaultMessage;
    const filePath = String(record.file_path || record.file || '').trim();
    const fixHint = String(record.fix_hint || '').trim();

    return {
        code,
        message,
        filePath,
        fixHint,
        fixable: Boolean(record.fixable),
    };
}

function groupValidationRecordsByCode(records, {
    fallbackCode = 'WARNING',
    defaultMessage = 'Validation issue',
} = {}) {
    const groupsByCode = new Map();

    (Array.isArray(records) ? records : []).forEach((record) => {
        const normalized = normalizeValidationRecord(record, fallbackCode, defaultMessage);
        const code = normalized.code;

        if (!groupsByCode.has(code)) {
            groupsByCode.set(code, {
                code,
                count: 0,
                hasFixable: false,
                fixHints: [],
                messagesByText: new Map(),
            });
        }

        const group = groupsByCode.get(code);
        group.count += 1;
        group.hasFixable = group.hasFixable || normalized.fixable;

        if (normalized.fixHint && !group.fixHints.includes(normalized.fixHint)) {
            group.fixHints.push(normalized.fixHint);
        }

        const messageKey = normalized.message;
        if (!group.messagesByText.has(messageKey)) {
            group.messagesByText.set(messageKey, {
                message: normalized.message,
                occurrenceCount: 0,
                files: [],
            });
        }

        const messageGroup = group.messagesByText.get(messageKey);
        messageGroup.occurrenceCount += 1;
        if (normalized.filePath && !messageGroup.files.includes(normalized.filePath)) {
            messageGroup.files.push(normalized.filePath);
        }
    });

    return Array.from(groupsByCode.values())
        .map((group) => ({
            code: group.code,
            count: group.count,
            hasFixable: group.hasFixable,
            fixHints: group.fixHints,
            messages: Array.from(group.messagesByText.values()).sort((a, b) => (
                b.occurrenceCount - a.occurrenceCount || a.message.localeCompare(b.message)
            )),
        }))
        .sort((a, b) => (b.count - a.count || a.code.localeCompare(b.code)));
}

function getProjectValidationAction(code) {
    const normalizedCode = String(code || '').trim().toUpperCase();

    if (normalizedCode === 'PRISM707') {
        return {
            href: '/converter?tab=participants',
            label: 'Open Sociodemographics',
            iconClass: 'fas fa-users',
        };
    }

    return null;
}

function renderGroupedValidationHint(fixHints, label = 'Hint') {
    if (!Array.isArray(fixHints) || fixHints.length === 0) {
        return '';
    }

    const extraHintCount = Math.max(0, fixHints.length - 1);
    return `
        <div class="alert alert-info py-1 px-2 mb-2 smaller d-flex align-items-start">
            <i class="fas fa-lightbulb me-2 text-warning mt-1"></i>
            <div>
                <strong>${escapeHtml(label)}:</strong> ${escapeHtml(fixHints[0])}
                ${extraHintCount > 0 ? `<div class="x-small text-muted mt-1">+${extraHintCount} additional hint(s) in this code group.</div>` : ''}
            </div>
        </div>
    `;
}

function renderGroupedValidationMessages(messageGroups) {
    if (!Array.isArray(messageGroups) || messageGroups.length === 0) {
        return '';
    }

    return messageGroups.map((messageGroup, index) => {
        const visibleFiles = messageGroup.files.slice(0, 3);
        const hiddenFilesCount = Math.max(0, messageGroup.files.length - visibleFiles.length);
        const dividerClass = index < messageGroups.length - 1 ? 'border-bottom pb-2 mb-2' : '';
        const repeatBadge = messageGroup.occurrenceCount > 1
            ? `<span class="badge bg-light text-muted border ms-2 project-group-count-badge">${messageGroup.occurrenceCount}</span>`
            : '';
        const filesHtml = visibleFiles.map((filePath) => `
            <div class="d-flex align-items-start mb-1">
                <i class="fas fa-file text-muted me-2 x-small mt-1"></i>
                <span class="text-muted x-small text-break">${escapeHtml(filePath)}</span>
            </div>
        `).join('');

        return `
            <div class="project-group-message ${dividerClass}">
                <div class="small fw-semibold text-dark d-flex align-items-center flex-wrap">
                    <span>${escapeHtml(messageGroup.message)}</span>
                    ${repeatBadge}
                </div>
                ${filesHtml ? `<div class="project-group-files">${filesHtml}</div>` : ''}
                ${hiddenFilesCount > 0 ? `<div class="text-muted x-small mt-1"><i class="fas fa-ellipsis-h me-1"></i>and ${hiddenFilesCount} more file(s)</div>` : ''}
            </div>
        `;
    }).join('');
}

function setCurrentProjectBannerVisibility(type) {
    const banner = document.getElementById('currentProjectBanner');
    if (!banner) return;
    banner.style.display = (type === 'create') ? 'none' : '';
}

function clearRecentProjects() {
    recentProjectStatusCache.clear();
    saveRecentProjects([]);
    renderRecentProjects();
}

function normalizeHintText(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
}

function getExistingFieldHelpTexts(field) {
    const container = field.closest('.form-check, [class*="col-"], .mb-3, .card-body') || field.parentElement;
    if (!container) return [];

    const texts = [];
    const nodes = container.querySelectorAll('small.text-muted, .form-text, small');
    nodes.forEach(node => {
        if (node.classList.contains('field-hint-inline')) return;
        const text = normalizeHintText(node.textContent);
        if (text) texts.push(text);
    });

    return texts;
}

function isHintDuplicate(hintText, existingTexts) {
    const normalizedHint = normalizeHintText(hintText).toLowerCase();
    if (!normalizedHint) return true;

    return existingTexts.some(existing => {
        const normalizedExisting = normalizeHintText(existing).toLowerCase();
        if (!normalizedExisting) return false;
        return normalizedExisting === normalizedHint
            || normalizedExisting.includes(normalizedHint)
            || normalizedHint.includes(normalizedExisting);
    });
}

function isFieldEffectivelyEmpty(field) {
    if (field.type === 'checkbox' || field.type === 'radio') {
        return !field.checked;
    }
    if (field.tagName === 'SELECT' && field.multiple) {
        return Array.from(field.selectedOptions || []).length === 0;
    }
    return !String(field.value || '').trim();
}

function shouldShowBeginnerHint(field) {
    const isFocused = document.activeElement === field;
    const isInvalid = field.matches(':invalid') || field.classList.contains('is-invalid');
    return isFocused || isInvalid || isFieldEffectivelyEmpty(field);
}

function getFieldHintText(field) {
    const parts = [];

    const placeholder = normalizeHintText(field.getAttribute('placeholder'));
    if (placeholder) {
        parts.push(`Example: ${placeholder}`);
    }

    if (parts.length > 0) {
        return parts[0];
    }

    if (field.tagName === 'SELECT') {
        return 'Choose the option that best matches your study.';
    }
    if (field.type === 'checkbox' || field.type === 'radio') {
        return 'Enable this option if it applies to your project.';
    }
    return 'Fill out this field based on your study.';
}

function addHintIconToLabel(label, hintText) {
    if (!label || !hintText) return;
    if (label.querySelector('.field-hint-trigger')) return;

    const existingTooltipIcon = label.querySelector('[data-bs-toggle="tooltip"]');
    if (existingTooltipIcon) return;

    const hintButton = document.createElement('button');
    hintButton.type = 'button';
    hintButton.className = 'btn btn-link p-0 ms-1 align-baseline text-muted field-hint-trigger';
    hintButton.setAttribute('data-bs-toggle', 'tooltip');
    hintButton.setAttribute('data-bs-placement', 'top');
    hintButton.setAttribute('data-bs-title', hintText);
    hintButton.setAttribute('aria-label', 'Show field guidance');
    hintButton.innerHTML = '<i class="fas fa-info-circle"></i>';

    label.appendChild(hintButton);

    if (window.bootstrap?.Tooltip) {
        window.bootstrap.Tooltip.getOrCreateInstance(hintButton);
    }
}

function clearInlineFieldHints() {
    document.querySelectorAll('.field-hint-inline').forEach(node => node.remove());
}

function getBeginnerHelpModeEnabled() {
    try {
        const value = localStorage.getItem(beginnerHelpModeKey);
        if (value === null) return true;
        return value === '1';
    } catch (_) {
        return true;
    }
}

function setBeginnerHelpModeEnabled(enabled) {
    try {
        localStorage.setItem(beginnerHelpModeKey, enabled ? '1' : '0');
    } catch (_) {
        // ignore storage failures
    }
}

function renderInlineFieldHints() {
    clearInlineFieldHints();

    const formIds = [
        'createProjectForm',
        'openProjectForm',
        'studyMetadataForm',
        'globalSettingsForm',
        'exportProjectForm'
    ];

    formIds.forEach(formId => {
        const form = document.getElementById(formId);
        if (!form) return;

        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            if (!field.id || field.type === 'hidden') return;
            if (!shouldShowBeginnerHint(field)) return;

            const hintText = getFieldHintText(field);
            if (!hintText) return;

            const existingHelpTexts = getExistingFieldHelpTexts(field);
            if (isHintDuplicate(hintText, existingHelpTexts)) return;

            const fieldGroup = field.closest('.form-check, .input-group, [class*="col-"]') || field.parentElement;
            if (!fieldGroup) return;

            if (fieldGroup.querySelector(`.field-hint-inline[data-for="${field.id}"]`)) {
                return;
            }

            const hint = document.createElement('div');
            hint.className = 'field-hint-inline form-text text-muted';
            hint.setAttribute('data-for', field.id);
            hint.innerHTML = `<i class="fas fa-info-circle me-1"></i>${escapeHtml(hintText)}`;

            if (fieldGroup.classList.contains('input-group')) {
                fieldGroup.insertAdjacentElement('afterend', hint);
            } else {
                fieldGroup.appendChild(hint);
            }
        });
    });
}

let beginnerHintRefreshBound = false;

function bindBeginnerHintRefreshEvents() {
    if (beginnerHintRefreshBound) return;

    const refreshIfEnabled = () => {
        if (!getBeginnerHelpModeEnabled()) return;
        renderInlineFieldHints();
    };

    ['focusin', 'focusout', 'input', 'change'].forEach(eventName => {
        document.addEventListener(eventName, (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            if (!target.closest('#createProjectForm, #openProjectForm, #studyMetadataForm, #globalSettingsForm, #exportProjectForm')) return;
            if (!target.matches('input, select, textarea')) return;
            refreshIfEnabled();
        });
    });

    beginnerHintRefreshBound = true;
}

function applyBeginnerHelpMode(enabled) {
    if (enabled) {
        renderInlineFieldHints();
    } else {
        clearInlineFieldHints();
    }
}

function initBeginnerHelpMode() {
    if (window.prismGlobalBeginnerHintsManaged === true) {
        return;
    }

    const toggle = document.getElementById('beginnerHelpModeToggle');
    const enabled = getBeginnerHelpModeEnabled();

    if (toggle) {
        toggle.checked = enabled;
        toggle.addEventListener('change', () => {
            const modeEnabled = Boolean(toggle.checked);
            setBeginnerHelpModeEnabled(modeEnabled);
            applyBeginnerHelpMode(modeEnabled);
        });
    }

    window.addEventListener('prism-beginner-help-changed', (event) => {
        const modeEnabled = Boolean(event?.detail?.enabled);
        if (toggle) {
            toggle.checked = modeEnabled;
        }
        setBeginnerHelpModeEnabled(modeEnabled);
        applyBeginnerHelpMode(modeEnabled);
    });

    applyBeginnerHelpMode(enabled);
    bindBeginnerHintRefreshEvents();
}

function initProjectFieldHints() {
    const formIds = [
        'createProjectForm',
        'openProjectForm',
        'studyMetadataForm',
        'globalSettingsForm',
        'exportProjectForm'
    ];

    formIds.forEach(formId => {
        const form = document.getElementById(formId);
        if (!form) return;

        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            if (!field.id || field.type === 'hidden') return;

            let label = form.querySelector(`label[for="${field.id}"]`);
            if (!label) {
                label = field.closest('.form-check')?.querySelector('.form-check-label') || null;
            }
            if (!label) return;

            const hintText = getFieldHintText(field);
            addHintIconToLabel(label, hintText);
        });
    });
}

async function isRecentProjectAvailable(path) {
    if (!path) return false;
    if (recentProjectStatusCache.has(path)) {
        return recentProjectStatusCache.get(path);
    }

    const statusPromise = fetchWithApiFallback('/api/projects/path-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    })
        .then(response => response.json().catch(() => null))
        .then(data => {
            if (!data || data.success !== true) {
                return null;
            }
            return Boolean(data.available);
        })
        .catch(() => null);

    recentProjectStatusCache.set(path, statusPromise);
    return statusPromise;
}

async function checkCreateTargetStatus() {
    const projectName = document.getElementById('projectName')?.value.trim() || '';
    const projectPath = document.getElementById('projectPath')?.value.trim() || '';
    const validProjectName = /^[a-zA-Z0-9_-]+$/.test(projectName);

    if (!projectName || !projectPath || !validProjectName) {
        clearCreateResult('preflight');
        return { conflict: false };
    }

    const targetPath = joinProjectTargetPath(projectPath, projectName);
    const requestToken = ++createTargetStatusRequestToken;

    try {
        const response = await fetchWithApiFallback('/api/projects/path-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: targetPath })
        });
        const status = await response.json().catch(() => null);

        if (requestToken !== createTargetStatusRequestToken) {
            return { conflict: false, stale: true };
        }

        if (!status || status.success !== true || status.exists !== true) {
            clearCreateResult('preflight');
            return { conflict: false, targetPath };
        }

        if (status.is_dir && status.is_empty_dir) {
            clearCreateResult('preflight');
            return { conflict: false, targetPath, status };
        }

        let title = 'Target Folder Already Exists';
        let message = `The target folder <code>${escapeHtml(targetPath)}</code> already exists and contains files. Project Location must be the parent folder where PRISM creates a new project folder.`;

        if (status.is_file) {
            title = 'Target Path Is A File';
            message = `The target path <code>${escapeHtml(targetPath)}</code> already exists as a file. Project Location must be the parent folder, not the final project path.`;
        } else if (status.available) {
            title = 'Project Already Exists';
            message = `The target folder <code>${escapeHtml(targetPath)}</code> already contains a <code>project.json</code>. Use Open Existing Project instead of Create New Project.`;
        }

        const actionHtml = status.available
            ? `
                <div class="mt-3">
                    <button
                        type="button"
                        class="btn btn-sm btn-outline-primary"
                        data-action="open-existing-project"
                        data-path="${escapeHtml(status.project_json_path || targetPath)}"
                    >
                        <i class="fas fa-folder-open me-1"></i>Open Existing Project
                    </button>
                </div>
            `
            : '';

        setCreateResultHtml(
            `
                <div class="alert alert-warning">
                    <h5><i class="fas fa-exclamation-triangle me-2"></i>${title}</h5>
                    <p class="mb-0">${message}</p>
                    ${actionHtml}
                </div>
            `,
            'preflight'
        );

        return { conflict: true, targetPath, status };
    } catch (_error) {
        if (requestToken === createTargetStatusRequestToken) {
            clearCreateResult('preflight');
        }
        return { conflict: false, targetPath };
    }
}

function scheduleCreateTargetStatusCheck() {
    resetCreateTargetStatusChecks();
    createTargetStatusDebounceTimer = window.setTimeout(() => {
        checkCreateTargetStatus().catch(() => {});
    }, 200);
}

export function renderRecentProjects() {
    const block = document.getElementById('recentProjectsBlock');
    const listEl = document.getElementById('recentProjectsList');
    if (!block || !listEl) return;

    const list = getRecentProjects();
    if (!list.length) {
        block.style.display = 'none';
        listEl.innerHTML = '';
        return;
    }

    Promise.all(list.map(async (project) => ({
        project,
        available: await isRecentProjectAvailable(project.path)
    }))).then(results => {
        const availableProjects = results
            .filter(({ available }) => available !== false)
            .map(({ project }) => project);

        const unavailableProjects = results.filter(({ available }) => available === false);
        if (unavailableProjects.length > 0) {
            results
                .filter(({ available }) => available === false)
                .forEach(({ project }) => recentProjectStatusCache.delete(project.path));
            saveRecentProjects(availableProjects);
        }

        if (!availableProjects.length) {
            block.style.display = 'none';
            listEl.innerHTML = '';
            return;
        }

        block.style.display = 'block';
        listEl.innerHTML = availableProjects.map((p, idx) => {
        const label = p.name || p.path;
        const iconClass = resolveProjectIconClass(p.icon);
        const safeLabel = escapeHtml(label);
        const safePath = escapeHtml(p.path || '');
        const safeIconClass = escapeHtml(iconClass);
        return `
            <button type="button" class="btn btn-outline-secondary btn-sm recent-project-btn" data-path="${safePath}" data-name="${safeLabel}" data-icon="${safeIconClass}" data-recent-id="${idx}" title="${safePath}">
                <span class="me-1" aria-hidden="true">${safeIconClass}</span>${safeLabel}
            </button>`;
        }).join('');
    }).catch(() => {
        block.style.display = 'none';
        listEl.innerHTML = '';
    });
}

// Load global library settings
export async function loadGlobalSettings() {
    try {
        const response = await fetchWithApiFallback('/api/settings/global-library');
        const data = await response.json();
        if (data.success) {
            const libraryInput = document.getElementById('globalLibraryPath');
            libraryInput.value = data.global_template_library_path || '';
            if (data.default_library_path) {
                libraryInput.placeholder = `Default: ${data.default_library_path}`;
            }

            const recipesInput = document.getElementById('globalRecipesPath');
            recipesInput.value = data.global_recipes_path || '';

            const connectedToggle = document.getElementById('connectedToServerToggle');
            if (connectedToggle) {
                connectedToggle.checked = Boolean(data.connected_to_server);
            }

            if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.setConnectedToServer === 'function') {
                window.PrismFileSystemMode.setConnectedToServer(Boolean(data.connected_to_server));
            }

            updateLibraryInfoPanel(data.global_template_library_path || data.default_library_path, null);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function loadBackendMonitoringSetting() {
    const toggle = document.getElementById('backendMonitoringToggle');
    const verboseToggle = document.getElementById('backendMonitoringVerboseToggle');
    if (!toggle) return;

    try {
        const response = await fetchWithApiFallback('/api/settings/backend-monitoring');
        const data = await response.json();
        if (data && data.success) {
            const enabled = Boolean(data.backend_monitoring);
            const verboseEnabled = Boolean(data.backend_monitoring_verbose);

            toggle.checked = enabled;
            if (verboseToggle) {
                verboseToggle.checked = verboseEnabled;
                verboseToggle.disabled = !enabled;
                if (!enabled) {
                    verboseToggle.checked = false;
                }
            }
        }
    } catch (error) {
        console.error('Error loading backend monitoring setting:', error);
    }
}

async function saveBackendMonitoringSetting(payload) {
    const response = await fetchWithApiFallback('/api/settings/backend-monitoring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (!response.ok || !data || !data.success) {
        throw new Error(data?.error || 'Failed to save backend monitoring setting');
    }

    return {
        backendMonitoring: Boolean(data.backend_monitoring),
        backendMonitoringVerbose: Boolean(data.backend_monitoring_verbose),
    };
}

async function loadDedicatedTerminalSetting() {
    const toggle = document.getElementById('dedicatedTerminalToggle');
    if (!toggle) return;

    try {
        const response = await fetchWithApiFallback('/api/settings/dedicated-terminal');
        const data = await response.json();
        if (data && data.success) {
            toggle.checked = Boolean(data.show_dedicated_terminal);
        }
    } catch (error) {
        console.error('Error loading dedicated terminal setting:', error);
    }
}

async function ensureOpenSectionVisibleForLoadedProject() {
    const path = String(currentProjectPath || '').trim();
    if (!path || !shouldHideProjectTypeSelectionWhenLoaded()) {
        return;
    }

    const openSection = document.getElementById('section-open');
    if (openSection && !openSection.classList.contains('active')) {
        selectProjectType('open');
    }

    const existingPathInput = document.getElementById('existingPath');
    if (existingPathInput && !String(existingPathInput.value || '').trim()) {
        existingPathInput.value = path;
    }

    await loadProjectWithoutValidation(path, null, { skipContextGuard: true });

    updateQuickValidateButtonState();
}

function submitOpenProjectPath(path) {
    const normalizedPath = String(path || '').trim();
    const existingPathInput = document.getElementById('existingPath');
    const openProjectForm = document.getElementById('openProjectForm');
    if (!normalizedPath || !existingPathInput || !openProjectForm) {
        return;
    }

    existingPathInput.value = normalizedPath;
    selectProjectType('open');

    if (typeof openProjectForm.requestSubmit === 'function') {
        openProjectForm.requestSubmit();
        return;
    }

    openProjectForm.dispatchEvent(
        new Event('submit', { bubbles: true, cancelable: true })
    );
}

async function saveDedicatedTerminalSetting(enabled) {
    const response = await fetchWithApiFallback('/api/settings/dedicated-terminal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ show_dedicated_terminal: Boolean(enabled) })
    });

    const data = await response.json();
    if (!response.ok || !data || !data.success) {
        throw new Error(data?.error || 'Failed to save dedicated terminal setting');
    }

    return Boolean(data.show_dedicated_terminal);
}

function initBackendMonitoringToggle() {
    const toggle = document.getElementById('backendMonitoringToggle');
    const verboseToggle = document.getElementById('backendMonitoringVerboseToggle');
    if (!toggle) return;

    loadBackendMonitoringSetting();

    toggle.addEventListener('change', async () => {
        const desired = Boolean(toggle.checked);
        toggle.disabled = true;
        if (verboseToggle) {
            verboseToggle.disabled = true;
        }

        try {
            const persisted = await saveBackendMonitoringSetting({
                backend_monitoring: desired,
                backend_monitoring_verbose: desired
                    ? Boolean(verboseToggle?.checked)
                    : false,
            });
            toggle.checked = persisted.backendMonitoring;
            if (verboseToggle) {
                verboseToggle.checked = persisted.backendMonitoringVerbose;
                verboseToggle.disabled = !persisted.backendMonitoring;
                if (!persisted.backendMonitoring) {
                    verboseToggle.checked = false;
                }
            }
        } catch (error) {
            console.error('Error saving backend monitoring setting:', error);
            toggle.checked = !desired;
            alert('Could not update backend monitoring setting.');
            if (verboseToggle) {
                verboseToggle.disabled = !toggle.checked;
            }
        } finally {
            toggle.disabled = false;
            if (verboseToggle) {
                verboseToggle.disabled = !toggle.checked;
            }
        }
    });

    if (verboseToggle) {
        verboseToggle.addEventListener('change', async () => {
            const desiredVerbose = Boolean(verboseToggle.checked);
            const baseEnabled = Boolean(toggle.checked);

            if (!baseEnabled) {
                verboseToggle.checked = false;
                return;
            }

            toggle.disabled = true;
            verboseToggle.disabled = true;
            try {
                const persisted = await saveBackendMonitoringSetting({
                    backend_monitoring_verbose: desiredVerbose,
                });
                toggle.checked = persisted.backendMonitoring;
                verboseToggle.checked = persisted.backendMonitoringVerbose;
                verboseToggle.disabled = !persisted.backendMonitoring;
            } catch (error) {
                console.error('Error saving backend monitoring verbose setting:', error);
                verboseToggle.checked = !desiredVerbose;
                alert('Could not update backend monitoring verbose setting.');
                verboseToggle.disabled = !toggle.checked;
            } finally {
                toggle.disabled = false;
                verboseToggle.disabled = !toggle.checked;
            }
        });
    }
}

function initDedicatedTerminalToggle() {
    const toggle = document.getElementById('dedicatedTerminalToggle');
    if (!toggle) return;

    loadDedicatedTerminalSetting();

    toggle.addEventListener('change', async () => {
        const desired = Boolean(toggle.checked);
        toggle.disabled = true;

        try {
            const persisted = await saveDedicatedTerminalSetting(desired);
            toggle.checked = persisted;
        } catch (error) {
            console.error('Error saving dedicated terminal setting:', error);
            toggle.checked = !desired;
            alert('Could not update dedicated terminal setting.');
        } finally {
            toggle.disabled = false;
        }
    });
}

// Load library info (both global and project)
export async function loadLibraryInfo() {
    try {
        const response = await fetchWithApiFallback('/api/projects/library-path');
        const data = await response.json();

        const infoPanel = document.getElementById('libraryInfoPanel');
        infoPanel.style.display = 'block';

        const globalInfo = document.getElementById('globalLibraryInfo');
        if (data.global_library_path) {
            globalInfo.innerHTML = `<code class="small">${escapeHtml(data.global_library_path)}</code>`;
        } else {
            globalInfo.innerHTML = '<span class="text-muted">Not configured</span>';
        }

        const projectInfo = document.getElementById('projectLibraryInfo');
        if (data.success && data.project_library_path) {
            projectInfo.innerHTML = `<code class="small">${escapeHtml(data.project_library_path)}</code>`;
        } else if (data.project_path) {
            projectInfo.innerHTML = '<span class="text-warning"><i class="fas fa-exclamation-triangle me-1"></i>No library folder</span>';
        } else {
            projectInfo.innerHTML = '<span class="text-muted">Select a project</span>';
        }
    } catch (error) {
        console.error('Error loading library info:', error);
    }
}

export function updateLibraryInfoPanel(globalPath, projectPath) {
    const infoPanel = document.getElementById('libraryInfoPanel');
    infoPanel.style.display = 'block';

    const globalInfo = document.getElementById('globalLibraryInfo');
    if (globalPath) {
        globalInfo.innerHTML = `<code class="small">${escapeHtml(globalPath)}</code>`;
    } else {
        globalInfo.innerHTML = '<span class="text-muted">Not configured</span>';
    }
}

initProjectPathPickers({
    fetchWithApiFallback,
    validateProjectField,
    clearCreateResult,
});

// Save global settings
const globalSettingsForm = document.getElementById('globalSettingsForm');
if (globalSettingsForm) {
    globalSettingsForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const btn = this.querySelector('button[type="submit"]');
        const originalText = setButtonLoading(btn, true, 'Saving...');

        const libraryPath = document.getElementById('globalLibraryPath').value.trim();
        const recipesPath = document.getElementById('globalRecipesPath').value.trim();
        const connectedToServer = Boolean(document.getElementById('connectedToServerToggle')?.checked);

        try {
            const response = await fetchWithApiFallback('/api/settings/global-library', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    global_template_library_path: libraryPath,
                    global_recipes_path: recipesPath,
                    connected_to_server: connectedToServer,
                })
            });
            const result = await response.json();

            const statusDiv = document.getElementById('libraryStatusMessage');
            if (result.success) {
                statusDiv.innerHTML = `
                    <div class="alert alert-success py-2">
                        <i class="fas fa-check-circle me-2"></i>Settings saved successfully!
                    </div>
                `;
                updateLibraryInfoPanel(result.global_template_library_path, null);
            } else {
                statusDiv.innerHTML = `
                    <div class="alert alert-danger py-2">
                        <i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(result.error || 'Could not save settings.')}
                    </div>
                `;
            }

            if (result.success) {
                if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.setConnectedToServer === 'function') {
                    window.PrismFileSystemMode.setConnectedToServer(connectedToServer);
                }

                window.dispatchEvent(new CustomEvent('prism-library-settings-changed', {
                    detail: {
                        global_library_path: document.getElementById('globalLibraryPath').value,
                        connected_to_server: connectedToServer,
                    }
                }));
            }

            setTimeout(() => {
                if (result.success) {
                    statusDiv.innerHTML = '';
                }
            }, 3000);

        } catch (error) {
            document.getElementById('libraryStatusMessage').innerHTML = `
                <div class="alert alert-danger py-2">
                    <i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(error.message || 'Could not save settings.')}
                </div>
            `;
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    });
}

export async function useDefaultLibrary() {
    document.getElementById('globalRecipesPath').value = '';
    try {
        const response = await fetchWithApiFallback('/api/settings/global-library');
        const data = await response.json();
        if (data.default_library_path) {
            document.getElementById('globalLibraryPath').value = data.default_library_path;
            document.getElementById('libraryStatusMessage').innerHTML = `
                <div class="alert alert-info py-2">
                    <i class="fas fa-info-circle me-2"></i>Default path set. Click "Save Settings" to apply.
                </div>
            `;
        }
    } catch (error) {
        console.error('Error getting default path:', error);
    }
}

export async function clearGlobalLibrary() {
    if (!confirm('Clear the global template and recipe library paths?')) {
        return;
    }
    document.getElementById('globalRecipesPath').value = '';

    try {
        const response = await fetchWithApiFallback('/api/settings/global-library', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ global_template_library_path: '' })
        });
        const result = await response.json();

        if (result.success) {
            document.getElementById('globalLibraryPath').value = '';
            document.getElementById('libraryStatusMessage').innerHTML = `
                <div class="alert alert-info py-2">
                    <i class="fas fa-info-circle me-2"></i>Global library path cleared.
                </div>
            `;
            updateLibraryInfoPanel(null, null);

            window.dispatchEvent(new CustomEvent('prism-library-settings-changed', {
                detail: { global_library_path: null }
            }));

            setTimeout(() => {
                document.getElementById('libraryStatusMessage').innerHTML = '';
            }, 3000);
        }
    } catch (error) {
        console.error('Error clearing library:', error);
    }
}

function hasUnsavedNewProjectDraft() {
    const createForm = document.getElementById('createProjectForm');
    const metadataForm = document.getElementById('studyMetadataForm');

    const forms = [createForm, metadataForm].filter(Boolean);
    if (!forms.length) return false;

    for (const form of forms) {
        const fields = form.querySelectorAll('input, textarea, select');
        for (const field of fields) {
            if (field.type === 'hidden') {
                continue;
            }

            if (field.tagName === 'SELECT') {
                const options = Array.from(field.options || []);
                if (options.some(option => option.selected !== option.defaultSelected)) {
                    return true;
                }
                continue;
            }

            if (field.type === 'checkbox' || field.type === 'radio') {
                if (field.checked !== field.defaultChecked) return true;
                continue;
            }

            if ((field.value || '').trim() !== (field.defaultValue || '').trim()) {
                return true;
            }
        }
    }

    const ethicsChoice = document.getElementById('metadataEthicsApproved')?.value || '';
    const fundingChoice = document.getElementById('metadataFundingDeclared')?.value || '';
    return Boolean(ethicsChoice || fundingChoice);
}

function confirmProjectContextChange(actionLabel = 'continue', targetPath = '') {
    const normalizedTargetPath = String(targetPath || '').trim();
    const normalizedCurrentPath = String(currentProjectPath || '').trim();

    if (normalizedTargetPath && normalizedCurrentPath && normalizedTargetPath === normalizedCurrentPath) {
        return true;
    }

    if (isStudyMetadataBusy()) {
        alert('Please wait until project metadata finishes loading or saving before switching projects.');
        return false;
    }

    if (normalizedCurrentPath && hasUnsavedStudyMetadataChanges()) {
        return confirm(
            '⚠️ Unsaved project metadata changes detected.\n\n' +
            `If you ${actionLabel}, the current changes will be lost.\n\n` +
            'Do you want to continue?'
        );
    }

    const createSection = document.getElementById('section-create');
    const createAlreadyActive = createSection && createSection.classList.contains('active');
    if (!normalizedCurrentPath && createAlreadyActive && hasUnsavedNewProjectDraft()) {
        return confirm(
            '⚠️ Unsaved New Project data detected.\n\n' +
            `If you ${actionLabel}, the current project and study metadata draft will be lost.\n\n` +
            'Do you want to continue?'
        );
    }

    return true;
}

function clearCurrentProjectForNewDraft() {
    currentProjectPath = '';
    currentProjectName = '';
    updateProjectTypeSelectionVisibility();

    if (window.updateNavbarProject) {
        window.updateNavbarProject('', '');
    } else {
        setGlobalProjectState('', '');
    }

    // Keep backend session in sync to avoid accidental writes to a stale project.
    fetchWithApiFallback('/api/projects/current', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: '' })
    }).catch(() => {
        // UI state remains source of truth for this interaction.
    });
}

// Project type selection
export function selectProjectType(type) {
    // Warn if switching to "create" from an existing project without saving
    if (type === 'create' && currentProjectPath) {
        const confirmSwitch = confirm(
            '⚠️ You are editing an existing project.\n\n' +
            'If you switch to "New Project" without saving, any changes will be lost.\n\n' +
            'Are you sure you want to continue?'
        );
        if (!confirmSwitch) {
            return; // User cancelled, don't switch
        }

        clearCurrentProjectForNewDraft();
    }

    // Warn if user is already in New Project mode and has unsaved draft input
    const createSection = document.getElementById('section-create');
    const createAlreadyActive = createSection && createSection.classList.contains('active');
    if (type === 'create' && !currentProjectPath && createAlreadyActive && hasUnsavedNewProjectDraft()) {
        const confirmReset = confirm(
            '⚠️ Unsaved New Project data detected.\n\n' +
            'Clicking "New Project" again will clear all currently entered project and study metadata fields.\n\n' +
            'Do you want to discard these unsaved changes?'
        );
        if (!confirmReset) {
            return;
        }
    }
    
    document.querySelectorAll('.project-card').forEach(card => {
        card.classList.remove('active');
    });
    document.getElementById('card-' + type).classList.add('active');

    document.querySelectorAll('.form-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById('section-' + type).classList.add('active');

    const createBtnContainer = document.getElementById('saveStudyMetadataSection');
    if (createBtnContainer) {
        createBtnContainer.style.display = (type === 'create') ? '' : 'none';
    }

    if (type === 'create') {
        clearCreateResult();
        resetCreateTargetStatusChecks();
        const projectNameInput = document.getElementById('projectName');
        if (projectNameInput) {
            projectNameInput.value = '';
            projectNameInput.classList.remove('is-invalid');
        }
        const projectPathInput = document.getElementById('projectPath');
        if (projectPathInput) {
            projectPathInput.value = '';
            projectPathInput.classList.remove('is-invalid');
        }
        const projectNameError = document.getElementById('projectNameError');
        if (projectNameError) projectNameError.textContent = '';
        resetStudyMetadataForm();
        
        // Reset all badges to their original colors (REQUIRED=red, etc.)
        if (window.resetAllBadges) {
            window.resetAllBadges();
        }
    }

    setCurrentProjectBannerVisibility(type);

    if (type === 'open') {
        const openProjectSection = document.getElementById('openProjectSection');
        if (openProjectSection) {
            if (window.bootstrap && typeof window.bootstrap.Collapse === 'function') {
                const collapse = window.bootstrap.Collapse.getOrCreateInstance(openProjectSection, { toggle: false });
                collapse.show();
            } else {
                openProjectSection.classList.add('show');
            }
        }

        const existingPathInput = document.getElementById('existingPath');
        if (existingPathInput) {
            existingPathInput.focus();
            existingPathInput.select();
        }
    }

    if (type === 'create') {
        const projectNameField = document.getElementById('projectName');
        if (projectNameField) {
            projectNameField.focus();
        }
    }

    showStudyMetadataCard();
}

// ── Init PRISM on existing BIDS dataset ─────────────────────────────────────

initProjectInitOnBidsController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    showExportCard,
    showMethodsCard,
});

initProjectFileBrowser({ fetchWithApiFallback, prefersServerPicker });

// Validate project name (no spaces, valid folder name)
const projectNameInput = document.getElementById('projectName');
if (projectNameInput) {
    projectNameInput.addEventListener('input', function(e) {
        const value = e.target.value;
        const isValid = /^[a-zA-Z0-9_-]*$/.test(value);
        const errorDiv = document.getElementById('projectNameError');

        if (!isValid) {
            e.target.classList.add('is-invalid');
            errorDiv.textContent = 'Only letters, numbers, underscores (_) and hyphens (-) allowed. No spaces!';
        } else {
            e.target.classList.remove('is-invalid');
            errorDiv.textContent = '';
        }

        clearCreateResult();
        scheduleCreateTargetStatusCheck();
    });
}

const projectPathInput = document.getElementById('projectPath');
if (projectPathInput) {
    projectPathInput.addEventListener('input', function() {
        this.classList.remove('is-invalid');
        clearCreateResult();
        scheduleCreateTargetStatusCheck();
    });
    projectPathInput.addEventListener('change', function() {
        this.classList.remove('is-invalid');
        clearCreateResult();
        scheduleCreateTargetStatusCheck();
    });
}

initCreateProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    textToArray: _textToArray,
    getProjectStateSnapshot,
    setCreateResultHtml,
    joinProjectTargetPath,
    resetCreateTargetStatusChecks,
    checkCreateTargetStatus,
    validateAllMandatoryFields,
    validateDatasetDescriptionDraftLive,
    getCitationAuthorsList,
    getEthicsApprovals,
    getFundingList,
    getRecMethodList,
    getRecLocationList,
    getYearMonthValue,
    saveProjectSchemaConfig,
    applyCurrentProject,
    getCurrentProjectState: () => ({
        path: currentProjectPath,
        name: currentProjectName,
        icon: currentProjectIcon,
    }),
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showExportCard,
    showMethodsCard,
});

async function runProjectValidation(path, triggerButton = null) {
    const normalizedPath = String(path || '').trim();
    if (!normalizedPath) {
        showOpenProjectError('Please provide a project folder or a project.json path.', 'Selection Error');
        return false;
    }

    const originalText = triggerButton ? setButtonLoading(triggerButton, true, 'Validating...') : null;

    try {
        const response = await fetchWithApiFallback('/api/projects/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: normalizedPath })
        });
        const result = await response.json().catch(() => ({
            success: false,
            error: 'Server returned an invalid response while validating the project.'
        }));

        if (!response.ok || !result.success) {
            showOpenProjectError(result.error || `Validation request failed (${response.status})`);
            return false;
        }

        const stats = result.stats;
        const validationPath = String(result.current_project?.path || normalizedPath).trim() || normalizedPath;
        const issues = Array.isArray(result.issues) ? result.issues : [];
        const fixableIssues = Array.isArray(result.fixable_issues) ? result.fixable_issues : [];
        const runnerWarnings = Array.isArray(result.runner_warnings) ? result.runner_warnings : [];
        const issueGroups = groupValidationRecordsByCode(issues, {
            fallbackCode: 'ISSUE',
            defaultMessage: 'Validation issue',
        });
        const warningGroups = groupValidationRecordsByCode(runnerWarnings, {
            fallbackCode: 'WARNING',
            defaultMessage: 'Validation warning',
        });

        let statusClass = 'valid';
        let statusIcon = 'check-circle';
        let statusText = 'Valid PRISM Structure';

        if (issues.length > 0) {
            const hasNonFixable = issues.some(i => !i.fixable);
            if (hasNonFixable) {
                statusClass = 'invalid';
                statusIcon = 'exclamation-circle';
                statusText = `${issues.length} Issue(s) Found`;
            } else {
                statusClass = 'warning';
                statusIcon = 'exclamation-triangle';
                statusText = `${issues.length} Fixable Issue(s) Found`;
            }
        } else if (runnerWarnings.length > 0) {
            statusClass = 'warning';
            statusIcon = 'exclamation-triangle';
            const warningGroupLabel = warningGroups.length === 1 ? 'code group' : 'code groups';
            statusText = `${runnerWarnings.length} Non-blocking Warning(s) in ${warningGroups.length} ${warningGroupLabel}`;
        }

        let html = `
            <div class="validation-result ${statusClass}">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="mb-0"><i class="fas fa-${statusIcon} me-2"></i>${statusText}</h5>
                    ${stats.is_yoda ? '<span class="badge bg-info"><i class="fas fa-microchip me-1"></i>YODA Layout</span>' : ''}
                </div>

                <div class="alert alert-warning d-none py-2 mb-3" id="projectRequirementGapAlert" role="alert">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    <span id="projectRequirementGapText"></span>
                </div>

                ${getBeginnerHelpModeEnabled() ? `
                <div class="mb-3">
                    <h6 class="mb-1">Project Metadata</h6>
                    <small class="text-muted d-block" id="projectBoxSaveHint">
                        <i class="fas fa-info-circle me-1"></i>Save metadata updates to project.json, dataset_description.json, CITATION.cff, and README.md.
                    </small>
                </div>` : ''}

                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">${stats.subjects}</div>
                        <div class="stat-label">Subjects</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.sessions.length || 0}</div>
                        <div class="stat-label">Sessions</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.modalities.length}</div>
                        <div class="stat-label">Modalities</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stats.has_dataset_description ? '✓' : '✗'}</div>
                        <div class="stat-label">dataset_description</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value ${stats.has_participants_tsv ? 'text-success' : 'text-danger'}">${stats.has_participants_tsv ? '✓' : '✗'}</div>
                        <div class="stat-label">participants.tsv</div>
                    </div>
                    <div class="stat-item" id="projectMetadataStatItem">
                        <div class="stat-value" id="projectMetadataStatValue">✓</div>
                        <div class="stat-label">metadata</div>
                    </div>
                </div>
        `;

        if (issueGroups.length > 0) {
            html += `
                <hr>
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="mb-0">Issues</h6>
                    ${fixableIssues.length > 0 ? `
                        <button class="btn btn-warning btn-sm" data-action="fix-all" data-path="${escapeHtml(validationPath)}">
                            <i class="fas fa-wrench me-1"></i>Fix All (${fixableIssues.length})
                        </button>
                    ` : ''}
                </div>
                <div id="issuesList">
            `;

            issueGroups.forEach((issueGroup, index) => {
                const collapseId = `project-issue-group-${index}`;
                const previewMessage = issueGroup.messages[0] ? issueGroup.messages[0].message : 'Validation issue';
                const groupAction = getProjectValidationAction(issueGroup.code);

                html += `
                    <div class="issue-item ${issueGroup.hasFixable ? 'fixable' : 'not-fixable'} project-validation-group">
                        <div class="d-flex align-items-center gap-2">
                            <button type="button"
                                class="project-group-toggle flex-grow-1"
                                data-bs-toggle="collapse"
                                data-bs-target="#${collapseId}"
                                aria-expanded="false"
                                aria-controls="${collapseId}">
                                <div class="project-group-summary d-flex flex-column">
                                    <span class="fw-bold">${escapeHtml(issueGroup.code)} (${issueGroup.count})</span>
                                    <span class="small text-muted project-group-preview">${escapeHtml(previewMessage)}</span>
                                </div>
                                <i class="fas fa-chevron-down small text-muted project-group-chevron"></i>
                            </button>
                            ${issueGroup.hasFixable ? `
                                <button class="btn btn-sm btn-outline-warning flex-shrink-0" data-action="fix-issue" data-path="${escapeHtml(validationPath)}" data-code="${escapeHtml(issueGroup.code)}" aria-label="Apply fix for ${escapeHtml(issueGroup.code)}">
                                    <i class="fas fa-wrench"></i>
                                </button>
                            ` : groupAction ? `
                                <a href="${escapeHtml(groupAction.href)}" class="btn btn-sm btn-outline-success flex-shrink-0" aria-label="${escapeHtml(groupAction.label)} for ${escapeHtml(issueGroup.code)}">
                                    <i class="${escapeHtml(groupAction.iconClass)} me-1"></i>${escapeHtml(groupAction.label)}
                                </a>
                            ` : `
                                <span class="badge bg-secondary flex-shrink-0">Manual fix required</span>
                            `}
                        </div>
                        <div class="collapse" id="${collapseId}">
                            <div class="project-group-body">
                                ${renderGroupedValidationHint(issueGroup.fixHints)}
                                ${renderGroupedValidationMessages(issueGroup.messages)}
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
        }

        if (warningGroups.length > 0) {
            html += `
                <hr>
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="mb-0">Validator Warnings (${warningGroups.length} code${warningGroups.length === 1 ? '' : 's'})</h6>
                    <span class="badge bg-warning text-dark">Non-blocking</span>
                </div>
                <div id="projectWarningsList">
            `;

            warningGroups.forEach((warningGroup, index) => {
                const collapseId = `project-warning-group-${index}`;
                const previewMessage = warningGroup.messages[0] ? warningGroup.messages[0].message : 'Validation warning';

                html += `
                    <div class="issue-item not-fixable project-warning-group project-validation-group">
                        <button type="button"
                            class="project-group-toggle"
                            data-bs-toggle="collapse"
                            data-bs-target="#${collapseId}"
                            aria-expanded="false"
                            aria-controls="${collapseId}">
                            <div class="project-group-summary d-flex flex-column">
                                <span class="fw-bold">${escapeHtml(warningGroup.code)} (${warningGroup.count})</span>
                                <span class="small text-muted project-group-preview">${escapeHtml(previewMessage)}</span>
                            </div>
                            <div class="project-group-meta d-flex align-items-center gap-2">
                                <span class="badge bg-warning text-dark">Non-blocking</span>
                                <i class="fas fa-chevron-down small text-muted project-group-chevron"></i>
                            </div>
                        </button>
                        <div class="collapse" id="${collapseId}">
                            <div class="project-group-body">
                                ${renderGroupedValidationHint(warningGroup.fixHints)}
                                ${renderGroupedValidationMessages(warningGroup.messages)}
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
        }

        html += `
            <hr>
            <div class="d-flex justify-content-between align-items-center mt-3">
                <div>
                    <h6 class="text-muted mb-2">Next Steps:</h6>
                    <div class="btn-group" role="group">
                        <a href="/template-editor" class="btn btn-sm btn-outline-success">
                            <i class="fas fa-file-import me-1"></i>Import Templates
                        </a>
                        <a href="/survey-generator" class="btn btn-sm btn-outline-info">
                            <i class="fas fa-poll-h me-1"></i>Survey Export
                        </a>
                        <a href="/validate" class="btn btn-sm btn-outline-primary">
                            <i class="fas fa-check-circle me-1"></i>Validate Dataset
                        </a>
                    </div>
                </div>
                <div class="d-flex flex-column align-items-end">
                    <div class="d-flex gap-2 flex-wrap justify-content-end">
                        <button type="button" class="btn btn-outline-warning" id="projectBoxPreliminarySaveBtn">
                            <i class="fas fa-save me-2"></i>Save Preliminary Project State
                        </button>
                        <button type="button" class="btn btn-info" id="projectBoxSaveBtn">
                            <i class="fas fa-save me-2"></i>Save Changes to Project
                        </button>
                    </div>
                    <small class="text-muted mt-1" id="projectBoxSaveStatus" aria-live="polite"></small>
                </div>
            </div>
        `;

        html += '</div>';
        setProjectValidationResult(html);

        applyCurrentProject(result.current_project);
        addRecentProject(currentProjectName, validationPath, currentProjectIcon);
        showStudyMetadataCard();
        bindProjectBoxActionButtons();
        updateCreateProjectButton();
        showExportCard();
        showMethodsCard();

        return true;
    } catch (error) {
        showOpenProjectError(error.message || 'Validation failed unexpectedly.');
        return false;
    } finally {
        if (triggerButton) {
            setButtonLoading(triggerButton, false, null, originalText);
        }
        updateQuickValidateButtonState();
    }
}

const openProjectController = initOpenProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    getBeginnerHelpModeEnabled,
    resolveProjectIconClass,
    getCurrentProjectState: () => ({
        path: currentProjectPath,
        name: currentProjectName,
        icon: currentProjectIcon,
    }),
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showExportCard,
    showMethodsCard,
    bindProjectBoxActionButtons,
});

const getOpenProjectActionPath = openProjectController.getOpenProjectActionPath;
const updateQuickValidateButtonState = openProjectController.updateQuickValidateButtonState;
const loadProjectWithoutValidation = openProjectController.loadProjectWithoutValidation;
const runProjectValidation = openProjectController.runProjectValidation;

export async function fixIssue(path, code) {
    try {
        const response = await fetchWithApiFallback('/api/projects/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path, fix_codes: [code] })
        });
        const result = await response.json();

        if (result.success) {
            await runProjectValidation(path);
        } else {
            alert('Error applying fix: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

export async function fixAllIssues(path) {
    try {
        const response = await fetchWithApiFallback('/api/projects/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        const result = await response.json();

        if (result.success) {
            await runProjectValidation(path);
        } else {
            alert('Error applying fixes: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

export async function clearCurrentProject() {
    try {
        await fetchWithApiFallback('/api/projects/current', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: null })
        });
        window.location.reload();
    } catch (error) {
        console.error('Error clearing project:', error);
    }
}

// ===== INITIALIZATION =====

export function initProjectsPage() {
    if (projectsPageInitialized) {
        updateQuickValidateButtonState();
        return;
    }
    projectsPageInitialized = true;

    const isWindows = navigator.platform.toUpperCase().indexOf('WIN') > -1;
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') > -1;
    const existingPathInput = document.getElementById('existingPath');
    const projectPathInput = document.getElementById('projectPath');
    const pathHelpTooltip = document.getElementById('pathHelpTooltip');

    if (existingPathInput) {
        if (isWindows) {
            existingPathInput.placeholder = "C:\\Users\\YourName\\MyProject\\project.json";
        } else if (isMac) {
            existingPathInput.placeholder = "/Users/YourName/MyProject/project.json";
        } else {
            existingPathInput.placeholder = "/home/username/MyProject/project.json";
        }
    }

    if (projectPathInput) {
        if (isWindows) {
            projectPathInput.placeholder = "C:\\Users\\YourName\\Documents";
        } else if (isMac) {
            projectPathInput.placeholder = "/Users/YourName/Documents";
        } else {
            projectPathInput.placeholder = "/home/username/Documents";
        }
    }

    if (pathHelpTooltip) {
        const osExample = isWindows ? "C:\\Users\\YourName\\Documents\\MyProject\\project.json" :
            isMac ? "/Users/YourName/Documents/MyProject/project.json" :
            "/home/username/Documents/MyProject/project.json";
        const tooltipTitle = `Type the full path to your project folder or <code>project.json</code> file (e.g., <code>${osExample}</code>), or click Browse to select it.`;

        pathHelpTooltip.setAttribute('title', tooltipTitle);
        pathHelpTooltip.setAttribute('data-bs-original-title', tooltipTitle);

        if (window.bootstrap && typeof window.bootstrap.Tooltip === 'function') {
            window.bootstrap.Tooltip.getOrCreateInstance(pathHelpTooltip);
        }
    }

    initProjectFieldHints();
    initBeginnerHelpMode();
    initBackendMonitoringToggle();
    initDedicatedTerminalToggle();

    loadGlobalSettings();
    loadLibraryInfo();
    showStudyMetadataCard();
    showExportCard();
    showMethodsCard();
    renderRecentProjects();
    loadRecentProjectsFromServer();
    ensureOpenSectionVisibleForLoadedProject();

    if (currentProjectPath) {
        addRecentProject(currentProjectName, currentProjectPath, currentProjectIcon);
    }

    const sections = [
        { element: 'openProjectSection', chevron: 'openProjectChevron' },
        { element: 'studyMetadataSection', chevron: 'studyMetadataChevron' },
        { element: 'methodsSectionBody', chevron: 'methodsSectionChevron' },
        { element: 'exportSection', chevron: 'exportChevron' },
        { element: 'settingsSection', chevron: 'settingsChevron' }
    ];

    sections.forEach(section => {
        const el = document.getElementById(section.element);
        const chevron = document.getElementById(section.chevron);
        if (el && chevron) {
            el.addEventListener('shown.bs.collapse', function() {
                chevron.classList.replace('fa-chevron-down', 'fa-chevron-up');
            });
            el.addEventListener('hidden.bs.collapse', function() {
                chevron.classList.replace('fa-chevron-up', 'fa-chevron-down');
            });
        }
    });

    document.querySelectorAll('.card-header[data-bs-toggle="collapse"][role="button"]').forEach((header) => {
        if (!header.hasAttribute('tabindex')) {
            header.setAttribute('tabindex', '0');
        }
        header.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                header.click();
            }
        });
    });

    const validationResultDiv = document.getElementById('validationResult');
    if (validationResultDiv) {
        validationResultDiv.addEventListener('click', (event) => {
            const fixAllBtn = event.target.closest('[data-action="fix-all"]');
            if (fixAllBtn) { fixAllIssues(fixAllBtn.dataset.path); return; }
            const fixOneBtn = event.target.closest('[data-action="fix-issue"]');
            if (fixOneBtn) { fixIssue(fixOneBtn.dataset.path, fixOneBtn.dataset.code); return; }
            const validateProjectBtn = event.target.closest('[data-action="validate-project"]');
            if (validateProjectBtn) {
                runProjectValidation(validateProjectBtn.dataset.path || getOpenProjectActionPath());
            }
        });
    }

    const recentList = document.getElementById('recentProjectsList');
    if (recentList) {
        recentList.addEventListener('click', (event) => {
            const btn = event.target.closest('.recent-project-btn');
            if (!btn) return;
            const path = btn.getAttribute('data-path');
            if (path) {
                submitOpenProjectPath(path);
            }
        });
    }

    const createResultDiv = document.getElementById('createResult');
    if (createResultDiv) {
        createResultDiv.addEventListener('click', (event) => {
            const openExistingBtn = event.target.closest('[data-action="open-existing-project"]');
            if (!openExistingBtn) return;
            const path = openExistingBtn.getAttribute('data-path');
            if (!path) return;
            submitOpenProjectPath(path);
        });
    }

    const clearRecentBtn = document.getElementById('clearRecentProjectsBtn');
    if (clearRecentBtn) {
        clearRecentBtn.addEventListener('click', () => {
            if (!confirm('Clear recent projects list?')) return;
            clearRecentProjects();
        });
    }

    const createSection = document.getElementById('section-create');
    const openSection = document.getElementById('section-open');
    if (createSection?.classList.contains('active')) {
        setCurrentProjectBannerVisibility('create');
    } else if (openSection?.classList.contains('active')) {
        setCurrentProjectBannerVisibility('open');
    }

    const cardCreate = document.getElementById('card-create');
    if (cardCreate) {
        cardCreate.addEventListener('click', () => selectProjectType('create'));
        cardCreate.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectProjectType('create');
            }
        });
    }

    const cardOpen = document.getElementById('card-open');
    if (cardOpen) {
        cardOpen.addEventListener('click', () => selectProjectType('open'));
        cardOpen.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectProjectType('open');
            }
        });
    }

    const cardInitBids = document.getElementById('card-init-bids');
    if (cardInitBids) {
        cardInitBids.addEventListener('click', () => selectProjectType('init-bids'));
        cardInitBids.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectProjectType('init-bids');
            }
        });
    }

    const clearCurrentProjectBtn = document.getElementById('clearCurrentProjectBtn');
    if (clearCurrentProjectBtn) {
        clearCurrentProjectBtn.addEventListener('click', () => {
            clearCurrentProject();
        });
    }

    const useDefaultLibraryBtn = document.getElementById('useDefaultLibraryBtn');
    if (useDefaultLibraryBtn) {
        useDefaultLibraryBtn.addEventListener('click', () => {
            useDefaultLibrary();
        });
    }

    const clearGlobalLibraryBtn = document.getElementById('clearGlobalLibraryBtn');
    if (clearGlobalLibraryBtn) {
        clearGlobalLibraryBtn.addEventListener('click', () => {
            clearGlobalLibrary();
        });
    }
}

// Expose for inline handlers and legacy code
window.selectProjectType = selectProjectType;
window.fixIssue = fixIssue;
window.fixAllIssues = fixAllIssues;
window.clearCurrentProject = clearCurrentProject;
window.useDefaultLibrary = useDefaultLibrary;
window.clearGlobalLibrary = clearGlobalLibrary;

export { currentProjectPath, currentProjectName };
