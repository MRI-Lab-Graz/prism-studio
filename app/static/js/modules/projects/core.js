/**
 * Projects Module - Core
 * Main project management logic: create, open, load, validate projects
 */

import { setButtonLoading, textToArray as _textToArray } from './helpers.js';
import { initCreateProjectController } from './create-project.js';
import { initCreatePreflightController } from './create-preflight.js';
import { initProjectInitOnBidsController } from './init-on-bids.js';
import { initOpenProjectController } from './open-project.js';
import { initProjectsPageBootstrap } from './page-bootstrap.js';
import { initProjectPathPickers } from './path-pickers.js';
import { initProjectSelectionController } from './project-selection.js';
import { createRecentProjectsController } from './recent-projects.js';
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
});

const recentProjectsController = createRecentProjectsController({
    fetchWithApiFallback,
    escapeHtml,
    resolveProjectIconClass,
    getCurrentProjectIcon: () => currentProjectIcon,
});

const getRecentProjects = recentProjectsController.getRecentProjects;
const saveRecentProjects = recentProjectsController.saveRecentProjects;
const addRecentProject = recentProjectsController.addRecentProject;
const clearRecentProjects = recentProjectsController.clearRecentProjects;
const renderRecentProjects = recentProjectsController.renderRecentProjects;
const loadRecentProjectsFromServer = recentProjectsController.loadRecentProjectsFromServer;

export { getRecentProjects, saveRecentProjects, addRecentProject, renderRecentProjects };

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

const createPreflightController = initCreatePreflightController({
    fetchWithApiFallback,
    escapeHtml,
    clearCreateResult,
    setCreateResultHtml,
    joinProjectTargetPath,
    getSelectProjectType: () => selectProjectType,
});

const resetCreateTargetStatusChecks = createPreflightController.resetCreateTargetStatusChecks;
const checkCreateTargetStatus = createPreflightController.checkCreateTargetStatus;
const submitOpenProjectPath = createPreflightController.submitOpenProjectPath;

const projectSelectionController = initProjectSelectionController({
    fetchWithApiFallback,
    getCurrentProjectState: () => ({
        path: currentProjectPath,
        name: currentProjectName,
        icon: currentProjectIcon,
    }),
    applyCurrentProject,
    hasUnsavedStudyMetadataChanges,
    isStudyMetadataBusy,
    clearCreateResult,
    resetCreateTargetStatusChecks,
    resetStudyMetadataForm,
    showStudyMetadataCard,
});

const confirmProjectContextChange = projectSelectionController.confirmProjectContextChange;
const selectProjectType = projectSelectionController.selectProjectType;

export { selectProjectType };

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

const openProjectController = initOpenProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
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
const loadProjectWithoutValidation = openProjectController.loadProjectWithoutValidation;

export async function fixIssue(path, code) {
    try {
        const response = await fetchWithApiFallback('/api/projects/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path, fix_codes: [code] })
        });
        const result = await response.json();

        if (result.success) {
            await loadProjectWithoutValidation(path, null, { skipContextGuard: true });
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
            await loadProjectWithoutValidation(path, null, { skipContextGuard: true });
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
        return;
    }
    projectsPageInitialized = true;

    initProjectsPageBootstrap({
        initProjectFieldHints,
        initBeginnerHelpMode,
        initBackendMonitoringToggle,
        initDedicatedTerminalToggle,
        loadGlobalSettings,
        loadLibraryInfo,
        showStudyMetadataCard,
        showExportCard,
        showMethodsCard,
        renderRecentProjects,
        loadRecentProjectsFromServer,
        ensureOpenSectionVisibleForLoadedProject,
        getCurrentProjectState: () => ({
            path: currentProjectPath,
            name: currentProjectName,
            icon: currentProjectIcon,
        }),
        addRecentProject,
        fixAllIssues,
        fixIssue,
        getOpenProjectActionPath,
        submitOpenProjectPath,
        clearRecentProjects,
        initProjectSelectionUi: () => projectSelectionController.initProjectSelectionUi(),
        clearCurrentProject,
        useDefaultLibrary,
        clearGlobalLibrary,
    });
}

// Expose for inline handlers and legacy code
window.selectProjectType = selectProjectType;
window.fixIssue = fixIssue;
window.fixAllIssues = fixAllIssues;
window.clearCurrentProject = clearCurrentProject;
window.useDefaultLibrary = useDefaultLibrary;
window.clearGlobalLibrary = clearGlobalLibrary;

export { currentProjectPath, currentProjectName };
