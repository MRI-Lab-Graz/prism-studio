/**
 * Projects Module - Export
 * Project export and ANC (Austrian NeuroCloud) export functionality
 */

import { setButtonLoading } from './helpers.js';
import { getById, setHtml, hide, show, escapeHtml } from '../../shared/dom.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

const EXPORT_VALIDATION_MODES = new Set(['both', 'bids', 'prism', 'ignore']);
const EXPORT_REPOSITORY_MODES = new Set(['datalad_free', 'datalad_preserving', 'git_lfs']);
const ANNEX_AVAILABILITY_CACHE_TTL_MS = 15000;

let projectStructureLoadToken = 0;
let exportPreferencesLoadToken = 0;
let isApplyingExportPreferences = false;
let exportModuleInitialized = false;
let lastLoadedExportPreferences = getDefaultExportPreferences();
let lastExportPreferenceInheritance = {
    repository_mode: false,
    defacing_confirmation_mode: false,
};
let lastExportStructureStatus = {
    message: 'Load a project to view export filters.',
    tone: 'muted',
};
let lastAnnexAvailabilityScopeSignature = '';
let lastAnnexAvailabilitySummary = null;
let lastAnnexAvailabilityCheckedAtMs = 0;
let defacingPreflightLoadToken = 0;
let lastDefacingVariantSelection = null;

function getDefacingVariantCheckboxes() {
    return Array.from(document.querySelectorAll('.export-defacing-variant-filter'));
}

function getCheckedDefacingVariantKeys() {
    return getDefacingVariantCheckboxes()
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => String(checkbox.value || '').trim())
        .filter((value) => value.length > 0);
}

function getAllDefacingVariantKeys() {
    return getDefacingVariantCheckboxes()
        .map((checkbox) => String(checkbox.value || '').trim())
        .filter((value) => value.length > 0);
}

function setDefacingVariantFiltersChecked(checked) {
    const desiredState = Boolean(checked);
    getDefacingVariantCheckboxes().forEach((checkbox) => {
        checkbox.checked = desiredState;
    });
    const selected = getCheckedDefacingVariantKeys();
    lastDefacingVariantSelection = selected.length ? new Set(selected) : null;
}

function renderDefacingVariantFilterList(availableVariants) {
    const container = getById('exportDefacingVariantList');
    const checkAllBtn = getById('exportDefacingCheckAllVariants');
    const uncheckAllBtn = getById('exportDefacingUncheckAllVariants');
    if (!container) {
        return;
    }

    const variants = Array.isArray(availableVariants)
        ? availableVariants
            .filter((entry) => entry && typeof entry === 'object')
            .map((entry) => ({
                key: String(entry.key || '').trim(),
                label: String(entry.label || '').trim(),
                count: Number(entry.count || 0),
            }))
            .filter((entry) => entry.key.length > 0 && entry.label.length > 0)
        : [];

    if (!variants.length) {
        setHtml(container, '<span class="text-muted small">No anatomical scan variants detected.</span>');
        if (checkAllBtn) {
            checkAllBtn.disabled = true;
        }
        if (uncheckAllBtn) {
            uncheckAllBtn.disabled = true;
        }
        lastDefacingVariantSelection = null;
        return;
    }

    if (checkAllBtn) {
        checkAllBtn.disabled = false;
    }
    if (uncheckAllBtn) {
        uncheckAllBtn.disabled = false;
    }

    const existingSelection = new Set(getCheckedDefacingVariantKeys());
    const rememberedSelection = lastDefacingVariantSelection instanceof Set
        ? new Set(Array.from(lastDefacingVariantSelection))
        : null;
    const preferredSelection = existingSelection.size
        ? existingSelection
        : rememberedSelection;

    const hasPreferredMatch = preferredSelection
        ? variants.some((entry) => preferredSelection.has(entry.key))
        : false;

    const html = variants.map((entry, index) => {
        const inputId = `export_defacing_variant_${index}_${entry.key.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const checked = hasPreferredMatch ? preferredSelection.has(entry.key) : true;
        const countLabel = Number.isFinite(entry.count) && entry.count > 0
            ? ` <span class="text-muted">(${entry.count})</span>`
            : '';
        return `<div class="form-check form-check-sm">
            <input class="form-check-input export-defacing-variant-filter" type="checkbox" id="${inputId}" value="${escapeHtml(entry.key)}" ${checked ? 'checked' : ''}>
            <label class="form-check-label small" for="${inputId}">${escapeHtml(entry.label)}${countLabel}</label>
        </div>`;
    }).join('');

    setHtml(container, html);
    const selected = getCheckedDefacingVariantKeys();
    lastDefacingVariantSelection = selected.length ? new Set(selected) : null;
}

function getSelectedDefacingVariantPayload() {
    const allVariantKeys = getAllDefacingVariantKeys();
    if (!allVariantKeys.length) {
        return { selectedVariants: null, errorMessage: '' };
    }

    const selectedVariantKeys = getCheckedDefacingVariantKeys();
    if (!selectedVariantKeys.length) {
        return {
            selectedVariants: [],
            errorMessage: 'Select at least one anatomical scan variant for defacing checks.',
        };
    }

    if (selectedVariantKeys.length === allVariantKeys.length) {
        return { selectedVariants: null, errorMessage: '' };
    }

    return {
        selectedVariants: selectedVariantKeys,
        errorMessage: '',
    };
}

function resetDefacingUiState() {
    const controls = getById('exportDefacingControls');
    const preflightStatus = getById('exportDefacingPreflightStatus');
    const report = getById('exportDefacingReport');
    const checkBtn = getById('exportCheckDefacing');
    const runBtn = getById('exportRunDefacing');
    const variantList = getById('exportDefacingVariantList');
    const checkAllBtn = getById('exportDefacingCheckAllVariants');
    const uncheckAllBtn = getById('exportDefacingUncheckAllVariants');

    if (controls) {
        controls.style.display = 'none';
    }
    if (preflightStatus) {
        preflightStatus.style.display = 'none';
        setHtml(preflightStatus, '');
    }
    if (report) {
        report.style.display = 'none';
        setHtml(report, '');
    }
    if (checkBtn) {
        checkBtn.disabled = true;
    }
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.title = '';
    }
    if (variantList) {
        setHtml(variantList, '<span class="text-muted small">Loading anatomical scan variants...</span>');
    }
    if (checkAllBtn) {
        checkAllBtn.disabled = true;
    }
    if (uncheckAllBtn) {
        uncheckAllBtn.disabled = true;
    }
    lastDefacingVariantSelection = null;
}

function hasAnatomicalModality(modalities) {
    return Array.isArray(modalities)
        && modalities.some((item) => String(item || '').trim().toLowerCase() === 'anat');
}

function renderDefacingPreflightStatus(preflight) {
    const preflightStatus = getById('exportDefacingPreflightStatus');
    if (!preflightStatus) {
        return;
    }

    const message = String(preflight?.message || '').trim();
    if (!message) {
        preflightStatus.style.display = 'none';
        setHtml(preflightStatus, '');
        return;
    }

    const canRun = Boolean(preflight?.can_run_defacing);
    const cssClass = canRun ? 'alert alert-info py-1 mb-0' : 'alert alert-warning py-1 mb-0';
    setHtml(preflightStatus, `<div class="${cssClass}">${escapeHtml(message)}</div>`);
    preflightStatus.style.display = 'block';
}

async function fetchDefacingPreflight(projectPath) {
    const resp = await fetchWithApiFallback('/api/projects/export/defacing-preflight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath }),
    });
    const result = await resp.json().catch(() => ({ success: false, error: 'Invalid server response' }));
    if (!resp.ok || !result.success) {
        throw new Error(result.error || 'Could not check defacing prerequisites.');
    }
    return result;
}

async function refreshDefacingPreflight({ projectPath, modalities = [] }) {
    const requestToken = ++defacingPreflightLoadToken;
    const controls = getById('exportDefacingControls');
    const checkBtn = getById('exportCheckDefacing');
    const runBtn = getById('exportRunDefacing');

    const hasAnat = hasAnatomicalModality(modalities);
    if (!projectPath || !hasAnat) {
        resetDefacingUiState();
        return;
    }

    if (controls) {
        controls.style.display = 'block';
    }
    if (checkBtn) {
        checkBtn.disabled = false;
    }
    if (runBtn) {
        runBtn.disabled = true;
        runBtn.title = 'Checking defacing prerequisites...';
    }

    try {
        const preflight = await fetchDefacingPreflight(projectPath);
        if (requestToken !== defacingPreflightLoadToken) {
            return;
        }

        renderDefacingVariantFilterList(preflight.available_scan_variants || []);
        renderDefacingPreflightStatus(preflight);
        const canRun = Boolean(preflight.can_run_defacing);
        if (runBtn) {
            runBtn.disabled = !canRun;
            runBtn.title = canRun ? '' : String(preflight.message || 'Defacing prerequisites are not met.');
        }
    } catch (error) {
        if (requestToken !== defacingPreflightLoadToken) {
            return;
        }
        renderDefacingPreflightStatus({ message: error?.message || 'Could not check defacing prerequisites.', can_run_defacing: false });
        if (runBtn) {
            runBtn.disabled = true;
            runBtn.title = error?.message || 'Could not check defacing prerequisites.';
        }
    }
}

function getDefaultExportPreferences() {
    return {
        output_folder: '',
        exclude_subjects: [],
        exclude_sessions: [],
        exclude_modalities: [],
        exclude_acq: {},
        exclude_tasks: {},
        validation_mode: 'both',
        repository_mode: 'datalad_free',
        defacing_confirmation_mode: 'risk',
    };
}

function normalizeExportValidationMode(value) {
    const normalized = String(value || '').trim().toLowerCase();
    if (!normalized) {
        return 'both';
    }
    if (normalized === 'none') {
        return 'ignore';
    }
    return EXPORT_VALIDATION_MODES.has(normalized) ? normalized : 'both';
}

function getSelectedExportValidationMode() {
    const select = getById('exportValidationMode');
    return normalizeExportValidationMode(select?.value || 'both');
}

function normalizeExportRepositoryMode(value) {
    const normalized = String(value || '').trim().toLowerCase();
    return EXPORT_REPOSITORY_MODES.has(normalized) ? normalized : 'datalad_free';
}

function getSelectedExportRepositoryMode() {
    const select = getById('exportRepositoryMode');
    return normalizeExportRepositoryMode(select?.value || 'datalad_free');
}

function normalizeDefacingConfirmationMode(value) {
    const normalized = String(value || '').trim().toLowerCase();
    return normalized === 'always' ? 'always' : 'risk';
}

async function loadGlobalDefacingDefault() {
    const select = getById('exportDefacingGlobalDefaultMode');
    if (!select) return;

    try {
        const response = await fetchWithApiFallback('/api/settings/global-library');
        const data = await response.json();
        if (data && data.success) {
            select.value = normalizeDefacingConfirmationMode(data.export_defacing_confirmation_mode);
        }
    } catch (error) {
        console.error('Error loading global defacing confirmation default:', error);
    }
}

function shouldScrubAllMriTags() {
    return getById('exportScrubAllTags')?.checked !== false;
}

function getSelectedMriScrubGroups() {
    if (shouldScrubAllMriTags()) {
        return [];
    }

    return Array.from(document.querySelectorAll('.export-scrub-group'))
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => String(checkbox.value || '').trim())
        .filter((value) => value.length > 0);
}

function syncMriScrubControls() {
    const scrubEnabled = getById('exportScrubMriJson')?.checked || false;
    const scrubAll = shouldScrubAllMriTags();
    const groupContainer = getById('exportScrubGroupContainer');
    const groupCheckboxes = Array.from(document.querySelectorAll('.export-scrub-group'));

    if (groupContainer) {
        groupContainer.style.display = scrubEnabled && !scrubAll ? 'block' : 'none';
    }

    groupCheckboxes.forEach((checkbox) => {
        checkbox.disabled = !scrubEnabled || scrubAll;
    });
}

function buildExportRequestData(currentProjectPath, overrides = {}) {
    const scrubGroups = getSelectedMriScrubGroups();
    return {
        project_path: currentProjectPath,
        anonymize: getById('exportAnonymize')?.checked || false,
        mask_questions: getById('exportMaskQuestions')?.checked || false,
        scrub_mri_json: getById('exportScrubMriJson')?.checked || false,
        scrub_mri_json_groups: scrubGroups.length ? scrubGroups : null,
        export_phenotype_bridge: getById('exportPhenotypeBridge')?.checked || false,
        include_derivatives: getById('exportDerivatives')?.checked || false,
        include_sourcedata: getById('exportSourcedata')?.checked || false,
        include_code: getById('exportCode')?.checked || false,
        include_analysis: getById('exportAnalysis')?.checked || false,
        output_folder: (getById('exportOutputFolder')?.value || '').trim() || null,
        validation_mode: getSelectedExportValidationMode(),
        // Git LFS conversion only happens via the Folder Export button; ZIP export
        // just falls back to a DataLad-free package when "git_lfs" is selected.
        // The backend derives exclude_version_control_metadata from this mode
        // (see _resolve_exclude_version_control_metadata) so that rule lives
        // in exactly one place.
        repository_mode: getSelectedExportRepositoryMode(),
        exclude_subjects: _getUncheckedValues('export-subject-filter'),
        exclude_sessions: _getUncheckedValues('export-session-filter'),
        exclude_modalities: _getUncheckedValues('export-modality-filter'),
        exclude_acq: _getUncheckedAcqByModality(),
        exclude_tasks: _getUncheckedTaskByModality(),
        ...overrides,
    };
}

function renderDefacingTable(reportDiv, counts, report) {
    if (!reportDiv) {
        return;
    }

    if (!report || report.length === 0) {
        reportDiv.innerHTML = '<span class="text-muted small">No anatomical JSON sidecars found.</span>';
        reportDiv.style.display = 'block';
        return;
    }

    const rows = report.map((entry) => {
        const icon = entry.status === 'defaced' ? '✅' : entry.status === 'not_defaced' ? '⚠️' : '❓';
        return `<tr><td class="small text-break">${escapeHtml(entry.file || '')}</td><td>${icon} ${escapeHtml(String(entry.status || '').replace('_', ' '))}</td><td class="small text-muted">${escapeHtml(entry.reason || '')}</td></tr>`;
    }).join('');

    reportDiv.innerHTML = `
        <div class="small mb-1">
            <span class="badge bg-success me-1">${Number(counts?.defaced || 0)} defaced</span>
            <span class="badge bg-warning text-dark me-1">${Number(counts?.not_defaced || 0)} not defaced</span>
            <span class="badge bg-secondary">${Number(counts?.unknown || 0)} unknown</span>
        </div>
        <div style="max-height:200px;overflow-y:auto;">
          <table class="table table-sm table-bordered mb-0" style="font-size:0.8em;">
            <thead><tr><th>File</th><th>Status</th><th>Reason</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    reportDiv.style.display = 'block';
}

function buildFolderExportRequestData(currentProjectPath) {
    const scrubGroups = getSelectedMriScrubGroups();
    return {
        project_path: currentProjectPath,
        output_folder: (getById('exportOutputFolder')?.value || '').trim() || null,
        scrub_mri_json: getById('exportScrubMriJson')?.checked || false,
        scrub_mri_json_groups: scrubGroups.length ? scrubGroups : null,
        export_phenotype_bridge: getById('exportPhenotypeBridge')?.checked || false,
        include_derivatives: getById('exportDerivatives')?.checked || false,
        include_sourcedata: getById('exportSourcedata')?.checked || false,
        include_code: getById('exportCode')?.checked || false,
        include_analysis: getById('exportAnalysis')?.checked || false,
        exclude_subjects: _getUncheckedValues('export-subject-filter'),
        exclude_sessions: _getUncheckedValues('export-session-filter'),
        exclude_modalities: _getUncheckedValues('export-modality-filter'),
        exclude_acq: _getUncheckedAcqByModality(),
        exclude_tasks: _getUncheckedTaskByModality(),
        materialize_annex_content: true,
    };
}

function normalizeAnnexScopeStringArray(values) {
    if (!Array.isArray(values)) {
        return [];
    }
    return Array.from(new Set(values
        .map((value) => String(value || '').trim())
        .filter((value) => value.length > 0)))
        .sort((a, b) => a.localeCompare(b));
}

function normalizeAnnexScopeGroupedLabels(values) {
    if (!values || typeof values !== 'object') {
        return {};
    }

    return Object.keys(values)
        .map((key) => String(key || '').trim())
        .filter((key) => key.length > 0)
        .sort((a, b) => a.localeCompare(b))
        .reduce((accumulator, key) => {
            const normalizedLabels = normalizeAnnexScopeStringArray(values[key]);
            if (normalizedLabels.length) {
                accumulator[key] = normalizedLabels;
            }
            return accumulator;
        }, {});
}

function buildAnnexAvailabilityScopeSignature(projectPath) {
    const data = buildFolderExportRequestData(projectPath);
    return JSON.stringify({
        project_path: String(projectPath || '').trim(),
        include_derivatives: Boolean(data.include_derivatives),
        include_sourcedata: Boolean(data.include_sourcedata),
        include_code: Boolean(data.include_code),
        include_analysis: Boolean(data.include_analysis),
        exclude_subjects: normalizeAnnexScopeStringArray(data.exclude_subjects),
        exclude_sessions: normalizeAnnexScopeStringArray(data.exclude_sessions),
        exclude_modalities: normalizeAnnexScopeStringArray(data.exclude_modalities),
        exclude_acq: normalizeAnnexScopeGroupedLabels(data.exclude_acq),
        exclude_tasks: normalizeAnnexScopeGroupedLabels(data.exclude_tasks),
    });
}

function clearAnnexAvailabilityCache() {
    lastAnnexAvailabilityScopeSignature = '';
    lastAnnexAvailabilitySummary = null;
    lastAnnexAvailabilityCheckedAtMs = 0;
}

function resetAnnexAvailabilityReport() {
    clearAnnexAvailabilityCache();
    const reportDiv = getById('exportAnnexAvailabilityReport');
    if (!reportDiv) return;
    reportDiv.style.display = 'none';
    setHtml(reportDiv, '');
}

function getSelectedDefacingConfirmationMode() {
    const always = getById('exportDefacingConfirmAlways')?.checked || false;
    return always ? 'always' : 'risk';
}

function getExportValidationStatusText(validationMode) {
    const mode = normalizeExportValidationMode(validationMode);
    if (mode === 'ignore') {
        return 'Starting export...';
    }
    if (mode === 'bids') {
        return 'Running BIDS validation before export...';
    }
    if (mode === 'prism') {
        return 'Running PRISM validation before export...';
    }
    return 'Running PRISM + BIDS validation before export...';
}

function getExportRepositoryModeStatusSuffix(repositoryMode) {
    const mode = normalizeExportRepositoryMode(repositoryMode);
    if (mode === 'datalad_preserving') {
        return 'Repository metadata will be preserved.';
    }
    if (mode === 'git_lfs') {
        return 'Repository metadata will be removed (use Folder Export below for the Git LFS conversion).';
    }
    return 'Repository metadata will be removed.';
}

function getExportRepositoryModeSuccessNote(repositoryMode) {
    const mode = normalizeExportRepositoryMode(repositoryMode);
    if (mode === 'datalad_preserving') {
        return '<p class="mb-2">This ZIP keeps hidden Git/DataLad repository metadata for reproducible DataLad workflows.</p>';
    }
    if (mode === 'git_lfs') {
        return '<p class="mb-2">This ZIP excludes hidden Git/DataLad repository metadata. Git LFS conversion is not applied to ZIP exports — use the Folder Export button for a Git LFS-ready snapshot.</p>';
    }
    return '<p class="mb-2">This ZIP excludes hidden Git/DataLad repository metadata for a DataLad-free sharing package.</p>';
}

function isGitLfsExportModeSelected() {
    return getSelectedExportRepositoryMode() === 'git_lfs';
}

function updatePlainFolderExportButtonLabel() {
    const button = getById('plainFolderExportButton');
    if (!button) {
        return;
    }
    button.innerHTML = isGitLfsExportModeSelected()
        ? '<i class="fas fa-code-branch me-2"></i>Git LFS Export'
        : '<i class="fas fa-folder-open me-2"></i>Folder Export';
}

function normalizePreferenceStringArray(values) {
    if (!Array.isArray(values)) {
        return [];
    }

    const seen = new Set();
    const normalized = [];
    values.forEach(value => {
        const text = String(value || '').trim();
        if (!text || seen.has(text)) {
            return;
        }
        seen.add(text);
        normalized.push(text);
    });
    return normalized;
}

function normalizeGroupedPreferenceMap(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return {};
    }

    const normalized = {};
    Object.entries(value).forEach(([modality, entries]) => {
        const modalityKey = String(modality || '').trim();
        const normalizedEntries = normalizePreferenceStringArray(entries);
        if (!modalityKey || !normalizedEntries.length) {
            return;
        }
        normalized[modalityKey] = normalizedEntries;
    });
    return normalized;
}

function normalizeExportPreferences(preferences) {
    const normalized = getDefaultExportPreferences();
    if (!preferences || typeof preferences !== 'object') {
        return normalized;
    }

    normalized.output_folder = typeof preferences.output_folder === 'string'
        ? preferences.output_folder.trim()
        : '';
    normalized.exclude_subjects = normalizePreferenceStringArray(preferences.exclude_subjects);
    normalized.exclude_sessions = normalizePreferenceStringArray(preferences.exclude_sessions);
    normalized.exclude_modalities = normalizePreferenceStringArray(preferences.exclude_modalities);
    normalized.exclude_acq = normalizeGroupedPreferenceMap(preferences.exclude_acq);
    normalized.exclude_tasks = normalizeGroupedPreferenceMap(preferences.exclude_tasks);
    normalized.validation_mode = normalizeExportValidationMode(preferences.validation_mode);
    normalized.repository_mode = normalizeExportRepositoryMode(preferences.repository_mode);
    normalized.defacing_confirmation_mode = normalizeDefacingConfirmationMode(preferences.defacing_confirmation_mode);
    return normalized;
}

function formatExcludedCount(count, singular, plural = `${singular}s`) {
    return `${count} ${count === 1 ? singular : plural}`;
}

function countExcludedGroupedLabels(groupedValues) {
    return Object.values(groupedValues || {}).reduce((total, values) => {
        return total + (Array.isArray(values) ? values.length : 0);
    }, 0);
}

function countExcludedSubfilterLabels(excludedAcq, excludedTasks) {
    return countExcludedGroupedLabels(excludedAcq) + countExcludedGroupedLabels(excludedTasks);
}

function setExportChipState(chipId, text, tone = 'neutral') {
    const chip = getById(chipId);
    if (!chip) return;
    chip.textContent = text;
    chip.className = `export-filter-chip export-filter-chip--${tone}`;
}

function setBadge(id, text, tone = 'secondary') {
    const badge = getById(id);
    if (!badge) return;
    badge.textContent = text;
    badge.className = `badge bg-${tone} ms-2`;
}

/**
 * Reflect the Anonymization accordion's checkbox state in the always-visible
 * export snapshot and in a badge on the accordion header itself, so a user
 * who never opens that section still knows whether it's on.
 */
function updateAnonymizationStatus() {
    const summaryEl = getById('exportAnonymizationSummary');
    const detailEl = getById('exportAnonymizationDetail');
    if (!summaryEl && !detailEl && !getById('exportAnonymizationHeaderBadge')) return;

    const anonymize = getById('exportAnonymize')?.checked || false;
    const maskQuestions = getById('exportMaskQuestions')?.checked || false;
    const scrubMri = getById('exportScrubMriJson')?.checked || false;
    const defaceScans = getById('exportDefaceAnatomicalScans')?.checked || false;
    const phenotypeBridge = getById('exportPhenotypeBridge')?.checked || false;

    const activeLabels = [];
    if (maskQuestions) activeLabels.push('question text masked');
    if (scrubMri) activeLabels.push('MRI JSON scrubbed');
    if (defaceScans) activeLabels.push('anatomical scans defaced');
    if (phenotypeBridge) activeLabels.push('phenotype bridge added');

    let summaryText;
    let detailText;
    let badgeText;
    let badgeTone;

    if (!anonymize) {
        summaryText = activeLabels.length
            ? `IDs NOT randomized (${activeLabels.join(', ')})`
            : 'No anonymization applied';
        detailText = 'Participant IDs will be exported as-is. Enable "Randomize Participant IDs" below before sharing publicly.';
        badgeText = 'IDs not randomized';
        badgeTone = 'danger';
    } else if (!activeLabels.length) {
        summaryText = 'Randomize Participant IDs only';
        detailText = 'Question text, MRI sidecars, and scan defacing are exported unchanged. Open Anonymization below to enable more protections.';
        badgeText = 'Randomize IDs only';
        badgeTone = 'secondary';
    } else {
        const allLabels = ['IDs randomized', ...activeLabels];
        summaryText = allLabels.join(', ');
        detailText = `${allLabels.length} anonymization protections are active. Open Anonymization below to review.`;
        badgeText = `${allLabels.length} protections on`;
        badgeTone = 'info';
    }

    if (summaryEl) summaryEl.textContent = summaryText;
    if (detailEl) detailEl.textContent = detailText;
    setBadge('exportAnonymizationHeaderBadge', badgeText, badgeTone);
}

/**
 * Badge on the "Export Content & Filters" accordion header summarizing
 * whether extra top-level folders are included and whether any
 * subject/session/modality/task filters are narrowing the export.
 */
function updateContentFiltersStatusBadge() {
    if (!getById('exportContentHeaderBadge')) return;

    const extraFolders = [
        getById('exportDerivatives')?.checked && 'derivatives',
        getById('exportSourcedata')?.checked && 'sourcedata',
        getById('exportCode')?.checked && 'code',
        getById('exportAnalysis')?.checked && 'analysis',
    ].filter(Boolean);

    const hasExclusions = Boolean(
        _getUncheckedValues('export-subject-filter').length
        || _getUncheckedValues('export-session-filter').length
        || _getUncheckedValues('export-modality-filter').length
        || countExcludedSubfilterLabels(_getUncheckedAcqByModality(), _getUncheckedTaskByModality())
    );

    if (!extraFolders.length && !hasExclusions) {
        setBadge('exportContentHeaderBadge', 'Default scope', 'secondary');
        return;
    }

    const parts = [];
    if (extraFolders.length) parts.push(`+${extraFolders.join(', ')}`);
    if (hasExclusions) parts.push('filters active');
    setBadge('exportContentHeaderBadge', parts.join(' · '), 'info');
}

function updateOpenmindsStatusBadge() {
    if (!getById('exportOpenmindsHeaderBadge')) return;
    const enabled = getById('openmindsEnableExport')?.checked || false;
    setBadge('exportOpenmindsHeaderBadge', enabled ? 'Enabled' : 'Off', enabled ? 'success' : 'secondary');
}

function updateExportSnapshotUi() {
    const currentProjectPath = resolveCurrentProjectPath();
    const scopeSummary = getById('exportScopeSummary');
    const scopeDetail = getById('exportScopeDetail');
    const destinationSummary = getById('exportDestinationSummary');
    const destinationDetail = getById('exportDestinationDetail');
    const preferenceSummary = getById('exportPreferenceSummary');
    const preferenceDetail = getById('exportPreferenceDetail');
    const outputFolderInput = getById('exportOutputFolder');
    const outputFolderHelp = getById('exportOutputFolderHelp');

    const outputFolder = (outputFolderInput?.value || '').trim();
    const subjectCount = document.querySelectorAll('.export-subject-filter').length;
    const sessionCount = document.querySelectorAll('.export-session-filter').length;
    const modalityCount = document.querySelectorAll('.export-modality-filter').length;
    const excludedSubjects = _getUncheckedValues('export-subject-filter');
    const excludedSessions = _getUncheckedValues('export-session-filter');
    const excludedModalities = _getUncheckedValues('export-modality-filter');
    const excludedAcq = _getUncheckedAcqByModality();
    const excludedTasks = _getUncheckedTaskByModality();
    const excludedSubfilterCount = countExcludedSubfilterLabels(excludedAcq, excludedTasks);

    if (scopeSummary && scopeDetail) {
        if (!currentProjectPath) {
            scopeSummary.textContent = 'Load a project to unlock export';
            scopeDetail.textContent = 'Export choices appear once a project is your active working study.';
        } else if (!subjectCount && !sessionCount && !modalityCount) {
            scopeSummary.textContent = lastExportStructureStatus.tone === 'warning'
                ? 'Export filters need attention'
                : 'Preparing export scope';
            scopeDetail.textContent = lastExportStructureStatus.message;
        } else if (!excludedSubjects.length && !excludedSessions.length && !excludedModalities.length && !excludedSubfilterCount) {
            scopeSummary.textContent = 'Everything currently included';
            scopeDetail.textContent = 'Uncheck subjects, sessions, modalities, or task/acquisition labels below to narrow the export.';
        } else {
            scopeSummary.textContent = 'Custom export scope active';
            scopeDetail.textContent = [
                excludedSubjects.length
                    ? `${formatExcludedCount(excludedSubjects.length, 'subject')} excluded`
                    : 'all subjects included',
                excludedSessions.length
                    ? `${formatExcludedCount(excludedSessions.length, 'session')} excluded`
                    : 'all sessions included',
                excludedModalities.length
                    ? `${formatExcludedCount(excludedModalities.length, 'modality')} excluded`
                    : 'all modalities included',
                excludedSubfilterCount
                    ? `${formatExcludedCount(excludedSubfilterCount, 'task/acquisition label')} excluded`
                    : 'all task/acquisition labels included',
            ].join(' | ');
        }
    }

    if (destinationSummary && destinationDetail) {
        if (outputFolder) {
            destinationSummary.textContent = outputFolder;
            destinationDetail.textContent = 'Saved for this project and reused automatically next time.';
        } else {
            destinationSummary.textContent = 'Use the project parent folder';
            destinationDetail.textContent = 'Leave the folder blank to keep the default save location.';
        }
    }

    if (preferenceSummary && preferenceDetail) {
        if (currentProjectPath) {
            const defacingMode = normalizeDefacingConfirmationMode(
                lastLoadedExportPreferences.defacing_confirmation_mode
            );
            const repositoryMode = normalizeExportRepositoryMode(
                lastLoadedExportPreferences.repository_mode
            );
            const defacingModeLabel = defacingMode === 'always'
                ? 'always ask before MRI scrub export'
                : 'ask only on detected defacing risk';
            const repositoryModeLabel = repositoryMode === 'datalad_preserving'
                ? 'DataLad-preserving ZIP mode'
                : 'DataLad-free ZIP mode';
            const defacingModeSource = lastExportPreferenceInheritance.defacing_confirmation_mode
                ? 'inherited from Global Settings'
                : 'saved in project export preferences';
            const repositoryModeSource = lastExportPreferenceInheritance.repository_mode
                ? 'using default export mode'
                : 'saved in project export preferences';
            const hasInheritedPreference = Boolean(
                lastExportPreferenceInheritance.defacing_confirmation_mode
                || lastExportPreferenceInheritance.repository_mode
            );

            preferenceSummary.textContent = hasInheritedPreference
                ? 'Project + global defaults'
                : 'Saved per project';
            preferenceDetail.textContent = `Output folder and export filters are remembered automatically. ZIP repository mode: ${repositoryModeLabel} (${repositoryModeSource}). Defacing confirmation: ${defacingModeLabel} (${defacingModeSource}).`;
        } else {
            preferenceSummary.textContent = 'Inactive until a project is loaded';
            preferenceDetail.textContent = 'Load or create a project before export preferences can be restored.';
        }
    }

    const resetDefacingModeBtn = getById('exportDefacingUseGlobalDefault');
    if (resetDefacingModeBtn) {
        resetDefacingModeBtn.disabled = !currentProjectPath || lastExportPreferenceInheritance.defacing_confirmation_mode;
    }

    if (outputFolderHelp) {
        outputFolderHelp.textContent = outputFolder
            ? 'This folder is remembered for the current project and reused automatically.'
            : 'Leave blank to use the project parent folder. Any folder you choose here is remembered for this project.';
    }

    updateAnonymizationStatus();
    updateContentFiltersStatusBadge();
    updateOpenmindsStatusBadge();

    if (!currentProjectPath) {
        setExportChipState('exportSessionsChip', 'Sessions: waiting for active project', 'warning');
        setExportChipState('exportModalitiesChip', 'Modalities: waiting for active project', 'warning');
        setExportChipState('exportAcqChip', 'Task/acquisition labels: waiting for active project', 'warning');
        return;
    }

    if (!subjectCount && !sessionCount && !modalityCount) {
        const tone = lastExportStructureStatus.tone === 'warning' ? 'warning' : 'neutral';
        const waitingLabel = lastExportStructureStatus.tone === 'warning'
            ? 'structure unavailable'
            : 'waiting for project structure';
        setExportChipState('exportSessionsChip', `Sessions: ${waitingLabel}`, tone);
        setExportChipState('exportModalitiesChip', `Modalities: ${waitingLabel}`, tone);
        setExportChipState('exportAcqChip', `Task/acquisition labels: ${waitingLabel}`, tone);
        return;
    }

    setExportChipState(
        'exportSessionsChip',
        excludedSessions.length
            ? `Sessions: ${formatExcludedCount(excludedSessions.length, 'session')} excluded`
            : 'Sessions: all included',
        excludedSessions.length ? 'active' : 'neutral'
    );
    setExportChipState(
        'exportModalitiesChip',
        excludedModalities.length
            ? `Modalities: ${formatExcludedCount(excludedModalities.length, 'modality')} excluded`
            : 'Modalities: all included',
        excludedModalities.length ? 'active' : 'neutral'
    );
    setExportChipState(
        'exportAcqChip',
        excludedSubfilterCount
            ? `Task/acquisition labels: ${formatExcludedCount(excludedSubfilterCount, 'label')} excluded`
            : 'Task/acquisition labels: all included',
        excludedSubfilterCount ? 'active' : 'neutral'
    );
}

async function fetchDefacingSummary(projectPath) {
    const variantSelection = getSelectedDefacingVariantPayload();
    if (variantSelection.errorMessage) {
        throw new Error(variantSelection.errorMessage);
    }

    const requestPayload = {
        project_path: projectPath,
        exclude_subjects: _getUncheckedValues('export-subject-filter'),
        exclude_sessions: _getUncheckedValues('export-session-filter'),
    };
    if (Array.isArray(variantSelection.selectedVariants)) {
        requestPayload.selected_variants = variantSelection.selectedVariants;
    }

    const resp = await fetchWithApiFallback('/api/projects/export/defacing-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload)
    });
    const result = await resp.json();
    if (!resp.ok || result.error) {
        throw new Error(result.error || 'Error fetching defacing report');
    }

    const counts = result.counts || { defaced: 0, not_defaced: 0, unknown: 0 };
    const notDefacedCount = Number(counts.not_defaced || 0);
    const unknownCount = Number(counts.unknown || 0);
    return {
        counts,
        report: Array.isArray(result.report) ? result.report : [],
        riskCount: notDefacedCount + unknownCount,
    };
}

async function fetchAnnexAvailabilitySummary(projectPath) {
    const data = buildFolderExportRequestData(projectPath);
    const resp = await fetchWithApiFallback('/api/projects/export/annex-availability', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    const result = await resp.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
    if (!resp.ok || !result.success) {
        throw new Error(result.error || result.message || 'Could not check annex availability.');
    }
    return result;
}

async function ensureAnnexAvailabilitySummary(projectPath, { force = false } = {}) {
    const scopeSignature = buildAnnexAvailabilityScopeSignature(projectPath);
    const cacheAgeMs = Date.now() - lastAnnexAvailabilityCheckedAtMs;
    const hasFreshCache = Number.isFinite(cacheAgeMs)
        && lastAnnexAvailabilityCheckedAtMs > 0
        && cacheAgeMs >= 0
        && cacheAgeMs < ANNEX_AVAILABILITY_CACHE_TTL_MS;

    if (
        !force
        && hasFreshCache
        && lastAnnexAvailabilitySummary
        && lastAnnexAvailabilityScopeSignature === scopeSignature
    ) {
        return lastAnnexAvailabilitySummary;
    }

    const summary = await fetchAnnexAvailabilitySummary(projectPath);
    lastAnnexAvailabilityScopeSignature = scopeSignature;
    lastAnnexAvailabilitySummary = summary;
    lastAnnexAvailabilityCheckedAtMs = Date.now();
    return summary;
}

function renderAnnexAvailabilityReport(summary) {
    const reportDiv = getById('exportAnnexAvailabilityReport');
    if (!reportDiv) {
        return;
    }

    const missingCount = Number(summary?.missing_files_count || 0);
    const preview = Array.isArray(summary?.missing_files_preview)
        ? summary.missing_files_preview
            .filter((value) => typeof value === 'string' && value.trim())
            .slice(0, 8)
        : [];
    const previewRoot = typeof summary?.missing_files_preview_root === 'string'
        ? summary.missing_files_preview_root.trim()
        : '';
    const hintCommand = typeof summary?.hint_command === 'string'
        ? summary.hint_command.trim()
        : '';
    const message = typeof summary?.message === 'string'
        ? summary.message.trim()
        : '';

    if (missingCount > 0) {
        const previewHtml = preview.length
            ? `<details class="mt-2"><summary>Missing files preview</summary>${previewRoot ? `<p class="small text-muted mb-1">Relative to: <code class="user-select-all">${escapeHtml(previewRoot)}</code></p>` : ''}<ul class="mb-0">${preview.map((value) => `<li><code class="user-select-all">${escapeHtml(value)}</code></li>`).join('')}</ul></details>`
            : '';
        const hintHtml = hintCommand
            ? `<p class="mb-0 small">Try: <code class="user-select-all">${escapeHtml(hintCommand)}</code></p>`
            : '';
        setHtml(reportDiv, `<div class="alert alert-warning py-2 mb-0"><strong>Annex availability check:</strong> ${escapeHtml(message || `Detected ${missingCount} missing local file(s).`)}${previewHtml}${hintHtml}</div>`);
    } else {
        const alertClass = summary?.is_datalad_dataset ? 'alert-success' : 'alert-info';
        setHtml(reportDiv, `<div class="alert ${alertClass} py-2 mb-0">${escapeHtml(message || 'No missing local files detected for the current export scope.')}</div>`);
    }

    reportDiv.style.display = 'block';
}

function renderAnnexAvailabilityError(error) {
    const reportDiv = getById('exportAnnexAvailabilityReport');
    if (!reportDiv) {
        return;
    }
    setHtml(reportDiv, `<div class="alert alert-danger py-2 mb-0">${escapeHtml(error?.message || 'Could not check annex availability.')}</div>`);
    reportDiv.style.display = 'block';
}

function getExportFilterCheckbox(className, value) {
    return Array.from(document.querySelectorAll(`.${className}`))
        .find(checkbox => checkbox.value === value) || null;
}

function applyExportPreferencesToFilters(preferences = lastLoadedExportPreferences) {
    const normalized = normalizeExportPreferences(preferences);
    lastLoadedExportPreferences = normalized;

    isApplyingExportPreferences = true;

    document.querySelectorAll('.export-subject-filter').forEach(checkbox => {
        checkbox.checked = !normalized.exclude_subjects.includes(checkbox.value);
    });

    document.querySelectorAll('.export-session-filter').forEach(checkbox => {
        checkbox.checked = !normalized.exclude_sessions.includes(checkbox.value);
    });

    document.querySelectorAll('.export-modality-filter').forEach(checkbox => {
        checkbox.checked = !normalized.exclude_modalities.includes(checkbox.value);
        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
    });

    document.querySelectorAll('.export-acq-filter').forEach(checkbox => {
        const modality = String(checkbox.dataset.modality || '').trim();
        const filterKind = String(checkbox.dataset.filterKind || 'acq').trim();
        const modalityCheckbox = getExportFilterCheckbox('export-modality-filter', modality);
        if (modalityCheckbox && !modalityCheckbox.checked) {
            return;
        }

        const excludedEntries = filterKind === 'task'
            ? (normalized.exclude_tasks[modality] || [])
            : (normalized.exclude_acq[modality] || []);
        checkbox.checked = !excludedEntries.includes(checkbox.value);
    });

    syncAllModalitySubfilterStates();

    const validationModeSelect = getById('exportValidationMode');
    if (validationModeSelect) {
        validationModeSelect.value = normalized.validation_mode;
    }

    const repositoryModeSelect = getById('exportRepositoryMode');
    if (repositoryModeSelect) {
        repositoryModeSelect.value = normalized.repository_mode;
    }
    updatePlainFolderExportButtonLabel();

    const defacingConfirmAlwaysToggle = getById('exportDefacingConfirmAlways');
    if (defacingConfirmAlwaysToggle) {
        defacingConfirmAlwaysToggle.checked = normalized.defacing_confirmation_mode === 'always';
    }

    isApplyingExportPreferences = false;
    updateExportSnapshotUi();
}

function saveExportPreferencesPatch(preferencesPatch) {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        return Promise.resolve();
    }

    lastLoadedExportPreferences = normalizeExportPreferences({
        ...lastLoadedExportPreferences,
        ...preferencesPatch,
    });
    if (Object.prototype.hasOwnProperty.call(preferencesPatch, 'defacing_confirmation_mode')) {
        lastExportPreferenceInheritance = {
            ...lastExportPreferenceInheritance,
            defacing_confirmation_mode: false,
        };
    }
    if (Object.prototype.hasOwnProperty.call(preferencesPatch, 'repository_mode')) {
        lastExportPreferenceInheritance = {
            ...lastExportPreferenceInheritance,
            repository_mode: false,
        };
    }
    updateExportSnapshotUi();

    return fetchWithApiFallback('/api/projects/preferences/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath, preferences: preferencesPatch }),
    }).catch(error => {
        console.warn('Could not save export preferences:', error);
    });
}

function renderProjectStructureStatus(message, tone = 'muted') {
    lastExportStructureStatus = { message, tone };
    const cssClass = tone === 'warning' ? 'text-warning' : 'text-muted';
    const markup = `<span class="${cssClass} small">${escapeHtml(message)}</span>`;
    setHtml(getById('exportSubjectList'), markup);
    setHtml(getById('exportSessionList'), markup);
    setHtml(getById('exportModalityList'), markup);
    updateExportSnapshotUi();
}

/**
 * Show/hide export card based on current project
 * Uses centralized project state (with global fallback)
 */
export function showExportCard() {
    const card = getById('exportProjectCard');
    if (!card) return;

    const outputFolderInput = getById('exportOutputFolder');
    lastLoadedExportPreferences = getDefaultExportPreferences();
    lastExportPreferenceInheritance = {
        repository_mode: false,
        defacing_confirmation_mode: false,
    };
    lastExportStructureStatus = {
        message: 'Load a project to view export filters.',
        tone: 'muted',
    };

    if (resolveCurrentProjectPath()) {
        if (outputFolderInput) {
            outputFolderInput.value = '';
        }
        resetAnnexAvailabilityReport();
        resetDefacingUiState();
        show(card);
        loadProjectStructure();
        loadExportPreferences();
    } else {
        projectStructureLoadToken += 1;
        exportPreferencesLoadToken += 1;
        if (outputFolderInput) {
            outputFolderInput.value = '';
        }
        resetAnnexAvailabilityReport();
        resetDefacingUiState();
        renderProjectStructureStatus('Load a project to view export filters.');
        hide(card);
    }

    updateExportSnapshotUi();
}

/**
 * Load available sessions and modalities for the current project and render checkboxes.
 */
export async function loadProjectStructure() {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) {
        projectStructureLoadToken += 1;
        resetDefacingUiState();
        renderProjectStructureStatus('Load a project to view export filters.');
        return;
    }

    const requestToken = ++projectStructureLoadToken;
    renderProjectStructureStatus('Loading current project structure...');

    try {
        const resp = await fetchWithApiFallback('/api/projects/export/structure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_path: projectPath }),
        });
        if (requestToken !== projectStructureLoadToken) return;
        if (!resp.ok) {
            resetDefacingUiState();
            renderProjectStructureStatus('Could not load current project structure.', 'warning');
            return;
        }
        const data = await resp.json();
        if (requestToken !== projectStructureLoadToken) return;
        if (!data.success) {
            resetDefacingUiState();
            renderProjectStructureStatus('Could not load current project structure.', 'warning');
            return;
        }

        _renderCheckboxList('exportSubjectList', data.subjects || [], 'subject');
        _renderCheckboxList('exportSessionList', data.sessions || [], 'session');
        _renderCheckboxListWithAcq(
            'exportModalityList',
            data.modalities || [],
            data.acq_labels || {},
            data.task_labels || {}
        );
        lastExportStructureStatus = {
            message: 'Current project structure loaded. Uncheck items below to narrow the export.',
            tone: 'ready',
        };
        await refreshDefacingPreflight({
            projectPath,
            modalities: data.modalities || [],
        });
        applyExportPreferencesToFilters(lastLoadedExportPreferences);
    } catch {
        if (requestToken !== projectStructureLoadToken) return;
        resetDefacingUiState();
        renderProjectStructureStatus('Could not load current project structure.', 'warning');
    }
}

/**
 * Render modality checkboxes with optional task/acq sub-checkboxes.
 */
function _renderCheckboxListWithAcq(containerId, items, acqLabels, taskLabels = {}) {
    const container = getById(containerId);
    if (!container) return;
    if (!items.length) {
        setHtml(container, '<span class="text-muted small">None detected.</span>');
        return;
    }
    const html = items.map(item => {
        const id = `export_modality_${item.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const tasks = taskLabels[item] || [];
        const acqs = acqLabels[item] || [];
        const subfilters = [
            ...tasks.map(task => ({ value: task, kind: 'task' })),
            ...acqs.map(acq => ({ value: acq, kind: 'acq' })),
        ];
        const acqHtml = subfilters.length ? `
        <div class="ms-4 mt-1" id="acq_group_${item}">
            ${subfilters.map(({ value, kind }) => {
                const acqId = `export_${kind}_${item}_${value.replace(/[^a-zA-Z0-9]/g, '_')}`;
                return `<div class="form-check form-check-sm">
                    <input class="form-check-input export-acq-filter" type="checkbox"
                           id="${acqId}" value="${escapeHtml(value)}" data-modality="${escapeHtml(item)}" data-filter-kind="${escapeHtml(kind)}" checked>
                    <label class="form-check-label small text-muted" for="${acqId}">
                        <code>${escapeHtml(value)}</code>
                    </label>
                </div>`;
            }).join('')}
        </div>` : '';
        return `
        <div class="form-check">
            <input class="form-check-input export-modality-filter" type="checkbox"
                   id="${id}" value="${escapeHtml(item)}" checked>
            <label class="form-check-label" for="${id}">
                <code>${escapeHtml(item)}</code>
            </label>
        </div>${acqHtml}`;
    }).join('');
    setHtml(container, html);
    syncAllModalitySubfilterStates();
}

function getSubfiltersForModality(modality) {
    return Array.from(document.querySelectorAll('.export-acq-filter'))
        .filter(checkbox => String(checkbox.dataset.modality || '').trim() === modality);
}

function applyModalitySubfilterState(modalityCheckbox) {
    const modality = String(modalityCheckbox?.value || '').trim();
    if (!modality) {
        return;
    }

    const subfilters = getSubfiltersForModality(modality);
    if (!subfilters.length) {
        if (modalityCheckbox) {
            modalityCheckbox.indeterminate = false;
        }
        return;
    }

    if (modalityCheckbox.checked) {
        const hasSelectedSubfilter = subfilters.some(checkbox => checkbox.checked);
        subfilters.forEach(checkbox => {
            checkbox.disabled = false;
            if (!hasSelectedSubfilter) {
                checkbox.checked = true;
            }
        });
    } else {
        subfilters.forEach(checkbox => {
            checkbox.disabled = true;
            checkbox.checked = false;
        });
    }

    syncModalitySubfilterState(modality);
}

function syncModalitySubfilterState(modality) {
    const modalityCheckbox = getExportFilterCheckbox('export-modality-filter', modality);
    if (!modalityCheckbox) {
        return;
    }

    const subfilters = getSubfiltersForModality(modality);
    if (!subfilters.length) {
        modalityCheckbox.indeterminate = false;
        return;
    }

    const checkedCount = subfilters.filter(checkbox => checkbox.checked).length;
    const hasSelectedSubfilter = checkedCount > 0;

    modalityCheckbox.checked = hasSelectedSubfilter;
    modalityCheckbox.indeterminate = hasSelectedSubfilter && checkedCount < subfilters.length;

    subfilters.forEach(checkbox => {
        checkbox.disabled = !hasSelectedSubfilter;
    });
}

function syncAllModalitySubfilterStates() {
    document.querySelectorAll('.export-modality-filter').forEach(checkbox => {
        syncModalitySubfilterState(String(checkbox.value || '').trim());
    });
}

/**
 * Render a list of labeled checkboxes (all checked by default) into containerId.
 */
function _renderCheckboxList(containerId, items, prefix) {
    const container = getById(containerId);
    if (!container) return;
    if (!items.length) {
        setHtml(container, '<span class="text-muted small">None detected.</span>');
        return;
    }
    const html = items.map(item => {
        const id = `export_${prefix}_${item.replace(/[^a-zA-Z0-9]/g, '_')}`;
        return `
        <div class="form-check">
            <input class="form-check-input export-${prefix}-filter" type="checkbox"
                   id="${id}" value="${escapeHtml(item)}" checked>
            <label class="form-check-label" for="${id}">
                <code>${escapeHtml(item)}</code>
            </label>
        </div>`;
    }).join('');
    setHtml(container, html);
}

function setAllExportScopeFiltersChecked(checked) {
    const desiredState = Boolean(checked);
    const subjectFilters = Array.from(document.querySelectorAll('.export-subject-filter'));
    const sessionFilters = Array.from(document.querySelectorAll('.export-session-filter'));
    const modalityFilters = Array.from(document.querySelectorAll('.export-modality-filter'));

    if (!subjectFilters.length && !sessionFilters.length && !modalityFilters.length) {
        return;
    }

    subjectFilters.forEach(checkbox => {
        checkbox.checked = desiredState;
    });

    sessionFilters.forEach(checkbox => {
        checkbox.checked = desiredState;
    });

    modalityFilters.forEach(checkbox => {
        checkbox.checked = desiredState;
        applyModalitySubfilterState(checkbox);
    });

    resetAnnexAvailabilityReport();
    saveExportPreferencesPatch({
        exclude_subjects: _getUncheckedValues('export-subject-filter'),
        exclude_sessions: _getUncheckedValues('export-session-filter'),
        exclude_modalities: _getUncheckedValues('export-modality-filter'),
        exclude_acq: _getUncheckedAcqByModality(),
        exclude_tasks: _getUncheckedTaskByModality(),
    });
    updateExportSnapshotUi();
}

/**
 * Load saved export preferences for the current project.
 */
export async function loadExportPreferences() {
    const outputFolderInput = getById('exportOutputFolder');
    const requestProjectPath = resolveCurrentProjectPath();
    if (!requestProjectPath) {
        exportPreferencesLoadToken += 1;
        lastLoadedExportPreferences = getDefaultExportPreferences();
        lastExportPreferenceInheritance = {
            repository_mode: false,
            defacing_confirmation_mode: false,
        };
        if (outputFolderInput) {
            outputFolderInput.value = '';
        }
        updateExportSnapshotUi();
        return lastLoadedExportPreferences;
    }

    const requestToken = ++exportPreferencesLoadToken;

    try {
        const resp = await fetchWithApiFallback(
            `/api/projects/preferences/export?project_path=${encodeURIComponent(requestProjectPath)}`
        );
        const data = await resp.json().catch(() => ({}));
        if (requestToken !== exportPreferencesLoadToken || requestProjectPath !== resolveCurrentProjectPath()) {
            return lastLoadedExportPreferences;
        }
        const normalized = resp.ok && data.success
            ? normalizeExportPreferences(data.preferences)
            : getDefaultExportPreferences();
        const inheritedPreferences = data.inherited_preferences || {};
        lastExportPreferenceInheritance = {
            repository_mode: Boolean(inheritedPreferences.repository_mode),
            defacing_confirmation_mode: Boolean(inheritedPreferences.defacing_confirmation_mode),
        };

        lastLoadedExportPreferences = normalized;
        if (outputFolderInput) {
            outputFolderInput.value = normalized.output_folder;
        }
        applyExportPreferencesToFilters(normalized);
        updateExportSnapshotUi();
        return normalized;
    } catch {
        if (requestToken !== exportPreferencesLoadToken || requestProjectPath !== resolveCurrentProjectPath()) {
            return lastLoadedExportPreferences;
        }
        lastLoadedExportPreferences = getDefaultExportPreferences();
        lastExportPreferenceInheritance = {
            repository_mode: false,
            defacing_confirmation_mode: false,
        };
        if (outputFolderInput) {
            outputFolderInput.value = '';
        }
        applyExportPreferencesToFilters(lastLoadedExportPreferences);
        updateExportSnapshotUi();
        return lastLoadedExportPreferences;
    }
}

/**
 * Initialize export form
 */
export function initExportForm() {
    const exportProjectForm = getById('exportProjectForm');
    if (exportProjectForm) {
        exportProjectForm.addEventListener('submit', handleExportSubmit);
        exportProjectForm.addEventListener('change', (event) => {
            if (isApplyingExportPreferences) {
                return;
            }

            const target = event.target;
            if (!target || !target.classList) {
                return;
            }

            resetAnnexAvailabilityReport();
            updateExportSnapshotUi();

            if (
                target.classList.contains('export-subject-filter')
                || target.classList.contains('export-session-filter')
                || target.classList.contains('export-modality-filter')
                || target.classList.contains('export-acq-filter')
            ) {
                if (target.classList.contains('export-modality-filter')) {
                    applyModalitySubfilterState(target);
                } else if (target.classList.contains('export-acq-filter')) {
                    const modality = String(target.dataset.modality || '').trim();
                    if (modality) {
                        syncModalitySubfilterState(modality);
                    }
                }

                saveExportPreferencesPatch({
                    exclude_subjects: _getUncheckedValues('export-subject-filter'),
                    exclude_sessions: _getUncheckedValues('export-session-filter'),
                    exclude_modalities: _getUncheckedValues('export-modality-filter'),
                    exclude_acq: _getUncheckedAcqByModality(),
                    exclude_tasks: _getUncheckedTaskByModality(),
                });
            }
        });
    }

    const browseBtn = getById('exportBrowseFolder');
    if (browseBtn) {
        browseBtn.addEventListener('click', async () => {
            try {
                const resp = await fetchWithApiFallback('/api/projects/export/browse-folder', { method: 'POST' });
                const data = await resp.json();
                if (data.folder) {
                    const input = getById('exportOutputFolder');
                    if (input) input.value = data.folder;
                    saveExportPreferencesPatch({ output_folder: data.folder });
                    resetAnnexAvailabilityReport();
                }
            } catch { /* ignore */ }
        });
    }

    // Persist folder preference on manual input change
    const folderInput = getById('exportOutputFolder');
    if (folderInput) {
        folderInput.addEventListener('change', () => {
            saveExportPreferencesPatch({ output_folder: folderInput.value.trim() });
            resetAnnexAvailabilityReport();
        });
    }

    const validationModeSelect = getById('exportValidationMode');
    if (validationModeSelect) {
        validationModeSelect.addEventListener('change', () => {
            saveExportPreferencesPatch({ validation_mode: getSelectedExportValidationMode() });
        });
    }

    const repositoryModeSelect = getById('exportRepositoryMode');
    if (repositoryModeSelect) {
        repositoryModeSelect.addEventListener('change', () => {
            saveExportPreferencesPatch({ repository_mode: getSelectedExportRepositoryMode() });
            updatePlainFolderExportButtonLabel();
        });
    }

    const defacingConfirmAlwaysToggle = getById('exportDefacingConfirmAlways');
    if (defacingConfirmAlwaysToggle) {
        defacingConfirmAlwaysToggle.addEventListener('change', () => {
            saveExportPreferencesPatch({ defacing_confirmation_mode: getSelectedDefacingConfirmationMode() });
        });
    }

    const scrubMriToggle = getById('exportScrubMriJson');
    if (scrubMriToggle) {
        scrubMriToggle.addEventListener('change', () => {
            syncMriScrubControls();
        });
    }

    const scrubAllToggle = getById('exportScrubAllTags');
    if (scrubAllToggle) {
        scrubAllToggle.addEventListener('change', () => {
            syncMriScrubControls();
        });
    }

    const resetDefacingModeBtn = getById('exportDefacingUseGlobalDefault');
    if (resetDefacingModeBtn) {
        resetDefacingModeBtn.addEventListener('click', async () => {
            const projectPath = resolveCurrentProjectPath();
            if (!projectPath) {
                return;
            }

            resetDefacingModeBtn.disabled = true;
            try {
                await saveExportPreferencesPatch({ defacing_confirmation_mode: null });
                await loadExportPreferences();
            } finally {
                updateExportSnapshotUi();
            }
        });
    }

    loadGlobalDefacingDefault();

    const saveGlobalDefaultBtn = getById('exportDefacingSaveGlobalDefault');
    if (saveGlobalDefaultBtn) {
        saveGlobalDefaultBtn.addEventListener('click', async () => {
            const select = getById('exportDefacingGlobalDefaultMode');
            const statusDiv = getById('exportDefacingGlobalDefaultStatus');
            const mode = normalizeDefacingConfirmationMode(select?.value);

            saveGlobalDefaultBtn.disabled = true;
            try {
                const response = await fetchWithApiFallback('/api/settings/global-library', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ export_defacing_confirmation_mode: mode }),
                });
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'Could not save global default.');
                }
                if (statusDiv) {
                    statusDiv.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i>Global default saved.</span>';
                    setTimeout(() => { statusDiv.innerHTML = ''; }, 3000);
                }
                window.dispatchEvent(new CustomEvent('prism-library-settings-changed', {
                    detail: { export_defacing_confirmation_mode: mode },
                }));
                await loadExportPreferences();
            } catch (error) {
                if (statusDiv) {
                    statusDiv.innerHTML = `<span class="text-danger"><i class="fas fa-exclamation-circle me-1"></i>${escapeHtml(error.message || 'Could not save global default.')}</span>`;
                }
            } finally {
                saveGlobalDefaultBtn.disabled = false;
            }
        });
    }

    const templateExportButton = getById('templateExportButton');
    if (templateExportButton) {
        templateExportButton.addEventListener('click', handleTemplateExport);
    }

    const plainFolderExportButton = getById('plainFolderExportButton');
    if (plainFolderExportButton) {
        plainFolderExportButton.addEventListener('click', handlePlainFolderExport);
        updatePlainFolderExportButtonLabel();
    }

    const uncheckAllFiltersBtn = getById('exportUncheckAllFilters');
    if (uncheckAllFiltersBtn) {
        uncheckAllFiltersBtn.addEventListener('click', (event) => {
            event.preventDefault();
            setAllExportScopeFiltersChecked(false);
        });
    }

    const checkAllFiltersBtn = getById('exportCheckAllFilters');
    if (checkAllFiltersBtn) {
        checkAllFiltersBtn.addEventListener('click', (event) => {
            event.preventDefault();
            setAllExportScopeFiltersChecked(true);
        });
    }

    const checkAllDefacingVariantsBtn = getById('exportDefacingCheckAllVariants');
    if (checkAllDefacingVariantsBtn) {
        checkAllDefacingVariantsBtn.addEventListener('click', (event) => {
            event.preventDefault();
            setDefacingVariantFiltersChecked(true);
        });
    }

    const uncheckAllDefacingVariantsBtn = getById('exportDefacingUncheckAllVariants');
    if (uncheckAllDefacingVariantsBtn) {
        uncheckAllDefacingVariantsBtn.addEventListener('click', (event) => {
            event.preventDefault();
            setDefacingVariantFiltersChecked(false);
        });
    }

    const defacingVariantList = getById('exportDefacingVariantList');
    if (defacingVariantList) {
        defacingVariantList.addEventListener('change', (event) => {
            const target = event.target;
            if (!target || !target.classList || !target.classList.contains('export-defacing-variant-filter')) {
                return;
            }
            const selected = getCheckedDefacingVariantKeys();
            lastDefacingVariantSelection = selected.length ? new Set(selected) : null;
        });
    }

    const checkAnnexAvailabilityBtn = getById('exportCheckAnnexAvailability');
    if (checkAnnexAvailabilityBtn) {
        checkAnnexAvailabilityBtn.addEventListener('click', async () => {
            const projectPath = resolveCurrentProjectPath();
            if (!projectPath) {
                alert('No project is currently loaded');
                return;
            }

            const originalLabel = checkAnnexAvailabilityBtn.innerHTML;
            checkAnnexAvailabilityBtn.disabled = true;
            checkAnnexAvailabilityBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Checking availability...';

            try {
                const summary = await ensureAnnexAvailabilitySummary(projectPath, { force: true });
                renderAnnexAvailabilityReport(summary);
            } catch (error) {
                renderAnnexAvailabilityError(error);
            } finally {
                checkAnnexAvailabilityBtn.disabled = false;
                checkAnnexAvailabilityBtn.innerHTML = originalLabel;
            }
        });
    }

    const uploadReadyExportButton = getById('uploadReadyExportButton');
    if (uploadReadyExportButton) {
        uploadReadyExportButton.addEventListener('click', handleUploadReadyExport);
    }

    // Defacing status check
    const checkDefacingBtn = getById('exportCheckDefacing');
    if (checkDefacingBtn) {
        checkDefacingBtn.addEventListener('click', async () => {
            const projectPath = resolveCurrentProjectPath();
            if (!projectPath) { alert('No project is currently loaded'); return; }
            const reportDiv = getById('exportDefacingReport');

            const variantSelection = getSelectedDefacingVariantPayload();
            if (variantSelection.errorMessage) {
                if (reportDiv) {
                    reportDiv.style.display = 'block';
                    reportDiv.innerHTML = `<div class="alert alert-warning py-1 mb-0">${escapeHtml(variantSelection.errorMessage)}</div>`;
                }
                return;
            }

            checkDefacingBtn.disabled = true;
            checkDefacingBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Checking…';
            try {
                const { counts, report } = await fetchDefacingSummary(projectPath);
                renderDefacingTable(reportDiv, counts, report);
            } catch (err) {
                if (reportDiv) { reportDiv.style.display = 'block'; reportDiv.innerHTML = `<div class="alert alert-danger py-1 mb-0">${err.message}</div>`; }
            } finally {
                checkDefacingBtn.disabled = false;
                checkDefacingBtn.innerHTML = '<i class="fas fa-search me-1"></i>Check defacing status of anatomical scans';
            }
        });
    }

    const runDefacingBtn = getById('exportRunDefacing');
    if (runDefacingBtn) {
        runDefacingBtn.addEventListener('click', async () => {
            const projectPath = resolveCurrentProjectPath();
            if (!projectPath) {
                alert('No project is currently loaded');
                return;
            }

            const reportDiv = getById('exportDefacingReport');
            const variantSelection = getSelectedDefacingVariantPayload();
            if (variantSelection.errorMessage) {
                if (reportDiv) {
                    reportDiv.style.display = 'block';
                    reportDiv.innerHTML = `<div class="alert alert-warning py-1 mb-0">${escapeHtml(variantSelection.errorMessage)}</div>`;
                }
                return;
            }

            try {
                const preflight = await fetchDefacingPreflight(projectPath);
                if (!preflight.has_anatomical_data) {
                    if (reportDiv) {
                        reportDiv.style.display = 'block';
                        reportDiv.innerHTML = '<div class="alert alert-info py-1 mb-0">No anatomical scans available in the current dataset.</div>';
                    }
                    return;
                }
                if (!preflight.can_run_defacing) {
                    if (reportDiv) {
                        reportDiv.style.display = 'block';
                        reportDiv.innerHTML = `<div class="alert alert-warning py-1 mb-0">${escapeHtml(preflight.message || 'Defacing prerequisites are not met.')}</div>`;
                    }
                    return;
                }
            } catch (preflightError) {
                if (reportDiv) {
                    reportDiv.style.display = 'block';
                    reportDiv.innerHTML = `<div class="alert alert-danger py-1 mb-0">${escapeHtml(preflightError.message || 'Could not check defacing prerequisites.')}</div>`;
                }
                return;
            }

            const selectedRepositoryMode = normalizeExportRepositoryMode(
                getById('exportRepositoryMode')?.value
            );
            const outputFolder = (getById('exportOutputFolder')?.value || '').trim() || null;
            const preservingMode = selectedRepositoryMode === 'datalad_preserving';
            const timeCostNote = ' This can take a long time (several minutes per scan) depending on how many scans are selected - the page will show progress until it finishes.';
            const proceed = window.confirm((preservingMode
                ? 'Run pydeface for export copy now? PRISM will create a DataLad-preserving export copy, run pydeface via DataLad in that copy, and keep the current project unchanged.'
                : 'Run pydeface for export copy now? PRISM will copy selected anatomical scans to the export target and deface that copy. The current project stays unchanged.') + timeCostNote);
            if (!proceed) {
                return;
            }

            const originalLabel = runDefacingBtn.innerHTML;
            runDefacingBtn.disabled = true;
            runDefacingBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Defacing...';

            try {
                const resp = await fetchWithApiFallback('/api/projects/export/deface', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_path: projectPath,
                        repository_mode: selectedRepositoryMode,
                        output_folder: outputFolder,
                        exclude_subjects: _getUncheckedValues('export-subject-filter'),
                        exclude_sessions: _getUncheckedValues('export-session-filter'),
                        selected_variants: Array.isArray(variantSelection.selectedVariants)
                            ? variantSelection.selectedVariants
                            : null,
                    }),
                });
                const result = await resp.json().catch(() => ({}));
                if (!resp.ok || !result.success) {
                    throw new Error(result.error || result.message || 'Defacing failed.');
                }

                const afterCounts = result.report_counts || { defaced: 0, not_defaced: 0, unknown: 0 };
                const afterReport = Array.isArray(result.report) ? result.report : [];
                renderDefacingTable(reportDiv, afterCounts, afterReport);

                const defacingCounts = result.defacing?.counts || {};
                const targetMode = String(result.target_mode || '');
                const targetPath = String(result.target_path || '');
                const targetSummary = targetMode === 'export_copy'
                    ? `Target copy: ${escapeHtml(targetPath || 'created in export output folder')}. Source project unchanged.`
                    : 'Source project unchanged.';
                const summaryHtml = `
                    <div class="alert alert-info py-1 mb-2">
                        ${escapeHtml(result.message || 'Defacing finished.')} Defaced: ${Number(defacingCounts.defaced || 0)}, already defaced: ${Number(defacingCounts.already_defaced || 0)}, failed: ${Number(defacingCounts.failed || 0)}.<br>
                        ${targetSummary}
                    </div>`;
                if (reportDiv) {
                    reportDiv.innerHTML = summaryHtml + reportDiv.innerHTML;
                }
            } catch (error) {
                if (reportDiv) {
                    reportDiv.style.display = 'block';
                    reportDiv.innerHTML = `<div class="alert alert-danger py-1 mb-0">${escapeHtml(error.message || 'Defacing failed.')}</div>`;
                }
            } finally {
                runDefacingBtn.disabled = false;
                runDefacingBtn.innerHTML = originalLabel;
                await loadProjectStructure();
            }
        });
    }

    syncMriScrubControls();
}

export function initializeProjectsExport() {
    if (exportModuleInitialized) {
        updateExportSnapshotUi();
        showExportCard();
        return;
    }

    exportModuleInitialized = true;
    initExportForm();
    initAndExport();
    initOpenMindsExport();
    loadExportPreferences();
    updateExportSnapshotUi();
    showExportCard();
}

/**
 * Handle template export action.
 */
async function handleTemplateExport(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this;
    const originalText = setButtonLoading(btn, true, 'Creating Template ZIP...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (statusText) statusText.textContent = getExportValidationStatusText(getSelectedExportValidationMode());

    const data = {
        project_path: currentProjectPath,
        output_folder: (getById('exportOutputFolder')?.value || '').trim() || null,
        validation_mode: getSelectedExportValidationMode(),
    };

    try {
        const response = await fetchWithApiFallback('/api/projects/template-export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await response.json();

        if (progressDiv) hide(progressDiv);
        if (resultDiv) show(resultDiv);

        if (response.ok && result.success) {
            const savedPath = result.output_path || 'unknown location';
            setHtml(resultDiv, `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>Template Export Successful!</h5>
                    <p class="mb-0">ZIP saved to:<br>
                    <code class="user-select-all">${escapeHtml(savedPath)}</code></p>
                </div>
            `);
        } else {
            throw new Error(result.error || 'Template export failed.');
        }
    } catch (error) {
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Template Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'Template export failed.')}</p>
                </div>
            `);
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

/**
 * Handle export form submission (async job with progress + cancel)
 */
async function handleExportSubmit(e) {
    e.preventDefault();

    const btn = this.querySelector('button[type="submit"]');
    await runProjectExport({
        button: btn,
        loadingText: 'Starting Export...',
        requestOverrides: {},
        successHeading: 'Export Successful!',
    });
}

async function handleUploadReadyExport(e) {
    e.preventDefault();

    await runProjectExport({
        button: this,
        loadingText: 'Preparing Upload-Ready ZIP...',
        requestOverrides: {
            export_preset: 'upload_ready',
            repository_mode: 'datalad_free',
        },
        successHeading: 'Upload-Ready Export Successful!',
        successNoteHtml: '<p class="mb-2">PRISM excluded <code>code/</code>, <code>derivatives/</code>, <code>analysis/</code>, and version-control metadata such as DataLad traces.</p>',
    });
}

async function handlePlainFolderExport(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const gitLfsMode = isGitLfsExportModeSelected();

    const btn = this;
    const originalText = setButtonLoading(btn, true, gitLfsMode ? 'Exporting Git LFS Snapshot...' : 'Exporting Folder...');
    const progressDiv = getById('exportProgress');
    const progressBar = getById('exportProgressBar');
    const progressText = getById('exportProgressText');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');
    const cancelBtn = getById('exportCancelBtn');
    const materializeAnnex = true;

    let progressPercent = materializeAnnex ? 8 : 12;
    const maxPendingPercent = materializeAnnex ? 94 : 88;
    const progressStep = materializeAnnex ? 2 : 4;
    const progressTickMs = materializeAnnex ? 900 : 650;
    let progressTimerId = null;
    let statusPulseTimerId = null;
    let statusPulseTick = 0;
    const exportStartedAtMs = Date.now();

    const setFolderProgress = (nextPercent) => {
        const boundedPercent = Math.max(0, Math.min(100, Number(nextPercent) || 0));
        progressPercent = boundedPercent;
        if (progressBar) {
            progressBar.style.width = `${boundedPercent}%`;
        }
        if (progressText) {
            progressText.textContent = `${boundedPercent}%`;
        }
    };

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (cancelBtn) {
        cancelBtn.style.display = 'none';
    }
    setFolderProgress(progressPercent);
    if (statusText) {
        statusText.textContent = materializeAnnex
            ? 'Checking annex availability for selected scope...'
            : 'Creating plain folder export without Git/DataLad metadata...';
    }
    if (gitLfsMode && statusText) {
        statusText.textContent = 'Checking annex availability for selected scope (Git LFS export)...';
    }

    if (materializeAnnex) {
        try {
            const preflightSummary = await ensureAnnexAvailabilitySummary(currentProjectPath, { force: true });
            renderAnnexAvailabilityReport(preflightSummary);
            const missingPreflightCount = Number(preflightSummary.missing_files_count || 0);
            if (missingPreflightCount > 0 && statusText) {
                statusText.textContent = `Detected ${missingPreflightCount} missing local file(s); continuing with materialized folder export...`;
            }
        } catch (preflightError) {
            renderAnnexAvailabilityError(preflightError);
            if (statusText) {
                statusText.textContent = 'Could not complete annex preflight automatically; continuing with materialized folder export...';
            }
        }
        if (statusText) {
            statusText.textContent = gitLfsMode
                ? 'Materializing content and preparing Git LFS export...'
                : 'Materializing DataLad content and creating plain folder export...';
        }
    }

    progressTimerId = window.setInterval(() => {
        if (progressPercent >= maxPendingPercent) {
            return;
        }
        setFolderProgress(Math.min(maxPendingPercent, progressPercent + progressStep));
    }, progressTickMs);

    statusPulseTimerId = window.setInterval(() => {
        if (!statusText || progressPercent < maxPendingPercent) {
            return;
        }
        const elapsedSeconds = Math.max(0, Math.floor((Date.now() - exportStartedAtMs) / 1000));
        const elapsedMinutes = Math.floor(elapsedSeconds / 60);
        const remainingSeconds = elapsedSeconds % 60;
        const dots = '.'.repeat((statusPulseTick % 3) + 1);
        statusPulseTick += 1;
        statusText.textContent = materializeAnnex
            ? `Still materializing selected scope (${elapsedMinutes}m ${remainingSeconds}s elapsed)${dots}`
            : `Still creating folder export (${elapsedMinutes}m ${remainingSeconds}s elapsed)${dots}`;
    }, 5000);

    try {
        const data = buildFolderExportRequestData(currentProjectPath);
        if (data.scrub_mri_json && !shouldScrubAllMriTags()) {
            const selectedScrubGroups = Array.isArray(data.scrub_mri_json_groups)
                ? data.scrub_mri_json_groups
                : [];
            if (!selectedScrubGroups.length) {
                throw new Error('Select at least one MRI tag group or enable scrub-all mode.');
            }
        }

        const endpoint = gitLfsMode ? '/api/projects/export/git-lfs' : '/api/projects/export/folder';
        const requestBody = gitLfsMode
            ? { ...data, init_git_lfs_repo: true }
            : data;
        const response = await fetchWithApiFallback(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
        });
        const result = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));

        if (statusText) {
            statusText.textContent = gitLfsMode ? 'Finalizing Git LFS export...' : 'Finalizing folder export...';
        }
        setFolderProgress(97);

        if (progressDiv) hide(progressDiv);
        if (resultDiv) show(resultDiv);

        if (response.ok && result.success) {
            setFolderProgress(100);
            const savedPath = result.output_path || 'unknown location';
            const excludedMetadata = Array.isArray(result.excluded_repository_metadata)
                ? result.excluded_repository_metadata.filter((value) => typeof value === 'string' && value.trim())
                : [];
            const warningText = typeof result.warning === 'string'
                ? result.warning.trim()
                : '';
            const materializedExport = Boolean(result.materialized_export);
            const materializationWarnings = Array.isArray(result.materialization_warnings)
                ? result.materialization_warnings
                    .filter((value) => typeof value === 'string' && value.trim())
                    .slice(0, 5)
                : [];
            const missingFilesCount = Number(result.missing_files_count || 0);
            const missingFilePreview = Array.isArray(result.missing_files_preview)
                ? result.missing_files_preview
                    .filter((value) => typeof value === 'string' && value.trim())
                    .slice(0, 5)
                : [];
            const missingPreviewRoot = typeof result.missing_files_preview_root === 'string'
                ? result.missing_files_preview_root.trim()
                : '';
            const excludedMetadataHtml = excludedMetadata.length
                ? `<p class="mb-2">Stripped repository metadata: <code>${escapeHtml(excludedMetadata.join(', '))}</code></p>`
                : '';
            const materializationWarningsHtml = materializationWarnings.length
                ? `<details class="mt-2"><summary>Materialization warnings</summary><ul class="mb-0">${materializationWarnings.map((value) => `<li>${escapeHtml(value)}</li>`).join('')}</ul></details>`
                : '';
            const materializationHtml = materializedExport
                ? `<div class="alert alert-info mb-2"><p class="mb-1"><i class="fas fa-database me-2"></i>PRISM created this folder from a temporary DataLad clone and materialized only files in the selected export scope.</p>${materializationWarningsHtml}</div>`
                : (materializationWarningsHtml
                    ? `<div class="alert alert-info mb-2"><p class="mb-1">Materialization notes:</p>${materializationWarningsHtml}</div>`
                    : '');
            const missingPreviewHtml = missingFilePreview.length
                ? `<details class="mt-2"><summary>Skipped files preview</summary>${missingPreviewRoot ? `<p class="small text-muted mb-1">Relative to: <code class="user-select-all">${escapeHtml(missingPreviewRoot)}</code></p>` : ''}<ul class="mb-0">${missingFilePreview.map((value) => `<li><code class="user-select-all">${escapeHtml(value)}</code></li>`).join('')}</ul></details>`
                : '';
            const warningHtml = (warningText || missingFilesCount > 0)
                ? `<div class="alert alert-warning mb-2">`
                    + `<p class="mb-1"><i class="fas fa-exclamation-triangle me-2"></i>${escapeHtml(warningText || `Skipped ${missingFilesCount} file(s) that were not available locally during export.`)}</p>`
                    + missingPreviewHtml
                    + `</div>`
                : '';
            const gitLfsResult = result.git_lfs && typeof result.git_lfs === 'object' ? result.git_lfs : null;
            const gitLfsHtml = gitLfsResult
                ? `<div class="alert ${gitLfsResult.warning ? 'alert-warning' : 'alert-info'} mb-2">`
                    + `<p class="mb-1"><i class="fas fa-code-branch me-2"></i>${gitLfsResult.repo_initialized
                        ? 'Initialized a Git LFS repository with an initial commit in this folder.'
                        : 'Wrote .gitattributes and GIT_LFS_EXPORT_NOTES.md; the repository was not auto-initialized.'}</p>`
                    + (gitLfsResult.warning ? `<p class="mb-1">${escapeHtml(gitLfsResult.warning)}</p>` : '')
                    + `<p class="mb-0 small text-muted">This is a one-way export snapshot — it has no ongoing connection back to this project.</p>`
                    + `</div>`
                : '';
            setHtml(resultDiv, `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>${gitLfsResult ? 'Git LFS Export Successful!' : 'Folder Export Successful!'}</h5>
                    <p class="mb-2">${gitLfsResult
                        ? 'PRISM created a folder copy prepared for Git LFS, without Git/DataLad metadata from the source project.'
                        : 'PRISM created a normal folder copy without Git/DataLad metadata or hidden repository files.'}</p>
                    ${materializationHtml}
                    ${excludedMetadataHtml}
                    ${gitLfsHtml}
                    ${warningHtml}
                    <p class="mb-0">Folder saved to:<br>
                    <code class="user-select-all">${escapeHtml(savedPath)}</code></p>
                </div>
            `);
            return;
        }

        throw new Error(result.error || result.message || 'Folder export failed.');
    } catch (error) {
        setFolderProgress(100);
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Folder Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'Folder export failed.')}</p>
                </div>
            `);
        }
    } finally {
        if (progressTimerId !== null) {
            window.clearInterval(progressTimerId);
        }
        if (statusPulseTimerId !== null) {
            window.clearInterval(statusPulseTimerId);
        }
        if (cancelBtn) {
            cancelBtn.style.display = '';
        }
        setButtonLoading(btn, false, null, originalText);
    }
}

async function runProjectExport({
    button,
    loadingText,
    requestOverrides,
    successHeading,
    successNoteHtml = '',
}) {

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const originalText = setButtonLoading(button, true, loadingText);

    const progressDiv = getById('exportProgress');
    const progressBar = getById('exportProgressBar');
    const progressText = getById('exportProgressText');
    const statusText = getById('exportStatusText');
    const cancelBtn = getById('exportCancelBtn');
    const resultDiv = getById('exportResult');

    // Reset and show progress
    if (progressBar) { progressBar.style.width = '0%'; }
    if (progressText) progressText.textContent = '0%';
    const data = buildExportRequestData(currentProjectPath, requestOverrides);
    if (data.scrub_mri_json && !shouldScrubAllMriTags()) {
        const selectedScrubGroups = Array.isArray(data.scrub_mri_json_groups)
            ? data.scrub_mri_json_groups
            : [];
        if (!selectedScrubGroups.length) {
            if (progressDiv) hide(progressDiv);
            if (resultDiv) {
                show(resultDiv);
                setHtml(resultDiv, '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>Select at least one MRI tag group or enable scrub-all mode.</div>');
            }
            setButtonLoading(button, false, null, originalText);
            return;
        }
    }
    const selectedValidationMode = normalizeExportValidationMode(data.validation_mode);
    const selectedRepositoryMode = normalizeExportRepositoryMode(data.repository_mode);
    const effectiveRepositoryMode = data.export_preset === 'upload_ready'
        ? 'datalad_free'
        : selectedRepositoryMode;
    data.repository_mode = effectiveRepositoryMode;
    if (statusText) {
        statusText.textContent = `${getExportValidationStatusText(selectedValidationMode)} ${getExportRepositoryModeStatusSuffix(effectiveRepositoryMode)}`;
    }
    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);

    if (data.scrub_mri_json) {
        const defacingConfirmationMode = getSelectedDefacingConfirmationMode();
        const variantSelection = getSelectedDefacingVariantPayload();
        if (variantSelection.errorMessage) {
            if (progressDiv) hide(progressDiv);
            if (resultDiv) {
                show(resultDiv);
                setHtml(resultDiv, `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>${escapeHtml(variantSelection.errorMessage)}</div>`);
            }
            setButtonLoading(button, false, null, originalText);
            return;
        }

        try {
            if (statusText) {
                statusText.textContent = 'Checking defacing status before export...';
            }
            const defacingSummary = await fetchDefacingSummary(currentProjectPath);
            if (defacingConfirmationMode === 'always' || defacingSummary.riskCount > 0) {
                const counts = defacingSummary.counts || {};
                const confirmMessage = defacingSummary.riskCount > 0
                    ? `Defacing check found ${counts.not_defaced || 0} not-defaced and ${counts.unknown || 0} unknown anatomical scan(s). Continue export anyway?`
                    : 'Defacing check did not detect unresolved risk in anatomical scans. Continue export anyway?';
                const continueExport = window.confirm(
                    confirmMessage
                );
                if (!continueExport) {
                    if (progressDiv) hide(progressDiv);
                    if (resultDiv) {
                        show(resultDiv);
                        setHtml(resultDiv, '<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Export cancelled before start: defacing risk was not accepted.</div>');
                    }
                    return;
                }
            }
        } catch {
            if (defacingConfirmationMode === 'always') {
                const continueExport = window.confirm(
                    'Could not retrieve defacing status before export. Continue export anyway?'
                );
                if (!continueExport) {
                    if (progressDiv) hide(progressDiv);
                    if (resultDiv) {
                        show(resultDiv);
                        setHtml(resultDiv, '<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Export cancelled before start: defacing risk was not accepted.</div>');
                    }
                    return;
                }
            }
        }

        if (statusText) {
            statusText.textContent = `${getExportValidationStatusText(selectedValidationMode)} ${getExportRepositoryModeStatusSuffix(effectiveRepositoryMode)}`;
        }
    }

    let jobId = null;
    let cancelled = false;

    async function requestCancelForActiveJob() {
        if (!jobId) {
            return false;
        }
        try {
            await fetchWithApiFallback(`/api/projects/export/${encodeURIComponent(jobId)}/cancel`, { method: 'DELETE' });
        } catch {
            // Ignore cancellation network failures; the UI already reflects the local cancel state.
        }
        return true;
    }

    // Cancel button handler
    function onCancelClick() {
        cancelled = true;
        void requestCancelForActiveJob();
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Export cancelled.</div>`);
        }
        setButtonLoading(btn, false, null, originalText);
    }

    if (cancelBtn) {
        cancelBtn.onclick = onCancelClick;
    }

    try {
        // Start the async job
        const startResp = await fetchWithApiFallback('/api/projects/export/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!startResp.ok) {
            const err = await startResp.json();
            throw new Error(err.error || 'Failed to start export');
        }
        const startData = await startResp.json();
        jobId = startData.job_id;
        if (cancelled) {
            await requestCancelForActiveJob();
            return;
        }

        // Poll for status (max ~2250 iterations = ~30 minutes)
        const MAX_POLLS = 2250;
        for (let i = 0; i < MAX_POLLS; i++) {
            if (cancelled) break;
            await new Promise(r => setTimeout(r, 800));
            if (cancelled) break;

            const statusResp = await fetchWithApiFallback(
                `/api/projects/export/${encodeURIComponent(jobId)}/status`
            );
            if (!statusResp.ok) break;
            const status = await statusResp.json();

            const pct = status.percent || 0;
            if (progressBar) progressBar.style.width = `${pct}%`;
            if (progressText) progressText.textContent = `${pct}%`;
            if (statusText) statusText.textContent = status.message || '';

            if (status.status === 'complete') {
                    if (progressDiv) hide(progressDiv);
                    if (resultDiv) {
                        show(resultDiv);
                        const savedPath = status.zip_path || 'unknown location';
                        const repositoryModeNoteHtml = successNoteHtml || getExportRepositoryModeSuccessNote(effectiveRepositoryMode);
                        const defacingWarning = status.defacing_warning || null;
                        const defacingWarningHtml = (defacingWarning && defacingWarning.message)
                            ? `
                                <div class="alert alert-warning mt-2 mb-0">
                                    <i class="fas fa-triangle-exclamation me-2"></i>${escapeHtml(defacingWarning.message)}
                                </div>
                            `
                            : '';
                        setHtml(resultDiv, `
                            <div class="alert alert-success">
                                <h5><i class="fas fa-check-circle me-2"></i>${escapeHtml(successHeading)}</h5>
                                ${repositoryModeNoteHtml}
                                <p class="mb-0">ZIP saved to:<br>
                                <code class="user-select-all">${escapeHtml(savedPath)}</code></p>
                            </div>
                            ${defacingWarningHtml}
                    `);
                }
                return;
            }

            if (status.status === 'error') {
                throw new Error(status.error || 'Export failed');
            }

            if (status.status === 'cancelled') {
                cancelled = true;
                break;
            }
        }

        if (!cancelled) {
            throw new Error('Export timed out after 30 minutes. Please check server logs.');
        }

    } catch (error) {
        if (cancelled) return; // already showed cancel message
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'Export failed.')}</p>
                </div>
            `);
        }
    } finally {
        if (cancelBtn && cancelBtn.onclick === onCancelClick) {
            cancelBtn.onclick = null;
        }
        if (!cancelled) {
            setButtonLoading(button, false, null, originalText);
        }
    }
}

/**
 * Return the values of unchecked checkboxes with the given class name.
 * These are the items the user wants to EXCLUDE.
 */
function _getUncheckedValues(className) {
    return Array.from(document.querySelectorAll(`.${className}`))
        .filter(cb => !cb.checked)
        .map(cb => cb.value);
}

/**
 * Return a dict of {modality: [acq_label, ...]} for unchecked acq checkboxes.
 */
function _getUncheckedAcqByModality() {
    return _getUncheckedSubfiltersByKind('acq');
}

/**
 * Return a dict of {modality: [task_label, ...]} for unchecked task checkboxes.
 */
function _getUncheckedTaskByModality() {
    return _getUncheckedSubfiltersByKind('task');
}

function _getUncheckedSubfiltersByKind(kind) {
    const result = {};
    document.querySelectorAll('.export-acq-filter').forEach(cb => {
        if (!cb.checked && String(cb.dataset.filterKind || 'acq') === kind) {
            const mod = cb.dataset.modality;
            if (mod) {
                if (!result[mod]) result[mod] = [];
                result[mod].push(cb.value);
            }
        }
    });
    return result;
}

/**
 * Initialize ANC export
 */
export function initAndExport() {
    const ancEnableExport = getById('ancEnableExport');
    if (ancEnableExport) {
        ancEnableExport.addEventListener('change', function() {
            const isEnabled = this.checked;
            const optionsGroup = getById('ancOptionsGroup');
            const optionsGroup2 = getById('ancOptionsGroup2');
            const metadataSection = getById('ancMetadataSection');
            const exportButton = getById('ancExportButton');

            if (optionsGroup) optionsGroup.style.display = isEnabled ? 'block' : 'none';
            if (optionsGroup2) optionsGroup2.style.display = isEnabled ? 'block' : 'none';
            if (metadataSection) metadataSection.style.display = isEnabled ? 'block' : 'none';
            if (exportButton) exportButton.style.display = isEnabled ? 'inline-block' : 'none';
        });
    }

    const ancExportButton = getById('ancExportButton');
    if (ancExportButton) {
        ancExportButton.addEventListener('click', handleAndExport);
    }
}

/**
 * Handle ANC export
 */
async function handleAndExport(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this;
    const originalText = setButtonLoading(btn, true, 'Exporting for ANC...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (statusText) statusText.textContent = 'Preparing ANC export...';

    const metadata = {};
    const title = getById('ancDatasetTitle')?.value.trim() || '';
    const email = getById('ancContactEmail')?.value.trim() || '';
    const givenName = getById('ancAuthorGiven')?.value.trim() || '';
    const familyName = getById('ancAuthorFamily')?.value.trim() || '';
    const description = getById('ancDatasetDescription')?.value.trim() || '';

    if (title) metadata.DATASET_NAME = title;
    if (email) metadata.CONTACT_EMAIL = email;
    if (givenName) metadata.AUTHOR_GIVEN_NAME = givenName;
    if (familyName) metadata.AUTHOR_FAMILY_NAME = familyName;
    if (description) metadata.DATASET_ABSTRACT = description;

    const data = {
        project_path: currentProjectPath,
        convert_to_git_lfs: getById('ancConvertGitLfs')?.checked || false,
        include_ci_examples: getById('ancIncludeCiExamples')?.checked || false,
        metadata
    };

    try {
        const response = await fetchWithApiFallback('/api/projects/anc-export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (progressDiv) hide(progressDiv);
        if (resultDiv) show(resultDiv);

        if (result.success) {
            let infoHtml = '';
            if (data.convert_to_git_lfs) {
                infoHtml += `
                    <div class="alert alert-info py-2 mt-2 mb-2">
                        <i class="fas fa-info-circle me-2"></i>
                        Git LFS configuration added. See <code>GIT_LFS_SETUP.md</code> in the export folder for setup instructions.
                    </div>
                `;
            } else {
                infoHtml += `
                    <div class="alert alert-info py-2 mt-2 mb-2">
                        <i class="fas fa-info-circle me-2"></i>
                        Export is DataLad-compatible. See <code>DATALAD_NOTE.md</code> for more information.
                    </div>
                `;
            }

            if (data.include_ci_examples) {
                infoHtml += `
                    <div class="alert alert-info py-2 mt-2 mb-2">
                        <i class="fas fa-info-circle me-2"></i>
                        CI/CD example files included. See <code>CI_SETUP.md</code> for instructions.
                    </div>
                `;
            }

            const filesList = result.generated_files ?
                Object.entries(result.generated_files).map(([key, path]) =>
                    `<li><code>${path.split('/').pop()}</code></li>`
                ).join('') : '';

            if (resultDiv) {
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>ANC Export Successful!</h5>
                        <p class="mb-2">Dataset exported to: <strong><code>${result.output_path}</code></strong></p>
                        ${filesList ? `
                            <div class="mt-2">
                                <strong>Generated files:</strong>
                                <ul class="mb-0 mt-1">${filesList}</ul>
                            </div>
                        ` : ''}
                        ${infoHtml}
                        <div class="mt-3">
                            <strong>Next steps:</strong>
                            <ol class="mb-0 mt-1">
                                <li>Review and edit <code>README.md</code> and <code>CITATION.cff</code> in the export folder</li>
                                <li>Run BIDS validator to verify compliance</li>
                                <li>Submit to ANC</li>
                            </ol>
                        </div>
                    </div>
                `;
            }
        } else {
            if (resultDiv) {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>ANC Export Failed</h5>
                        <p class="mb-0">${escapeHtml(result.error || 'Unknown error occurred')}</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>ANC Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'ANC export failed.')}</p>
                </div>
            `;
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

/**
 * Initialize openMINDS export
 */
export function initOpenMindsExport() {
    const enableCheckbox = getById('openmindsEnableExport');
    if (enableCheckbox) {
        enableCheckbox.addEventListener('change', function() {
            const isEnabled = this.checked;
            const optionsGroup = getById('openmindsOptionsGroup');
            const metadataSection = getById('openmindsMetadataSection');
            const exportButton = getById('openmindsExportButton');
            if (optionsGroup) optionsGroup.style.display = isEnabled ? 'block' : 'none';
            if (metadataSection) metadataSection.style.display = isEnabled ? 'block' : 'none';
            if (exportButton) exportButton.style.display = isEnabled ? 'inline-block' : 'none';
            if (isEnabled) _loadOpenMindsTaskDescriptions();
        });
    }

    const exportButton = getById('openmindsExportButton');
    if (exportButton) {
        exportButton.addEventListener('click', handleOpenMindsExport);
    }
}

/**
 * Fetch tasks from the project and render description inputs in the pre-flight form.
 */
async function _loadOpenMindsTaskDescriptions() {
    const container = getById('openmindsProtocolsContainer');
    const placeholder = getById('openmindsProtocolsPlaceholder');
    if (!container) return;

    const currentProjectPath = resolveCurrentProjectPath();
    const params = currentProjectPath ? `?project_path=${encodeURIComponent(currentProjectPath)}` : '';

    try {
        const response = await fetchWithApiFallback(`/api/projects/openminds-tasks${params}`);
        const result = await response.json();

        if (!result.success || !result.tasks || result.tasks.length === 0) {
            if (placeholder) placeholder.textContent = 'No tasks found in project.';
            return;
        }

        // Render one textarea per task
        const rows = result.tasks.map(task => `
            <div class="mb-2">
                <label class="form-label small fw-semibold mb-1">${task}</label>
                <textarea class="form-control form-control-sm openminds-protocol-desc"
                          rows="2"
                          data-task="${task}"
                          placeholder="Describe what participants did in this task…"></textarea>
            </div>
        `).join('');

        container.innerHTML = rows;
    } catch (_err) {
        if (placeholder) placeholder.textContent = 'Could not load tasks.';
    }
}

/**
 * Handle openMINDS export
 */
async function handleOpenMindsExport(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this;
    const originalText = setButtonLoading(btn, true, 'Exporting to openMINDS...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (statusText) statusText.textContent = 'Running bids2openminds...';

    const singleFileRadio = getById('openmindsModeSingle');
    const singleFile = singleFileRadio ? singleFileRadio.checked : true;

    // Collect pre-flight supplements
    const protocolDescriptions = {};
    document.querySelectorAll('.openminds-protocol-desc').forEach(el => {
        const task = el.dataset.task;
        const desc = el.value.trim();
        if (task && desc) protocolDescriptions[task] = desc;
    });
    const ethicsCategory = getById('openmindsEthicsCategory')?.value.trim() || '';

    const data = {
        project_path: currentProjectPath,
        single_file: singleFile,
        include_empty: getById('openmindsIncludeEmpty')?.checked || false,
        supplements: {
            protocol_descriptions: protocolDescriptions,
            ethics_category: ethicsCategory,
        },
    };

    try {
        const response = await fetchWithApiFallback('/api/projects/openminds-export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (progressDiv) hide(progressDiv);
        if (resultDiv) show(resultDiv);

        if (result.success) {
            const outputLabel = result.single_file
                ? `<code>${result.output_path}</code>`
                : `folder <code>${result.output_path}</code>`;
            const notesHtml = result.has_notes
                ? `<div class="alert alert-info py-2 mt-2 mb-0">
                       <i class="fas fa-info-circle me-2"></i>
                       Ethics and other supplements saved to
                       <code>${result.output_path.replace(/\.jsonld$/, '_supplements.json')}</code>.
                   </div>`
                : '';
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>openMINDS Export Successful!</h5>
                    <p class="mb-2">Metadata written to: <strong>${outputLabel}</strong></p>
                    ${notesHtml}
                    <div class="mt-3">
                        <strong>Next steps:</strong>
                        <ol class="mb-0 mt-1">
                            <li>Review the generated <code>.jsonld</code> file for completeness</li>
                            <li>Submit or publish the openMINDS metadata alongside your dataset</li>
                        </ol>
                    </div>
                </div>
            `;
        } else {
            const isNotInstalled = (result.error || '').includes('not installed');
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>openMINDS Export Failed</h5>
                    <p class="mb-0">${escapeHtml(result.error || 'Unknown error occurred')}</p>
                    ${isNotInstalled ? `<p class="mb-0 mt-2"><small>Install with: <code>pip install bids2openminds</code></small></p>` : ''}
                </div>
            `;
        }
    } catch (error) {
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>openMINDS Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'openMINDS export failed.')}</p>
                </div>
            `;
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}
