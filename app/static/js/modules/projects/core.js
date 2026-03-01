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
    showStudyMetadataCard,
    showMethodsCard
} from './metadata.js';
import { showExportCard } from './export.js';

// Global state
let currentProjectPath = '';
let currentProjectName = '';
const recentProjectsKey = 'prism_recent_projects';
const beginnerHelpModeKey = 'prism_beginner_help_mode';
const recentProjectStatusCache = new Map();

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
            localStorage.setItem(recentProjectsKey, JSON.stringify(data.projects.slice(0, 6)));
            renderRecentProjects();
        })
        .catch(() => {
            // keep local fallback
        });
}

const projectsRoot = document.getElementById('projectsRoot');
const globalProjectPath = typeof window.currentProjectPath === 'string' ? window.currentProjectPath : '';
const globalProjectName = typeof window.currentProjectName === 'string' ? window.currentProjectName : '';

if (projectsRoot) {
    currentProjectPath = projectsRoot.dataset.currentProjectPath || globalProjectPath || '';
    currentProjectName = projectsRoot.dataset.currentProjectName || globalProjectName || '';
} else {
    currentProjectPath = globalProjectPath;
    currentProjectName = globalProjectName;
}

window.currentProjectPath = currentProjectPath;
window.currentProjectName = currentProjectName;

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
    const limited = list.slice(0, 6);
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

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeHintText(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
}

function getFieldHintText(field) {
    const parts = [];

    const placeholder = normalizeHintText(field.getAttribute('placeholder'));
    if (placeholder) {
        parts.push(`Example: ${placeholder}`);
    }

    const container = field.closest('.form-check, [class*="col-"], .mb-3, .card-body') || field.parentElement;
    if (container) {
        const helpNodes = container.querySelectorAll('small.text-muted, .form-text, small');
        helpNodes.forEach(node => {
            const text = normalizeHintText(node.textContent);
            if (text && !parts.includes(text)) {
                parts.push(text);
            }
        });
    }

    if (parts.length > 0) {
        return parts.slice(0, 2).join(' ');
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

            const hintText = getFieldHintText(field);
            if (!hintText) return;

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

function applyBeginnerHelpMode(enabled) {
    if (enabled) {
        renderInlineFieldHints();
    } else {
        clearInlineFieldHints();
    }
}

function initBeginnerHelpMode() {
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

// Load library info (both global and project)
export async function loadLibraryInfo() {
    try {
        const response = await fetch('/api/projects/library-path');
        const data = await response.json();

        const infoPanel = document.getElementById('libraryInfoPanel');
        infoPanel.style.display = 'block';

        const globalInfo = document.getElementById('globalLibraryInfo');
        if (data.global_library_path) {
            globalInfo.innerHTML = `<code class="small">${data.global_library_path}</code>`;
        } else {
            globalInfo.innerHTML = '<span class="text-muted">Not configured</span>';
        }

        const projectInfo = document.getElementById('projectLibraryInfo');
        if (data.success && data.project_library_path) {
            projectInfo.innerHTML = `<code class="small">${data.project_library_path}</code>`;
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
        globalInfo.innerHTML = `<code class="small">${globalPath}</code>`;
    } else {
        globalInfo.innerHTML = '<span class="text-muted">Not configured</span>';
    }
}

// Browse button for global library
const browseGlobalLibrary = document.getElementById('browseGlobalLibrary');
if (browseGlobalLibrary) {
    browseGlobalLibrary.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/browse-folder');
            const data = await response.json();
            if (data.path) {
                document.getElementById('globalLibraryPath').value = data.path;
            } else if (data.error) {
                alert('Folder picker unavailable: ' + data.error);
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
            const response = await fetch('/api/browse-folder');
            const data = await response.json();
            if (data.path) {
                document.getElementById('globalRecipesPath').value = data.path;
            } else if (data.error) {
                alert('Folder picker unavailable: ' + data.error);
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
                        <i class="fas fa-exclamation-circle me-2"></i>${result.error}
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
                    <i class="fas fa-exclamation-circle me-2"></i>${error.message}
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

    const createBtnContainer = document.getElementById('createProjectButtonContainer');
    if (createBtnContainer) {
        createBtnContainer.style.display = (type === 'create') ? 'block' : 'none';
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
        const projectNameError = document.getElementById('projectNameError');
        if (projectNameError) projectNameError.textContent = '';
        resetStudyMetadataForm();
        
        // Reset all badges to their original colors (REQUIRED=red, etc.)
        if (window.resetAllBadges) {
            window.resetAllBadges();
        }
    }

    setCurrentProjectBannerVisibility(type);

    showStudyMetadataCard();
}

// Browse button for project location
const browseProjectPath = document.getElementById('browseProjectPath');
if (browseProjectPath) {
    browseProjectPath.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/browse-folder');
            const data = await response.json();
            if (data.path) {
                const pathField = document.getElementById('projectPath');
                pathField.value = data.path;
                // Trigger validation after setting the value
                validateProjectField('projectPath');
                // Also dispatch change event in case other handlers are listening
                pathField.dispatchEvent(new Event('change', { bubbles: true }));
            } else if (data.error) {
                alert('Folder picker unavailable: ' + data.error);
            }
        } catch (error) {
            console.error('Browse error:', error);
            alert('Failed to open folder picker. Please enter path manually.');
        }
    });
}

// Browse button for existing project
const browseExistingPath = document.getElementById('browseExistingPath');
if (browseExistingPath) {
    browseExistingPath.addEventListener('click', async function() {
        try {
            const response = await fetch('/api/browse-file');

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const isWindows = navigator.platform.toUpperCase().indexOf('WIN') > -1;
                const example = isWindows ? "C:\\Users\\YourName\\MyProject\\project.json" : "/Users/YourName/MyProject/project.json";
                alert('File picker is not available.\n\nPlease manually type the full path to your project.json file in the field above.\n\nExample: ' + example);
                return;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                alert('File picker error: ' + (errorData.error || 'Please enter the path manually.'));
                return;
            }

            const data = await response.json();
            if (data.path) {
                document.getElementById('existingPath').value = data.path;
            } else if (data.error) {
                alert('File picker unavailable: ' + data.error + '\n\nPlease select only project.json files.');
            }
        } catch (error) {
            console.error('Browse error:', error);
            const isWindows = navigator.platform.toUpperCase().indexOf('WIN') > -1;
            const example = isWindows ? "C:\\Users\\YourName\\MyProject\\project.json" : "/Users/YourName/MyProject/project.json";
            alert('File picker unavailable.\n\nPlease manually type the full path to your project.json file.\n\nExample: ' + example);
        }
    });
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
            errorDiv.textContent = 'Only letters, numbers, underscores (-) and hyphens (_) allowed. No spaces!';
        } else {
            e.target.classList.remove('is-invalid');
            errorDiv.textContent = '';
        }
    });
}

// Create Project Form
const createProjectFormEl = document.getElementById('createProjectForm');
if (createProjectFormEl) {
    async function handleCreateProjectSubmit(e) {
        if (e) e.preventDefault();

        const createSection = document.getElementById('section-create');
        const createActive = createSection && createSection.classList.contains('active');
        if (!createActive && window.currentProjectPath) {
            const studyMetadataForm = document.getElementById('studyMetadataForm');
            if (studyMetadataForm && typeof studyMetadataForm.requestSubmit === 'function') {
                studyMetadataForm.requestSubmit();
            } else if (studyMetadataForm) {
                studyMetadataForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            }
            return;
        }

        const projectName = document.getElementById('projectName').value.trim();
        const projectPath = document.getElementById('projectPath').value.trim();

        const validation = validateAllMandatoryFields();
        if (!validation.isValid) {
            const issues = [
                ...validation.emptyFields.map(f => `- ${f}`),
                ...(validation.invalidFields || []).map(f => `- ${f}`)
            ].join('\n');
            alert(`Please fix the Study Metadata issues:\n\n${issues}`);
            return;
        }

        await validateDatasetDescriptionDraftLive();

        if (!/^[a-zA-Z0-9_-]+$/.test(projectName)) {
            alert('Invalid project name. Only letters, numbers, underscores and hyphens allowed.');
            return;
        }

        const btn = document.getElementById('createProjectSubmitBtn');
        const originalText = setButtonLoading(btn, true, 'Creating...');

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
            References: document.getElementById('smReferences').value || undefined
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
                        <p class="mb-2">${result.message}</p>
                        <p class="mb-2"><strong>Location:</strong> <code>${result.path}</code></p>
                        <p class="mb-0 text-success"><i class="fas fa-folder-open me-1"></i>This project is now your current working project.</p>
                        <hr>
                        <p class="mb-1"><strong>Created files:</strong></p>
                        <ul class="mb-2">
                            ${result.created_files.map(f => `<li><code>${f}</code></li>`).join('')}
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

                currentProjectPath = result.current_project.path;
                currentProjectName = result.current_project.name;
                window.currentProjectPath = currentProjectPath;
                window.currentProjectName = currentProjectName;
                addRecentProject(currentProjectName, currentProjectPath);
                if (window.updateNavbarProject) {
                    window.updateNavbarProject(currentProjectName, currentProjectPath);
                }
                showStudyMetadataCard();
                showExportCard();
                showMethodsCard();
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${result.error}</p>
                    </div>
                `;
            }
        } catch (error) {
            document.getElementById('createResult').innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
            document.getElementById('createResult').style.display = 'block';
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    }

    const createProjectSubmitBtn = document.getElementById('createProjectSubmitBtn');
    if (createProjectSubmitBtn) {
        createProjectSubmitBtn.addEventListener('click', handleCreateProjectSubmit);
    }

    createProjectFormEl.addEventListener('submit', handleCreateProjectSubmit);
}

// Open Project Form
const openProjectForm = document.getElementById('openProjectForm');
if (openProjectForm) {
    openProjectForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const btn = this.querySelector('button[type="submit"]');
        const originalText = setButtonLoading(btn, true, 'Validating...');

        const path = document.getElementById('existingPath').value;

        if (!path.toLowerCase().endsWith('project.json')) {
            const resultDiv = document.getElementById('validationResult');
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="validation-result invalid">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Selection Error</h5>
                    <p class="mb-0">You must select the <strong>project.json</strong> file. Folder selection is no longer supported for project loading.</p>
                </div>
            `;
            setButtonLoading(btn, false, null, originalText);
            return;
        }

        try {
            const response = await fetch('/api/projects/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });
            const result = await response.json();

            const resultDiv = document.getElementById('validationResult');
            resultDiv.style.display = 'block';

            if (!result.success) {
                resultDiv.innerHTML = `
                    <div class="validation-result invalid">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${result.error}</p>
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
                            <div class="stat-value">${stats.has_participants_tsv ? '✓' : '✗'}</div>
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
                            <button class="btn btn-warning btn-sm" onclick="fixAllIssues('${path}')">
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
                                    <strong>${issue.code}</strong>: ${issue.message}
                                    ${issue.file_path ? `<br><small class="text-muted">${issue.file_path}</small>` : ''}
                                    ${issue.fix_hint ? `
                                        <div class="alert alert-info py-1 px-2 mt-2 mb-0 smaller d-flex align-items-center">
                                            <i class="fas fa-lightbulb me-2 text-warning"></i>
                                            <div><strong>Hint:</strong> ${issue.fix_hint}</div>
                                        </div>
                                    ` : ''}
                                </div>
                                ${issue.fixable ? `
                                    <button class="btn btn-sm btn-outline-warning" onclick="fixIssue('${path}', '${issue.code}')">
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

            currentProjectPath = result.current_project.path;
            currentProjectName = result.current_project.name;
            window.currentProjectPath = currentProjectPath;
            window.currentProjectName = currentProjectName;
            addRecentProject(currentProjectName, currentProjectPath);
            if (window.updateNavbarProject) {
                window.updateNavbarProject(currentProjectName, currentProjectPath);
            }
            showStudyMetadataCard();
            showExportCard();
            showMethodsCard();

        } catch (error) {
            document.getElementById('validationResult').innerHTML = `
                <div class="validation-result invalid">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${error.message}</p>
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

document.addEventListener('DOMContentLoaded', function() {
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

    loadGlobalSettings();
    loadLibraryInfo();
    showStudyMetadataCard();
    showExportCard();
    showMethodsCard();
    renderRecentProjects();
    loadRecentProjectsFromServer();

    if (currentProjectPath) {
        addRecentProject(currentProjectName, currentProjectPath);
    }

    const sections = [
        { element: 'openProjectSection', chevron: 'openProjectChevron' },
        { element: 'studyMetadataSection', chevron: 'studyMetadataChevron' },
        { element: 'methodsSectionBody', chevron: 'methodsSectionChevron' },
        { element: 'participantsSection', chevron: 'participantsChevron' },
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
    }

    const cardOpen = document.getElementById('card-open');
    if (cardOpen) {
        cardOpen.addEventListener('click', () => selectProjectType('open'));
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
});

// Expose for inline handlers and legacy code
window.selectProjectType = selectProjectType;
window.fixIssue = fixIssue;
window.fixAllIssues = fixAllIssues;
window.clearCurrentProject = clearCurrentProject;
window.useDefaultLibrary = useDefaultLibrary;
window.clearGlobalLibrary = clearGlobalLibrary;

export { currentProjectPath, currentProjectName };
