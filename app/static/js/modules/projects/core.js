/**
 * Projects Module - Core
 * Main project management logic: create, open, load, validate projects
 */

import { setButtonLoading, textToArray as _textToArray } from './helpers.js';
import { validateProjectField } from './validation.js';
import {
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
import { escapeHtml } from '../../shared/dom.js';

// Global state
let currentProjectPath = '';
let currentProjectName = '';
const recentProjectsKey = 'prism_recent_projects';
const beginnerHelpModeKey = 'prism_beginner_help_mode';
const recentProjectStatusCache = new Map();

function getFallbackApiOrigin() {
    const configuredOrigin = (window.PRISM_API_ORIGIN || '').trim();
    if (configuredOrigin) {
        return configuredOrigin.replace(/\/$/, '');
    }
    return 'http://127.0.0.1:5001';
}

async function fetchWithApiFallback(url, options) {
    try {
        return await fetch(url, options);
    } catch (primaryError) {
        const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
        const isRelativeApiRequest = typeof url === 'string' && url.startsWith('/api/');
        const canRetryWithFallback = isRelativeApiRequest && protocol !== 'http:' && protocol !== 'https:';

        if (!canRetryWithFallback) {
            throw primaryError;
        }

        const fallbackUrl = `${getFallbackApiOrigin()}${url}`;
        try {
            return await fetch(fallbackUrl, options);
        } catch (_fallbackError) {
            throw new Error('Cannot reach PRISM backend API. Please restart PRISM Studio and try again.');
        }
    }
}

function setGlobalProjectState(path, name) {
    setProjectStateSnapshot(path, name);
}

function updateProjectsActiveProjectSummary(name, path) {
    const summary = document.getElementById('projectsActiveProjectSummary');
    if (!summary) return;

    const safeName = String(name || '').trim();
    const safePath = String(path || '').trim();

    if (safePath) {
        summary.classList.remove('alert-warning');
        summary.classList.add('alert-info');
        summary.setAttribute('title', safePath);
        summary.setAttribute('aria-label', safePath);
        summary.innerHTML = `
            <i class="fas fa-folder-open me-2"></i>
            <div class="flex-grow-1">
                <strong>Current Project:</strong> ${escapeHtml(safeName || safePath.split(/[\\/]/).pop() || 'Project')}
                <br><small class="text-muted" title="${escapeHtml(safePath)}">${escapeHtml(safePath)}</small>
            </div>
        `;
        return;
    }

    summary.classList.remove('alert-info');
    summary.classList.add('alert-warning');
    summary.removeAttribute('title');
    summary.removeAttribute('aria-label');
    summary.innerHTML = `
        <i class="fas fa-info-circle me-2"></i>
        <div class="flex-grow-1">
            <strong>No project loaded.</strong>
            <br><small class="text-muted">Load or create a project to make it your active working study.</small>
        </div>
    `;
}

function applyCurrentProject(project) {
    currentProjectPath = (project && project.path) ? String(project.path).trim() : '';
    currentProjectName = (project && project.name) ? String(project.name).trim() : '';
    updateProjectsActiveProjectSummary(currentProjectName, currentProjectPath);

    if (window.updateNavbarProject) {
        window.updateNavbarProject(currentProjectName, currentProjectPath);
        return;
    }

    setGlobalProjectState(currentProjectPath, currentProjectName);
}

function requestStudyMetadataSaveFromProjectBox() {
    const studyMetadataForm = document.getElementById('studyMetadataForm');
    if (!studyMetadataForm) return;

    const primarySubmitButton = document.getElementById('createProjectSubmitBtn');
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
    const saveButton = document.getElementById('projectBoxSaveBtn');
    if (!saveButton || saveButton.dataset.bound === '1') {
        return;
    }

    saveButton.dataset.bound = '1';
    saveButton.addEventListener('click', (event) => {
        event.preventDefault();
        requestStudyMetadataSaveFromProjectBox();
    });
}

function syncRecentProjectsToServer(list) {
    fetch('/api/projects/recent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projects: list })
    }).catch(() => {
        // localStorage remains fallback source
    });
}

function loadRecentProjectsFromServer() {
    fetch('/api/projects/recent')
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

if (projectsRoot) {
    currentProjectPath = projectsRoot.dataset.currentProjectPath || globalProjectPath || '';
    currentProjectName = projectsRoot.dataset.currentProjectName || globalProjectName || '';
} else {
    currentProjectPath = globalProjectPath;
    currentProjectName = globalProjectName;
}

setGlobalProjectState(currentProjectPath, currentProjectName);
updateProjectsActiveProjectSummary(currentProjectName, currentProjectPath);

window.addEventListener('prism-project-changed', function(event) {
    const eventState = event && event.detail ? event.detail : null;
    const fallbackState = getProjectStateSnapshot();
    const nextPath = eventState && typeof eventState.path === 'string' ? eventState.path.trim() : fallbackState.path;
    const nextName = eventState && typeof eventState.name === 'string' ? eventState.name.trim() : fallbackState.name;

    currentProjectPath = nextPath;
    currentProjectName = nextName;
});

export function getRecentProjects() {
    try {
        const raw = localStorage.getItem(recentProjectsKey);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
        console.warn('Could not read recent projects', err);
        return [];
    }
}

export function saveRecentProjects(list) {
    const limited = list.slice(0, 5);
    try {
        localStorage.setItem(recentProjectsKey, JSON.stringify(limited));
    } catch (err) {
        console.warn('Could not save recent projects', err);
    }
    syncRecentProjectsToServer(limited);
}

export function addRecentProject(name, path) {
    if (!path) return;
    const safeName = name && name.trim() ? name.trim() : path.split(/[\/]/).pop();
    const list = getRecentProjects().filter(p => p.path !== path);
    list.unshift({ name: safeName, path: path });
    recentProjectStatusCache.delete(path);
    saveRecentProjects(list);
    renderRecentProjects();
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

    const statusPromise = fetch('/api/projects/path-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
    })
        .then(response => response.json())
        .then(data => Boolean(data && data.success && data.available))
        .catch(() => false);

    recentProjectStatusCache.set(path, statusPromise);
    return statusPromise;
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
            .filter(({ available }) => available)
            .map(({ project }) => project);

        if (availableProjects.length !== list.length) {
            results
                .filter(({ available }) => !available)
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
        const safeLabel = escapeHtml(label);
        const safePath = escapeHtml(p.path || '');
        return `
            <button type="button" class="btn btn-outline-secondary btn-sm recent-project-btn" data-path="${safePath}" data-name="${safeLabel}" data-recent-id="${idx}" title="${safePath}">
                <i class="fas fa-clock me-1"></i>${safeLabel}
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
        const response = await fetch('/api/settings/global-library');
        const data = await response.json();
        if (data.success) {
            const libraryInput = document.getElementById('globalLibraryPath');
            libraryInput.value = data.global_template_library_path || '';
            if (data.default_library_path) {
                libraryInput.placeholder = `Default: ${data.default_library_path}`;
            }

            const recipesInput = document.getElementById('globalRecipesPath');
            recipesInput.value = data.global_recipes_path || '';

            updateLibraryInfoPanel(data.global_template_library_path || data.default_library_path, null);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function loadBackendMonitoringSetting() {
    const toggle = document.getElementById('backendMonitoringToggle');
    if (!toggle) return;

    try {
        const response = await fetch('/api/settings/backend-monitoring');
        const data = await response.json();
        if (data && data.success) {
            toggle.checked = Boolean(data.backend_monitoring);
        }
    } catch (error) {
        console.error('Error loading backend monitoring setting:', error);
    }
}

async function saveBackendMonitoringSetting(enabled) {
    const response = await fetch('/api/settings/backend-monitoring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backend_monitoring: Boolean(enabled) })
    });

    const data = await response.json();
    if (!response.ok || !data || !data.success) {
        throw new Error(data?.error || 'Failed to save backend monitoring setting');
    }

    return Boolean(data.backend_monitoring);
}

async function loadDedicatedTerminalSetting() {
    const toggle = document.getElementById('dedicatedTerminalToggle');
    if (!toggle) return;

    try {
        const response = await fetch('/api/settings/dedicated-terminal');
        const data = await response.json();
        if (data && data.success) {
            toggle.checked = Boolean(data.show_dedicated_terminal);
        }
    } catch (error) {
        console.error('Error loading dedicated terminal setting:', error);
    }
}

function shouldShowOpenValidationFromNavbar() {
    try {
        const params = new URLSearchParams(window.location.search || '');
        return params.get('show_open_validation') === '1';
    } catch (_) {
        return false;
    }
}

function clearShowOpenValidationFlagFromUrl() {
    try {
        const url = new URL(window.location.href);
        if (!url.searchParams.has('show_open_validation')) {
            return;
        }
        url.searchParams.delete('show_open_validation');
        const nextUrl = `${url.pathname}${url.search}${url.hash}`;
        window.history.replaceState({}, '', nextUrl);
    } catch (_) {
        // no-op: keep original URL if parsing fails
    }
}

async function maybeRunOpenValidationFromNavbar() {
    if (!shouldShowOpenValidationFromNavbar()) {
        return;
    }

    const path = String(currentProjectPath || '').trim();
    const existingPathInput = document.getElementById('existingPath');
    const openProjectForm = document.getElementById('openProjectForm');
    if (!path || !existingPathInput || !openProjectForm) {
        clearShowOpenValidationFlagFromUrl();
        return;
    }

    selectProjectType('open');
    existingPathInput.value = path;
    openProjectForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    clearShowOpenValidationFlagFromUrl();
}

async function saveDedicatedTerminalSetting(enabled) {
    const response = await fetch('/api/settings/dedicated-terminal', {
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
    if (!toggle) return;

    loadBackendMonitoringSetting();

    toggle.addEventListener('change', async () => {
        const desired = Boolean(toggle.checked);
        toggle.disabled = true;

        try {
            const persisted = await saveBackendMonitoringSetting(desired);
            toggle.checked = persisted;
        } catch (error) {
            console.error('Error saving backend monitoring setting:', error);
            toggle.checked = !desired;
            alert('Could not update backend monitoring setting.');
        } finally {
            toggle.disabled = false;
        }
    });
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
        const response = await fetch('/api/projects/library-path');
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

async function browseFolderWithFallback(options = {}) {
    try {
        const response = await fetch('/api/browse-folder');
        const data = await response.json();
        if (!response.ok || data.error) {
            throw new Error(data.error || 'Folder picker unavailable.');
        }
        return (data.path || '').trim();
    } catch (error) {
        console.warn('Native folder picker failed, falling back to in-app browser:', error);
        if (window.PrismFolderBrowser && typeof window.PrismFolderBrowser.open === 'function') {
            return window.PrismFolderBrowser.open({
                title: options.title || 'Select Folder',
                confirmLabel: options.confirmLabel || 'Select Folder',
                startPath: options.startPath || ''
            });
        }
        throw error;
    }
}

// Browse button for global library
const browseGlobalLibrary = document.getElementById('browseGlobalLibrary');
if (browseGlobalLibrary) {
    browseGlobalLibrary.addEventListener('click', async function() {
        try {
            const selectedPath = await browseFolderWithFallback({
                title: 'Select Global Survey Template Library',
                confirmLabel: 'Use This Folder',
                startPath: document.getElementById('globalLibraryPath')?.value || ''
            });
            if (selectedPath) {
                document.getElementById('globalLibraryPath').value = selectedPath;
            }
        } catch (error) {
            console.error('Browse error:', error);
            alert('Failed to open folder picker. Please enter path manually.');
        }
    });
}

// Browse button for global recipes
const browseGlobalRecipes = document.getElementById('browseGlobalRecipes');
if (browseGlobalRecipes) {
    browseGlobalRecipes.addEventListener('click', async function() {
        try {
            const selectedPath = await browseFolderWithFallback({
                title: 'Select Global Recipe Library',
                confirmLabel: 'Use This Folder',
                startPath: document.getElementById('globalRecipesPath')?.value || ''
            });
            if (selectedPath) {
                document.getElementById('globalRecipesPath').value = selectedPath;
            }
        } catch (error) {
            console.error('Browse error:', error);
            alert('Failed to open folder picker. Please enter path manually.');
        }
    });
}

// Save global settings
const globalSettingsForm = document.getElementById('globalSettingsForm');
if (globalSettingsForm) {
    globalSettingsForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const btn = this.querySelector('button[type="submit"]');
        const originalText = setButtonLoading(btn, true, 'Saving...');

        const libraryPath = document.getElementById('globalLibraryPath').value.trim();
        const recipesPath = document.getElementById('globalRecipesPath').value.trim();

        try {
            const response = await fetch('/api/settings/global-library', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    global_template_library_path: libraryPath,
                    global_recipes_path: recipesPath
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
                window.dispatchEvent(new CustomEvent('prism-library-settings-changed', {
                    detail: { global_library_path: document.getElementById('globalLibraryPath').value }
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
        const response = await fetch('/api/settings/global-library');
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
        const response = await fetch('/api/settings/global-library', {
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
                if (field.multiple) {
                    const hasSelection = Array.from(field.selectedOptions)
                        .some(option => option.value && option.value.trim());
                    if (hasSelection) return true;
                } else if (field.value && field.value.trim()) {
                    return true;
                }
                continue;
            }

            if (field.type === 'checkbox' || field.type === 'radio') {
                if (field.checked) return true;
                continue;
            }

            if ((field.value || '').trim()) {
                return true;
            }
        }
    }

    const ethicsChoice = document.getElementById('metadataEthicsApproved')?.value || '';
    const fundingChoice = document.getElementById('metadataFundingDeclared')?.value || '';
    return Boolean(ethicsChoice || fundingChoice);
}

function clearCurrentProjectForNewDraft() {
    currentProjectPath = '';
    currentProjectName = '';

    if (window.updateNavbarProject) {
        window.updateNavbarProject('', '');
    } else {
        setGlobalProjectState('', '');
    }

    // Keep backend session in sync to avoid accidental writes to a stale project.
    fetch('/api/projects/current', {
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
        const createResult = document.getElementById('createResult');
        if (createResult) {
            createResult.style.display = 'none';
            createResult.innerHTML = '';
        }
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

// Browse button for project location
const browseProjectPath = document.getElementById('browseProjectPath');
if (browseProjectPath) {
    browseProjectPath.addEventListener('click', async function() {
        try {
            const selectedPath = await browseFolderWithFallback({
                title: 'Select Project Location',
                confirmLabel: 'Use This Folder',
                startPath: document.getElementById('projectPath')?.value || ''
            });
            if (selectedPath) {
                const pathField = document.getElementById('projectPath');
                pathField.value = selectedPath;
                // Trigger validation after setting the value
                validateProjectField('projectPath');
                // Also dispatch change event in case other handlers are listening
                pathField.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } catch (error) {
            console.error('Browse error:', error);
            alert('Failed to open folder picker. Please enter path manually.');
        }
    });
}

// Browse button for existing project — uses the in-page file browser modal
const browseExistingPath = document.getElementById('browseExistingPath');
if (browseExistingPath) {
    // --- File browser modal state ---
    let _fbCurrentPath = null;
    let _fbSelectedProjectJson = null;

    const _fbModal = document.getElementById('projectFileBrowserModal');
    const _fbList = document.getElementById('fsBrowserList');
    const _fbCurrentPathEl = document.getElementById('fsBrowserCurrentPath');
    const _fbUpBtn = document.getElementById('fsBrowserUp');
    const _fbSelectBtn = document.getElementById('fsBrowserSelectBtn');
    const _fbSelectedHint = document.getElementById('fsBrowserSelectedHint');
    const _fbSelectedPathEl = document.getElementById('fsBrowserSelectedPath');

    async function _fbLoad(path) {
        _fbList.innerHTML = '<div class="d-flex justify-content-center align-items-center py-5 text-muted"><span><i class="fas fa-spinner fa-spin me-2"></i>Loading…</span></div>';
        _fbSelectedProjectJson = null;
        _fbSelectBtn.disabled = true;
        _fbSelectedHint.style.display = 'none';

        try {
            const url = path ? '/api/fs/browse?path=' + encodeURIComponent(path) : '/api/fs/browse';
            const res = await fetch(url);
            if (!res.ok) {
                _fbList.innerHTML = '<div class="text-danger px-3 py-3"><i class="fas fa-exclamation-triangle me-1"></i>Could not load directory.</div>';
                return;
            }
            const data = await res.json();
            _fbCurrentPath = data.path;
            _fbCurrentPathEl.textContent = data.path;
            _fbUpBtn.disabled = !data.parent;

            let html = '';

            // project.json row (highlighted) — at the top if present
            if (data.has_project_json) {
                html += `<div class="d-flex align-items-center px-3 py-2 border-bottom fb-project-json" style="cursor:pointer;background:#e8f5e9;" data-pjson="${_escHtml(data.project_json_path)}">
                    <i class="fas fa-file-code text-success me-2"></i>
                    <span class="fw-semibold text-success">project.json</span>
                    <span class="ms-auto badge bg-success">Select</span>
                </div>`;
                _fbSelectedProjectJson = data.project_json_path;
                _fbSelectBtn.disabled = false;
                _fbSelectedPathEl.textContent = data.project_json_path;
                _fbSelectedHint.style.display = '';
            }

            // Subdirectory rows
            if (data.dirs && data.dirs.length > 0) {
                data.dirs.forEach(dir => {
                    html += `<div class="d-flex align-items-center px-3 py-2 border-bottom fb-dir" style="cursor:pointer;" data-path="${_escHtml(dir.path)}">
                        <i class="fas fa-folder text-warning me-2"></i>
                        <span>${_escHtml(dir.name)}</span>
                        <i class="fas fa-chevron-right ms-auto text-muted small"></i>
                    </div>`;
                });
            }

            if (!html) {
                html = '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>Empty folder</div>';
            }

            _fbList.innerHTML = html;

            // Bind click on project.json row
            _fbList.querySelectorAll('.fb-project-json').forEach(el => {
                el.addEventListener('click', () => {
                    _fbSelectedProjectJson = el.dataset.pjson;
                    _fbSelectBtn.disabled = false;
                    _fbSelectedPathEl.textContent = _fbSelectedProjectJson;
                    _fbSelectedHint.style.display = '';
                });
            });

            // Bind click on directory rows
            _fbList.querySelectorAll('.fb-dir').forEach(el => {
                el.addEventListener('click', () => _fbLoad(el.dataset.path));
            });

        } catch (err) {
            console.error('File browser error:', err);
            _fbList.innerHTML = '<div class="text-danger px-3 py-3"><i class="fas fa-exclamation-triangle me-1"></i>Error loading directory.</div>';
        }
    }

    function _escHtml(str) {
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    browseExistingPath.addEventListener('click', function() {
        // Start from value already in the input (its parent dir), or home
        const existing = (document.getElementById('existingPath')?.value || '').trim();
        let startPath = null;
        if (existing) {
            // Try to start from the directory containing the current value
            const lastSep = Math.max(existing.lastIndexOf('/'), existing.lastIndexOf('\\'));
            if (lastSep > 0) startPath = existing.substring(0, lastSep);
        }
        _fbLoad(startPath || null);
        const modal = new bootstrap.Modal(_fbModal);
        modal.show();
    });

    if (_fbUpBtn) {
        _fbUpBtn.addEventListener('click', async function() {
            if (!_fbCurrentPath) return;
            const url = '/api/fs/browse?path=' + encodeURIComponent(_fbCurrentPath);
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();
            if (data.parent) _fbLoad(data.parent);
        });
    }

    if (_fbSelectBtn) {
        _fbSelectBtn.addEventListener('click', function() {
            if (_fbSelectedProjectJson) {
                const input = document.getElementById('existingPath');
                if (input) input.value = _fbSelectedProjectJson;
                bootstrap.Modal.getInstance(_fbModal)?.hide();
            }
        });
    }
}

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
    });
}

// Create Project Form
/**
 * Show a Bootstrap modal warning the user about missing required fields.
 * Returns a Promise<boolean> — true if the user confirmed, false if cancelled.
 */
function _showIncompleteMetadataModal(missingItems) {
    return new Promise((resolve) => {
        const existingModal = document.getElementById('_incompleteMetadataModal');
        if (existingModal) existingModal.remove();

        const listHtml = missingItems
            .map(item => `<li class="mb-1">${escapeHtml(item)}</li>`)
            .join('');

        const modalEl = document.createElement('div');
        modalEl.id = '_incompleteMetadataModal';
        modalEl.className = 'modal fade';
        modalEl.tabIndex = -1;
        modalEl.setAttribute('aria-modal', 'true');
        modalEl.setAttribute('role', 'dialog');
        modalEl.innerHTML = `
            <div class="modal-dialog modal-dialog-centered modal-lg">
                <div class="modal-content border-warning">
                    <div class="modal-header bg-warning bg-opacity-10 border-bottom border-warning">
                        <h5 class="modal-title">
                            <i class="fas fa-exclamation-triangle text-warning me-2"></i>
                            Required Fields Missing
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <p>The following required fields are still empty or invalid. The project will be created, but the metadata will be <strong>incomplete</strong>. You can fill in missing fields later.</p>
                        <ul class="text-danger mb-0 ps-3">${listHtml}</ul>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal" id="_incompleteModalCancel">
                            <i class="fas fa-arrow-left me-1"></i>Go back and fill fields
                        </button>
                        <button type="button" class="btn btn-warning" id="_incompleteModalConfirm">
                            <i class="fas fa-folder-plus me-1"></i>Create anyway (incomplete)
                        </button>
                    </div>
                </div>
            </div>`;

        document.body.appendChild(modalEl);

        const bsModal = new bootstrap.Modal(modalEl, { backdrop: 'static' });

        document.getElementById('_incompleteModalConfirm').addEventListener('click', () => {
            bsModal.hide();
            resolve(true);
        });
        document.getElementById('_incompleteModalCancel').addEventListener('click', () => {
            bsModal.hide();
            resolve(false);
        });
        modalEl.addEventListener('hidden.bs.modal', () => {
            modalEl.remove();
        }, { once: true });

        bsModal.show();
    });
}

const createProjectFormEl = document.getElementById('createProjectForm');
if (createProjectFormEl) {
    async function submitCreateProject(options = {}) {
        const forcePreliminary = Boolean(options.forcePreliminary);
        const triggerButton = options.triggerButton instanceof HTMLElement ? options.triggerButton : null;

        const projectName = document.getElementById('projectName').value.trim();
        const projectPath = document.getElementById('projectPath').value.trim();

        if (!projectPath) {
            alert('Please select a Project Location (output folder) before saving or creating the project.');
            const pathField = document.getElementById('projectPath');
            pathField?.focus();
            return;
        }

        const validation = validateAllMandatoryFields();
        if (!validation.isValid && !forcePreliminary) {
            const issues = [
                ...validation.emptyFields.map(f => `• ${f}`),
                ...(validation.invalidFields || []).map(f => `• ${f}`)
            ];
            const confirmed = await _showIncompleteMetadataModal(issues);
            if (!confirmed) return;
        }

        await validateDatasetDescriptionDraftLive();

        if (!/^[a-zA-Z0-9_-]+$/.test(projectName)) {
            alert('Invalid project name. Only letters, numbers, underscores and hyphens allowed.');
            return;
        }

        const createButtons = [
            document.getElementById('createProjectSubmitBtn'),
            document.getElementById('createProjectSubmitBtnTop')
        ].filter(Boolean);
        const preliminaryButtons = [
            document.getElementById('preliminaryCreateBtn'),
            document.getElementById('preliminaryCreateBtnTop')
        ].filter(Boolean);

        const fallbackCreateButton = createButtons[0] || null;
        const fallbackPreliminaryButton = preliminaryButtons[0] || null;
        const activeBtn = triggerButton || (forcePreliminary ? fallbackPreliminaryButton : fallbackCreateButton);
        const originalText = activeBtn ? setButtonLoading(activeBtn, true, forcePreliminary ? 'Saving...' : 'Creating...') : null;

        createButtons.forEach(btn => { btn.disabled = true; });
        preliminaryButtons.forEach(btn => { btn.disabled = true; });

        const separator = projectPath.includes('/') ? '/' : '\\';
        const fullPath = projectPath + separator + projectName;

        const data = {
            path: fullPath,
            name: projectName,
            authors: getCitationAuthorsList(),
            license: document.getElementById('metadataLicense').value,
            doi: document.getElementById('metadataDOI').value.trim(),
            keywords: document.getElementById('metadataKeywords').value.split(',').map(s => s.trim()).filter(s => s),
            acknowledgements: document.getElementById('metadataAcknowledgements').value.trim(),
            ethics_approvals: getEthicsApprovals(),
            how_to_acknowledge: document.getElementById('metadataHowToAcknowledge').value.trim(),
            funding: getFundingList(),
            references_and_links: document.getElementById('metadataReferences').value.split(',').map(s => s.trim()).filter(s => s),
            hed_version: document.getElementById('metadataHED').value.trim(),
            dataset_type: document.getElementById('metadataType').value,
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
                    return list.length ? list : undefined;
                })(),
                Location: (function() {
                    const list = getRecLocationList();
                    return list.length ? list : undefined;
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
            References: document.getElementById('smReferencesText').value || undefined
        };

        try {
            const response = await fetch('/api/projects/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            const resultDiv = document.getElementById('createResult');
            resultDiv.style.display = 'block';

            if (result.success) {
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>Project Created Successfully!</h5>
                        <p class="mb-2">${escapeHtml(result.message)}</p>
                        <p class="mb-2"><strong>Location:</strong> <code>${escapeHtml(result.path)}</code></p>
                        <p class="mb-0 text-success"><i class="fas fa-folder-open me-1"></i>This project is now your current working project.</p>
                        <hr>
                        <p class="mb-1"><strong>Created files:</strong></p>
                        <ul class="mb-2">
                            ${(result.created_files || []).map(f => `<li><code>${escapeHtml(f)}</code></li>`).join('')}
                        </ul>
                        <div class="mt-3 pt-3 border-top">
                            <h6 class="text-muted mb-2">Next Steps:</h6>
                            <div class="btn-group" role="group">
                                <a href="/converter" class="btn btn-sm btn-outline-success">
                                    <i class="fas fa-magic me-1"></i>Open Converter Tool
                                </a>
                            </div>
                            <small class="text-muted d-block mt-2">
                                Add subject folders and metadata before validating to avoid missing data errors.
                            </small>
                        </div>
                    </div>
                `;

                applyCurrentProject(result.current_project);
                try {
                    await saveProjectSchemaConfig();
                } catch (schemaError) {
                    console.error('Error saving project schema version after create:', schemaError);
                }
                addRecentProject(currentProjectName, currentProjectPath);
                showStudyMetadataCard();
                updateCreateProjectButton();
                showExportCard();
                showMethodsCard();
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${escapeHtml(result.error)}</p>
                    </div>
                `;
            }
        } catch (error) {
            document.getElementById('createResult').innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${escapeHtml(error.message)}</p>
                </div>
            `;
            document.getElementById('createResult').style.display = 'block';
        } finally {
            if (activeBtn) {
                setButtonLoading(activeBtn, false, null, originalText);
            }
            createButtons.forEach(btn => { btn.disabled = false; });
            preliminaryButtons.forEach(btn => { btn.disabled = false; });
        }
    }

    const createProjectSubmitBtn = document.getElementById('createProjectSubmitBtn');
    if (createProjectSubmitBtn) {
        createProjectSubmitBtn.addEventListener('click', (e) => {
            const createSection = document.getElementById('section-create');
            const createActive = createSection && createSection.classList.contains('active');
            if (!createActive && getProjectStateSnapshot().path) {
                e.preventDefault();
                const studyMetadataForm = document.getElementById('studyMetadataForm');
                if (studyMetadataForm && typeof studyMetadataForm.requestSubmit === 'function') {
                    studyMetadataForm.requestSubmit();
                } else if (studyMetadataForm) {
                    studyMetadataForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                }
                return;
            }
            e.preventDefault();
            submitCreateProject();
        });
    }

    const createProjectSubmitBtnTop = document.getElementById('createProjectSubmitBtnTop');
    if (createProjectSubmitBtnTop) {
        createProjectSubmitBtnTop.addEventListener('click', (e) => {
            e.preventDefault();
            submitCreateProject({ triggerButton: createProjectSubmitBtnTop });
        });
    }

    const preliminaryCreateBtn = document.getElementById('preliminaryCreateBtn');
    if (preliminaryCreateBtn) {
        preliminaryCreateBtn.addEventListener('click', (e) => {
            e.preventDefault();
            submitCreateProject({ forcePreliminary: true, triggerButton: preliminaryCreateBtn });
        });
    }

    const preliminaryCreateBtnTop = document.getElementById('preliminaryCreateBtnTop');
    if (preliminaryCreateBtnTop) {
        preliminaryCreateBtnTop.addEventListener('click', (e) => {
            e.preventDefault();
            submitCreateProject({ forcePreliminary: true, triggerButton: preliminaryCreateBtnTop });
        });
    }

    createProjectFormEl.addEventListener('submit', (e) => {
        e.preventDefault();
        submitCreateProject();
    });
}

// Open Project Form
const openProjectForm = document.getElementById('openProjectForm');
if (openProjectForm) {
    openProjectForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const btn = this.querySelector('button[type="submit"]');
        const originalText = setButtonLoading(btn, true, 'Validating...');

        const path = document.getElementById('existingPath').value.trim();
        if (!path) {
            const resultDiv = document.getElementById('validationResult');
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="validation-result invalid">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Selection Error</h5>
                    <p class="mb-0">Please provide a project folder or a <strong>project.json</strong> path.</p>
                </div>
            `;
            setButtonLoading(btn, false, null, originalText);
            return;
        }

        try {
            const response = await fetchWithApiFallback('/api/projects/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });
            const result = await response.json().catch(() => ({
                success: false,
                error: 'Server returned an invalid response while validating the project.'
            }));

            const resultDiv = document.getElementById('validationResult');
            resultDiv.style.display = 'block';

            if (!response.ok || !result.success) {
                resultDiv.innerHTML = `
                    <div class="validation-result invalid">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${escapeHtml(result.error || `Validation request failed (${response.status})`)}</p>
                    </div>
                `;
                return;
            }

            const stats = result.stats;
            const issues = result.issues;
            const fixableIssues = result.fixable_issues;

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
            }

            let html = `
                <div class="validation-result ${statusClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h5 class="mb-0"><i class="fas fa-${statusIcon} me-2"></i>${statusText}</h5>
                        ${stats.is_yoda ? '<span class="badge bg-info"><i class="fas fa-microchip me-1"></i>YODA Layout</span>' : ''}
                    </div>
                    <p class="text-success mb-3"><i class="fas fa-folder-open me-1"></i>This project is now your current working project and is shown in the navbar.</p>

                    <div class="alert alert-warning d-none py-2 mb-3" id="projectRequirementGapAlert" role="alert">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <span id="projectRequirementGapText"></span>
                    </div>

                    <div class="project-box-actions mb-3">
                        <div class="project-box-actions__copy">
                            <h6 class="mb-1">Project Metadata</h6>
                            <small class="text-muted d-block" id="projectBoxSaveHint">
                                <i class="fas fa-info-circle me-1"></i>Save metadata updates to project.json, dataset_description.json, and README.md.
                            </small>
                            <small class="text-muted d-block mt-1" id="projectBoxSaveStatus" aria-live="polite"></small>
                        </div>
                        <div class="project-box-actions__buttons">
                            <button type="button" class="btn btn-info" id="projectBoxSaveBtn">
                                <i class="fas fa-save me-2"></i>Save Changes to Project
                            </button>
                        </div>
                    </div>

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

            if (issues.length > 0) {
                html += `
                    <hr>
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="mb-0">Issues</h6>
                        ${fixableIssues.length > 0 ? `
                            <button class="btn btn-warning btn-sm" data-action="fix-all" data-path="${escapeHtml(path)}">
                                <i class="fas fa-wrench me-1"></i>Fix All (${fixableIssues.length})
                            </button>
                        ` : ''}
                    </div>
                    <div id="issuesList">
                `;

                issues.forEach(issue => {
                    html += `
                        <div class="issue-item ${issue.fixable ? 'fixable' : 'not-fixable'}">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${escapeHtml(issue.code)}</strong>: ${escapeHtml(issue.message)}
                                    ${issue.file_path ? `<br><small class="text-muted">${escapeHtml(issue.file_path)}</small>` : ''}
                                    ${issue.fix_hint ? `
                                        <div class="alert alert-info py-1 px-2 mt-2 mb-0 smaller d-flex align-items-center">
                                            <i class="fas fa-lightbulb me-2 text-warning"></i>
                                            <div><strong>Hint:</strong> ${escapeHtml(issue.fix_hint)}</div>
                                        </div>
                                    ` : ''}
                                </div>
                                ${issue.fixable ? `
                                    <button class="btn btn-sm btn-outline-warning" data-action="fix-issue" data-path="${escapeHtml(path)}" data-code="${escapeHtml(issue.code)}">
                                        <i class="fas fa-wrench"></i>
                                    </button>
                                ` : `
                                    <span class="badge bg-secondary">Manual fix required</span>
                                `}
                            </div>
                        </div>
                    `;
                });

                html += '</div>';
            }

            html += `
                <hr>
                <div class="mt-3">
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
            `;

            html += '</div>';
            resultDiv.innerHTML = html;

            applyCurrentProject(result.current_project);
            addRecentProject(currentProjectName, currentProjectPath);
            showStudyMetadataCard();
            bindProjectBoxActionButtons();
            updateCreateProjectButton();
            showExportCard();
            showMethodsCard();

        } catch (error) {
            document.getElementById('validationResult').innerHTML = `
                <div class="validation-result invalid">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${escapeHtml(error.message)}</p>
                </div>
            `;
            document.getElementById('validationResult').style.display = 'block';
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    });
}

export async function fixIssue(path, code) {
    try {
        const response = await fetch('/api/projects/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path, fix_codes: [code] })
        });
        const result = await response.json();

        if (result.success) {
            document.getElementById('openProjectForm').dispatchEvent(new Event('submit'));
        } else {
            alert('Error applying fix: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

export async function fixAllIssues(path) {
    try {
        const response = await fetch('/api/projects/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        const result = await response.json();

        if (result.success) {
            document.getElementById('openProjectForm').dispatchEvent(new Event('submit'));
        } else {
            alert('Error applying fixes: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

export async function clearCurrentProject() {
    try {
        await fetch('/api/projects/current', {
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

function initProjectsPage() {
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
        const tooltipTitle = `Type the full path to your <code>project.json</code> file (e.g., <code>${osExample}</code>), or click Browse to select it. <strong>Only project.json files are supported.</strong>`;

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
    maybeRunOpenValidationFromNavbar();

    if (currentProjectPath) {
        addRecentProject(currentProjectName, currentProjectPath);
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
            if (fixOneBtn) { fixIssue(fixOneBtn.dataset.path, fixOneBtn.dataset.code); }
        });
    }

    const recentList = document.getElementById('recentProjectsList');
    if (recentList) {
        recentList.addEventListener('click', (event) => {
            const btn = event.target.closest('.recent-project-btn');
            if (!btn) return;
            const path = btn.getAttribute('data-path');
            if (path) {
                document.getElementById('existingPath').value = path;
                selectProjectType('open');
                document.getElementById('openProjectForm').dispatchEvent(new Event('submit'));
            }
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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProjectsPage);
} else {
    initProjectsPage();
}

// Expose for inline handlers and legacy code
window.selectProjectType = selectProjectType;
window.fixIssue = fixIssue;
window.fixAllIssues = fixAllIssues;
window.clearCurrentProject = clearCurrentProject;
window.useDefaultLibrary = useDefaultLibrary;
window.clearGlobalLibrary = clearGlobalLibrary;

export { currentProjectPath, currentProjectName };
