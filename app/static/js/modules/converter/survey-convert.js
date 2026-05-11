/**
 * Survey Convert Module (Landgig Integration)
 * Handles Excel/LimeSurvey data conversion to PRISM survey format
 * Includes: column detection, ID mapping, preview, participants mapping, validation
 */

import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { createSessionRegistrar } from '../../shared/session-register.js';
import { createSurveyParticipantsMetadataController } from './survey-participants-metadata.js';
import { createSurveyWorkflowPrepareController } from './survey-workflow-prepare.js';
import { createSurveyWorkflowConvertController } from './survey-workflow-convert.js';
import { createSurveyWorkflowProgressController } from './survey-workflow-progress.js';
import { createSurveySourcedataQuickSelectController } from './survey-sourcedata-quick-select.js';
import { createSurveyTemplateResultsController } from './survey-template-results.js';
import { createSurveyConversionSummaryController } from './survey-conversion-summary.js';
import { createSurveyConversionLogController } from './survey-conversion-log.js';
import { createSurveyValidationResultsController } from './survey-validation-results.js';
import { createSurveyValueOffsetEditorController } from './survey-value-offset-editor.js';
import {
    collectSuggestedValueOffsets,
    formatOffsetMagnitude,
    formatSignedOffset,
    normalizeTaskValueOffsets as normalizeTaskValueOffsetsMap,
    parseNumericOffsetValue,
    parseTaskValueOffsetsText as parseTaskValueOffsetsTextWithNormalizer,
} from './survey-value-offset-utils.js';
import { createSurveyWorkflowTemplateCheckController } from './survey-workflow-template-check.js';
import { createSurveyWorkflowPreviewController } from './survey-workflow-preview.js';

export function initSurveyConvert(elements) {
    const {
        // Survey Convert DOM elements
        convertLibraryPathInput,
        convertBrowseLibraryBtn,
        convertExcelFile,
        convertSeparator,
        surveySeparatorGroup,
        clearConvertExcelFileBtn,
        convertIdMapFile,
        clearIdMapFileBtn,
        checkProjectTemplatesBtn,
        convertBtn,
        previewBtn,
        convertDatasetName,
        convertLanguage,
        convertError,
        convertInfo,
        surveyRunProgressContainer,
        surveyRunProgressBar,
        surveyRunProgressLabel,
        surveyRunProgressPercent,
        surveyRunCancelBtn,
        convertIdColumnGroup,
        convertIdColumn,
        convertTemplateExportGroup,
        convertLanguageGroup,
        convertAliasGroup,
        convertSessionGroup,
        templateResultsContainer,
        convertSessionSelect,
        convertSessionCustom,
        biometricsSessionSelect,
        biometricsSessionCustom,
        sourcedataQuickSelect,
        sourcedataFileSelect,
        conversionLogContainer,
        conversionLog,
        conversionLogBody,
        templateEditorErrorCta,
        toggleLogBtn,
        validationResultsContainer,
        validationResultsCard,
        validationResultsHeader,
        validationBadge,
        validationSummary,
        validationDetails,
        conversionSummaryContainer,
        conversionSummaryBody,
        toggleSummaryBtn,
        // Shared functions
        populateSessionPickers
    } = elements;

    const convertAdvancedToggle = document.getElementById('convertAdvancedToggle');
    const surveyAdvancedOptionsPanel = document.getElementById('surveyAdvancedOptions');
    const convertValueOffsets = document.getElementById('convertValueOffsets');
    const convertValueOffsetsEditor = document.getElementById('convertValueOffsetsEditor');
    const convertValueOffsetRows = document.getElementById('convertValueOffsetRows');
    const convertAddValueOffsetRowBtn = document.getElementById('convertAddValueOffsetRowBtn');
    const convertApplyValueOffsetsBtn = document.getElementById('convertApplyValueOffsetsBtn');
    const convertValueOffsetsKnownTasks = document.getElementById('convertValueOffsetsKnownTasks');
    const convertValueOffsetsEmptyState = document.getElementById('convertValueOffsetsEmptyState');
    const convertValueOffsetsStatus = document.getElementById('convertValueOffsetsStatus');
    const convertValueOffsetAdvice = document.getElementById('convertValueOffsetAdvice');
    const surveyWorkflowHint = document.getElementById('surveyWorkflowHint');
    const browseServerSurveyFileBtn = document.getElementById('browseServerSurveyFileBtn');
    const convertSessionColumnOverride = document.getElementById('convertSessionColumnOverride');
    const convertRunColumnOverride = document.getElementById('convertRunColumnOverride');
    let templateWorkflowGate = null;
    const surveyVersionWizard = document.getElementById('surveyVersionWizard');
    const surveyVersionWizardBody = document.getElementById('surveyVersionWizardBody');
    const surveyVersionWizardCount = document.getElementById('surveyVersionWizardCount');
    const surveyVersionWizardStatus = document.getElementById('surveyVersionWizardStatus');
    const surveyVersionWizardApplyBtn = document.getElementById('surveyVersionWizardApplyBtn');
    let selectedTemplateVersions = {};
    let appliedTemplateVersionSelectionSignature = '';
    let versionWizardState = {
        multivariantTasks: {},
        taskRuns: {},
        previewParticipants: [],
        detectedSessions: []
    };
    let versionWizardSyncTimer = null;
    let versionWizardSyncRequestId = 0;
    let convertServerFilePath = '';
    let lastDetectedSurveyFingerprint = '';
    let confirmedNearMatchTasks = [];
    let versionWizardRetryGateMode = null;
    let isConvertRunning = false;
    let isPreviewRunning = false;
    let activeRunAbortController = null;
    let activeRunMode = null;
    let activeRunCancelledByUser = false;
    let taskValueOffsetRowSequence = 0;
    let taskValueOffsetEditorState = [];
    let appliedTaskValueOffsetSelectionSignature = '';
    let surveyPreviewSelectionState = {
        previewKey: '',
        availableTasks: [],
        selectedTasks: []
    };

    const surveyWorkflowProgressController = createSurveyWorkflowProgressController({
        surveyRunProgressContainer,
        surveyRunProgressBar,
        surveyRunProgressLabel,
        surveyRunProgressPercent,
        onProgressStateChanged: () => {
            updateConvertBtn();
        },
    });

    const surveySourcedataQuickSelectController = createSurveySourcedataQuickSelectController({
        sourcedataQuickSelect,
        sourcedataFileSelect,
        convertExcelFile,
        convertError,
        resolveCurrentProjectPath,
        onProjectChanged: () => {
            cancelActiveSurveyRun();
            resetSurveyImportFormState();
        },
    });

    const surveyWorkflowTemplateCheckController = createSurveyWorkflowTemplateCheckController({
        checkProjectTemplatesBtn,
        surveyVersionWizardApplyBtn,
        convertError,
        conversionLogContainer,
        conversionLogBody,
        toggleLogBtn,
        getSelectedSurveyFilename,
        convertIdColumn,
        appendLog,
        resolveCurrentProjectPath,
        appendSurveyInputToFormData,
        getSelectedSeparator,
        parseJsonResponse,
        setTemplateWorkflowGate: (value) => {
            templateWorkflowGate = (value && typeof value === 'object') ? value : null;
        },
        setTemplateEditorErrorCtaVisible,
        convertInfo,
        buildVersionWizard,
        hideVersionWizard,
        updateConvertBtn,
        hasMultiVersionWizardTasks,
        hasCompleteVersionWizardSelections,
        getCurrentTemplateVersionSelectionSignature,
        setAppliedTemplateVersionSelectionSignature: (value) => {
            appliedTemplateVersionSelectionSignature = String(value || '');
        },
        setVersionWizardRetryGateMode: (value) => {
            versionWizardRetryGateMode = value;
        },
        getTemplateWorkflowGate: () => templateWorkflowGate,
        updateVersionWizardActionState,
    });

    function getSelectedSurveyFile() {
        return (convertExcelFile && convertExcelFile.files && convertExcelFile.files[0])
            ? convertExcelFile.files[0]
            : null;
    }

    function getSelectedSurveyFilename() {
        const selectedFile = getSelectedSurveyFile();
        if (selectedFile && selectedFile.name) {
            return selectedFile.name;
        }
        if (convertServerFilePath) {
            const tokens = convertServerFilePath.split('/');
            return tokens[tokens.length - 1] || convertServerFilePath;
        }
        return '';
    }

    function hasSelectedSurveyInput() {
        return Boolean(getSelectedSurveyFile() || convertServerFilePath);
    }

    function appendSurveyInputToFormData(formData) {
        const selectedFile = getSelectedSurveyFile();
        if (selectedFile) {
            formData.append('excel', selectedFile);
            return { file: selectedFile, filename: selectedFile.name };
        }
        if (convertServerFilePath) {
            formData.append('source_file_path', convertServerFilePath);
            return { file: null, filename: getSelectedSurveyFilename() };
        }
        return { file: null, filename: '' };
    }

    function getSelectedSurveyFingerprint() {
        const selectedFile = getSelectedSurveyFile();
        if (selectedFile) {
            const lastModified = Number.isFinite(Number(selectedFile.lastModified))
                ? Number(selectedFile.lastModified)
                : 0;
            return `upload:${selectedFile.name}:${selectedFile.size}:${lastModified}`;
        }
        if (convertServerFilePath) {
            return `server:${convertServerFilePath}`;
        }
        return '';
    }

    function resetSurveyRefreshFingerprint() {
        lastDetectedSurveyFingerprint = '';
        clearRetryResolutionState();
        clearSurveyPreviewSelectionState();
    }

    function normalizeSurveyTaskName(value) {
        return normalizeNearMatchTaskName(value).replace(/^survey-/, '');
    }

    function getSelectedIdMapFingerprint() {
        const selectedFile = convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0]
            ? convertIdMapFile.files[0]
            : null;
        if (!selectedFile) {
            return '';
        }
        const lastModified = Number.isFinite(Number(selectedFile.lastModified))
            ? Number(selectedFile.lastModified)
            : 0;
        return `id-map:${selectedFile.name}:${selectedFile.size}:${lastModified}`;
    }

    function getSurveyPreviewContextKey({ includeValueOffsets = true } = {}) {
        const templateSelections = getTemplateVersionSelections()
            .map((entry) => ({
                task: normalizeSurveyTaskName(entry && entry.task),
                session: entry && entry.session ? String(entry.session) : '',
                run: entry && entry.run ? String(entry.run) : '',
                version: entry && entry.version ? String(entry.version) : ''
            }))
            .sort((left, right) => {
                const leftKey = `${left.task}::${left.session}::${left.run}::${left.version}`;
                const rightKey = `${right.task}::${right.session}::${right.run}::${right.version}`;
                return leftKey.localeCompare(rightKey);
            });

        return JSON.stringify({
            input: getSelectedSurveyFingerprint(),
            idMap: getSelectedIdMapFingerprint(),
            idColumn: String(convertIdColumn?.value || '').trim(),
            session: String(getSurveySessionValue() || '').trim(),
            sessionColumn: String(convertSessionColumnOverride?.value || '').trim(),
            runColumn: String(convertRunColumnOverride?.value || '').trim(),
            surveyFilter: isAdvancedOptionsEnabled() && convertDatasetName
                ? String(convertDatasetName.value || '').trim().toLowerCase()
                : '',
            language: isAdvancedOptionsEnabled() && convertLanguage
                ? String(convertLanguage.value || 'auto').trim().toLowerCase()
                : 'auto',
            separator: getSelectedSeparator(getSelectedSurveyFilename().toLowerCase()),
            valueOffsetsText: includeValueOffsets && isAdvancedOptionsEnabled() && convertValueOffsets
                ? String(convertValueOffsets.value || '').trim()
                : '',
            nearMatchTasks: getEffectiveNearMatchTasks().map(normalizeSurveyTaskName).sort(),
            templateSelections,
        });
    }

    function clearSurveyPreviewSelectionState() {
        surveyPreviewSelectionState = {
            previewKey: '',
            availableTasks: [],
            selectedTasks: []
        };
        renderTaskValueOffsetEditor();
    }

    function setSurveyPreviewSelectionState(taskSummaries, previewKey = getSurveyPreviewContextKey()) {
        if (!Array.isArray(taskSummaries) || taskSummaries.length === 0) {
            clearSurveyPreviewSelectionState();
            return;
        }

        const availableTasks = taskSummaries
            .map((entry) => normalizeSurveyTaskName(entry && entry.task))
            .filter(Boolean);
        const selectedTasks = taskSummaries
            .filter((entry) => entry && entry.selected !== false)
            .map((entry) => normalizeSurveyTaskName(entry && entry.task))
            .filter(Boolean);

        surveyPreviewSelectionState = {
            previewKey,
            availableTasks,
            selectedTasks: selectedTasks.length > 0 ? selectedTasks : [...availableTasks]
        };
        renderTaskValueOffsetEditor();
    }

    function setSurveyPreviewSelectedTasks(selectedTasks) {
        surveyPreviewSelectionState = {
            ...surveyPreviewSelectionState,
            selectedTasks: Array.isArray(selectedTasks) ? selectedTasks : []
        };
    }

    function hasFreshSurveyPreviewSelectionState() {
        return Boolean(
            surveyPreviewSelectionState.previewKey
            && surveyPreviewSelectionState.availableTasks.length > 0
            && surveyPreviewSelectionState.previewKey === getSurveyPreviewContextKey()
        );
    }

    function isPreviewStaleOnlyByOffsetChanges() {
        if (!surveyPreviewSelectionState.previewKey || surveyPreviewSelectionState.availableTasks.length === 0) {
            return false;
        }

        let previousPayload;
        let currentPayload;
        try {
            previousPayload = JSON.parse(surveyPreviewSelectionState.previewKey);
            currentPayload = JSON.parse(getSurveyPreviewContextKey());
        } catch (_error) {
            return false;
        }

        if (!previousPayload || !currentPayload || typeof previousPayload !== 'object' || typeof currentPayload !== 'object') {
            return false;
        }

        const previousWithoutOffsets = { ...previousPayload, valueOffsetsText: '' };
        const currentWithoutOffsets = { ...currentPayload, valueOffsetsText: '' };

        return (
            JSON.stringify(previousWithoutOffsets) === JSON.stringify(currentWithoutOffsets)
            && String(previousPayload.valueOffsetsText || '') !== String(currentPayload.valueOffsetsText || '')
        );
    }

    function updateSurveyWorkflowHint({
        hasFile,
        blockedByTemplateGate,
        versionSelectionsPending,
        valueOffsetSelectionsPending,
        hasFreshPreviewReview,
        hasSelectedPreviewTasks,
        isConvertRunning,
        isPreviewRunning,
    }) {
        if (!surveyWorkflowHint) {
            return;
        }

        let message = '';
        let className = 'form-text text-muted mb-2';

        if (isConvertRunning) {
            message = 'Step 5 is running. Wait for conversion to finish before changing workflow inputs.';
            className = 'form-text text-warning mb-2';
        } else if (isPreviewRunning) {
            message = 'Step 4 is running. Review output when preview completes.';
            className = 'form-text text-info mb-2';
        } else if (!hasFile) {
            message = 'Step 1: Choose a survey source file to begin.';
        } else if (versionSelectionsPending) {
            message = 'Apply questionnaire version selections, then continue with Step 4 (Preview).';
            className = 'form-text text-warning mb-2';
        } else if (valueOffsetSelectionsPending) {
            message = 'Apply manual offsets, then continue with Step 4 (Preview).';
            className = 'form-text text-warning mb-2';
        } else if (blockedByTemplateGate) {
            message = 'Project template metadata is incomplete. Finish template edits, then rerun Step 4 (Preview).';
            className = 'form-text text-warning mb-2';
        } else if (!hasFreshPreviewReview) {
            if (isPreviewStaleOnlyByOffsetChanges()) {
                message = 'Manual offsets changed. Run Step 4 (Preview) again to validate the new scale handling before Step 5 unlocks.';
            } else {
                message = 'Run Step 4 (Preview) after your latest changes before converting.';
            }
            className = 'form-text text-warning mb-2';
        } else if (!hasSelectedPreviewTasks) {
            message = 'Select at least one survey in Preview Review, then continue to Step 5.';
            className = 'form-text text-warning mb-2';
        } else {
            message = 'Ready for Step 5: Convert selected surveys.';
            className = 'form-text text-success mb-2';
        }

        surveyWorkflowHint.className = className;
        surveyWorkflowHint.textContent = message;
    }

    function getSelectedSurveyTasksForConversion() {
        const selectedTasks = Array.isArray(surveyPreviewSelectionState.selectedTasks)
            ? surveyPreviewSelectionState.selectedTasks.map(normalizeSurveyTaskName).filter(Boolean)
            : [];
        const availableTaskSet = new Set(
            (surveyPreviewSelectionState.availableTasks || []).map(normalizeSurveyTaskName).filter(Boolean)
        );
        return selectedTasks.filter((task) => availableTaskSet.has(task));
    }

    async function refreshSurveyColumnsBeforeRun() {
        const selectedFile = getSelectedSurveyFile();
        const sourceFilePath = selectedFile ? '' : convertServerFilePath;
        const currentFingerprint = getSelectedSurveyFingerprint();

        if (!currentFingerprint) {
            return;
        }

        // Server-picked files are refreshed every run so external saves are picked up.
        const shouldRefresh = Boolean(sourceFilePath) || currentFingerprint !== lastDetectedSurveyFingerprint;
        if (!shouldRefresh) {
            return;
        }

        await detectFileColumns(selectedFile, sourceFilePath);
    }

    function enrichSurveyRunErrorMessage(message) {
        const baseMessage = String(message || 'Conversion failed');
        const normalized = baseMessage.toLowerCase();
        const isGenericPatternMessage = normalized === 'the string did not match the expected pattern.';
        if (isGenericPatternMessage) {
            return 'Server response could not be parsed. Please retry once. If it persists, check backend logs for survey prepare/preview endpoint errors.';
        }
        const isDuplicateNormalizationError = normalized.includes('duplicate entries after normalization');
        if (!isDuplicateNormalizationError) {
            return baseMessage;
        }

        if (getSelectedSurveyFile()) {
            return `${baseMessage} If you edited the spreadsheet in Excel, save it and select the file again before retrying.`;
        }

        return baseMessage;
    }

    function summarizeServerResponseText(rawText) {
        const compact = String(rawText || '')
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        if (!compact) {
            return '';
        }
        if (compact.length <= 220) {
            return compact;
        }
        return `${compact.slice(0, 217)}...`;
    }

    async function parseJsonResponse(response, requestLabel = 'Request') {
        const statusCode = Number(response && response.status);
        const statusText = String((response && response.statusText) || '').trim();
        const statusLabel = Number.isFinite(statusCode) && statusCode > 0
            ? `HTTP ${statusCode}${statusText ? ` ${statusText}` : ''}`
            : 'HTTP response';

        let responseText = '';
        try {
            responseText = await response.text();
        } catch (_readError) {
            throw new Error(`${requestLabel} returned an unreadable response (${statusLabel}).`);
        }

        const trimmed = String(responseText || '').trim();
        if (!trimmed) {
            return {};
        }

        try {
            return JSON.parse(trimmed);
        } catch (_parseError) {
            const snippet = summarizeServerResponseText(trimmed);
            const suffix = snippet ? ` Response: ${snippet}` : '';
            throw new Error(`${requestLabel} returned a non-JSON response (${statusLabel}).${suffix}`);
        }
    }

    function normalizeNearMatchTaskName(value) {
        return String(value || '').trim().toLowerCase();
    }

    function collectNearMatchCandidates(payload) {
        if (!Array.isArray(payload && payload.near_match_candidates)) {
            return [];
        }
        return payload.near_match_candidates
            .map((candidate) => {
                const source = String(candidate && candidate.source_column || '').trim();
                const target = String(candidate && candidate.target_item || '').trim();
                const task = normalizeNearMatchTaskName(candidate && candidate.task);
                const run = candidate && candidate.run !== undefined ? candidate.run : null;
                if (!source || !target || !task) {
                    return null;
                }
                return { source, target, task, run };
            })
            .filter(Boolean);
    }

    function buildNearMatchConfirmationMessage(payload, actionLabel) {
        const candidates = collectNearMatchCandidates(payload);
        if (candidates.length === 0) {
            return '';
        }

        const lines = candidates.map((candidate) => {
            const run = (candidate.run !== undefined && candidate.run !== null && String(candidate.run).trim() !== '')
                ? `, run ${candidate.run}`
                : '';
            return `- ${candidate.source} -> ${candidate.target} (task ${candidate.task}${run})`;
        });

        return [
            `Safe near item matches detected during ${actionLabel}.`,
            '',
            'Exact matching is always used first.',
            'These optional near matches only tolerate minimal differences (separator/zero-padding) and are count-guarded.',
            '',
            `Apply ${candidates.length} near match(es) and rerun?`,
            '',
            ...lines,
        ].join('\n');
    }

    function promptNearMatchSelection(payload, actionLabel) {
        const candidates = collectNearMatchCandidates(payload);
        if (candidates.length === 0) {
            return Promise.resolve({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
        }

        const taskCounts = new Map();
        candidates.forEach((candidate) => {
            const count = taskCounts.get(candidate.task) || 0;
            taskCounts.set(candidate.task, count + 1);
        });
        const tasks = Array.from(taskCounts.entries())
            .sort((left, right) => left[0].localeCompare(right[0]))
            .map(([task, count]) => ({ task, count }));

        if (!(window.bootstrap && typeof window.bootstrap.Modal === 'function')) {
            const promptMessage = buildNearMatchConfirmationMessage(payload, actionLabel);
            const approved = Boolean(promptMessage) && window.confirm(promptMessage);
            return Promise.resolve({
                approved,
                selectedTasks: approved ? tasks.map((entry) => entry.task) : [],
                selectedCandidateCount: approved ? candidates.length : 0,
            });
        }

        return new Promise((resolve) => {
            const modalEl = document.createElement('div');
            modalEl.className = 'modal fade';
            modalEl.tabIndex = -1;
            modalEl.setAttribute('aria-hidden', 'true');

            const actionText = escapeHtml(String(actionLabel || 'preview'));
            const taskChecklistHtml = tasks
                .map((entry, index) => {
                    const task = escapeHtml(entry.task);
                    const countLabel = `${entry.count} item${entry.count === 1 ? '' : 's'}`;
                    return `
                        <div class="form-check mb-2">
                            <input
                                class="form-check-input"
                                type="checkbox"
                                id="nearMatchTask_${index}"
                                value="${task}"
                                data-role="near-task-checkbox"
                                checked
                            >
                            <label class="form-check-label" for="nearMatchTask_${index}">
                                <strong>${task}</strong>
                                <span class="text-muted small">(${countLabel})</span>
                            </label>
                        </div>
                    `;
                })
                .join('');

            const tableRowsHtml = candidates
                .map((candidate) => {
                    const runLabel = (candidate.run !== undefined && candidate.run !== null && String(candidate.run).trim() !== '')
                        ? escapeHtml(String(candidate.run))
                        : '-';
                    return `
                        <tr data-task="${escapeHtml(candidate.task)}">
                            <td><code>${escapeHtml(candidate.source)}</code></td>
                            <td><code>${escapeHtml(candidate.target)}</code></td>
                            <td>${escapeHtml(candidate.task)}</td>
                            <td>${runLabel}</td>
                        </tr>
                    `;
                })
                .join('');

            const summaryHtml = tasks
                .map(entry => `<strong>${escapeHtml(entry.task)}</strong>: ${entry.count} item${entry.count === 1 ? '' : 's'}`)
                .join(', ');

            modalEl.innerHTML = `
                <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <div class="d-flex align-items-center align-self-center overflow-hidden w-100 me-3">
                                <h5 class="modal-title flex-shrink-0">Review Safe Near Item Matches</h5>
                                <div class="text-muted ms-3 border-start ps-3 small text-truncate" title="${summaryHtml.replace(/<[^>]+>/g, '')}">
                                    ${summaryHtml}
                                </div>
                            </div>
                            <button type="button" class="btn-close" aria-label="Close" data-role="close-btn"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-1">Safe near item matches were detected during ${actionText}.</p>
                            <p class="text-muted small mb-3">Exact matching runs first. Near matching only allows minimal separator and zero-padding differences and only when count-safe checks pass.</p>

                            <div class="row g-3">
                                <div class="col-12 col-lg-4">
                                    <div class="d-flex gap-2 mb-2">
                                        <button type="button" class="btn btn-sm btn-outline-secondary" data-role="select-all-tasks">Select all</button>
                                        <button type="button" class="btn btn-sm btn-outline-secondary" data-role="clear-all-tasks">Clear all</button>
                                    </div>
                                    <div class="border rounded p-2" style="max-height: 360px; overflow-y: auto;">
                                        ${taskChecklistHtml}
                                    </div>
                                    <small class="text-muted d-block mt-2">Tick the survey tasks you want to allow for near matching.</small>
                                </div>
                                <div class="col-12 col-lg-8">
                                    <div class="table-responsive border rounded" style="max-height: 360px; overflow-y: auto;">
                                        <table class="table table-sm table-striped align-middle mb-0">
                                            <thead class="table-light" style="position: sticky; top: 0; z-index: 1;">
                                                <tr>
                                                    <th scope="col">Source Column</th>
                                                    <th scope="col">Template Item</th>
                                                    <th scope="col">Task</th>
                                                    <th scope="col">Run</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${tableRowsHtml}
                                            </tbody>
                                        </table>
                                    </div>
                                    <small class="text-muted d-block mt-2">All candidate near matches are shown above.</small>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <span class="me-auto text-muted small" data-role="selection-meta"></span>
                            <button type="button" class="btn btn-outline-secondary" data-role="cancel-btn">Cancel</button>
                            <button type="button" class="btn btn-primary" data-role="apply-btn">Apply Selected Tasks and Rerun</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modalEl);

            const modal = new window.bootstrap.Modal(modalEl, {
                backdrop: 'static',
                keyboard: false,
            });

            const taskCheckboxes = Array.from(
                modalEl.querySelectorAll('input[data-role="near-task-checkbox"]')
            );
            const selectionMeta = modalEl.querySelector('[data-role="selection-meta"]');
            const applyBtn = modalEl.querySelector('[data-role="apply-btn"]');
            const cancelBtn = modalEl.querySelector('[data-role="cancel-btn"]');
            const closeBtn = modalEl.querySelector('[data-role="close-btn"]');
            const selectAllBtn = modalEl.querySelector('[data-role="select-all-tasks"]');
            const clearAllBtn = modalEl.querySelector('[data-role="clear-all-tasks"]');
            const tableRows = Array.from(modalEl.querySelectorAll('tbody tr[data-task]'));

            let pendingResult = null;

            function collectSelectionState() {
                const selectedTasks = taskCheckboxes
                    .filter((checkbox) => checkbox.checked)
                    .map((checkbox) => normalizeNearMatchTaskName(checkbox.value));
                const selectedTaskSet = new Set(selectedTasks);
                const selectedCandidateCount = candidates.reduce((count, candidate) => {
                    return count + (selectedTaskSet.has(candidate.task) ? 1 : 0);
                }, 0);
                return {
                    selectedTasks,
                    selectedTaskSet,
                    selectedCandidateCount,
                };
            }

            function updateSelectionUi() {
                const state = collectSelectionState();
                if (selectionMeta) {
                    selectionMeta.textContent = `Selected surveys: ${state.selectedTasks.length}/${tasks.length} | Selected items: ${state.selectedCandidateCount}/${candidates.length}`;
                }
                if (applyBtn) {
                    applyBtn.disabled = state.selectedTasks.length === 0;
                }
                tableRows.forEach((row) => {
                    const task = normalizeNearMatchTaskName(row.getAttribute('data-task') || '');
                    const selected = state.selectedTaskSet.has(task);
                    row.classList.toggle('table-secondary', !selected);
                    row.classList.toggle('opacity-50', !selected);
                });
            }

            function setAllTaskSelections(checked) {
                taskCheckboxes.forEach((checkbox) => {
                    checkbox.checked = checked;
                });
                updateSelectionUi();
            }

            function finalizeAndClose(result) {
                pendingResult = result;
                modal.hide();
            }

            taskCheckboxes.forEach((checkbox) => {
                checkbox.addEventListener('change', updateSelectionUi);
            });

            if (selectAllBtn) {
                selectAllBtn.addEventListener('click', () => setAllTaskSelections(true));
            }
            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', () => setAllTaskSelections(false));
            }
            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    finalizeAndClose({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
                });
            }
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    finalizeAndClose({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
                });
            }
            if (applyBtn) {
                applyBtn.addEventListener('click', () => {
                    const state = collectSelectionState();
                    if (state.selectedTasks.length === 0) {
                        return;
                    }
                    finalizeAndClose({
                        approved: true,
                        selectedTasks: state.selectedTasks,
                        selectedCandidateCount: state.selectedCandidateCount,
                    });
                });
            }

            modalEl.addEventListener('hidden.bs.modal', () => {
                const result = pendingResult || {
                    approved: false,
                    selectedTasks: [],
                    selectedCandidateCount: 0,
                };
                modal.dispose();
                modalEl.remove();
                resolve(result);
            }, { once: true });

            updateSelectionUi();
            modal.show();
        });
    }

    function normalizeTaskValueOffsets(offsetMap) {
        return normalizeTaskValueOffsetsMap(offsetMap, normalizeNearMatchTaskName);
    }

    function createTaskValueOffsetRow(task = '', offset = null) {
        return surveyValueOffsetEditorController.createTaskValueOffsetRow(task, offset);
    }

    function getAvailableSurveyTasksForValueOffsets() {
        return surveyValueOffsetEditorController.getAvailableSurveyTasksForValueOffsets();
    }

    function getTaskValueOffsetMapFromEditorState() {
        return surveyValueOffsetEditorController.getTaskValueOffsetMapFromEditorState();
    }

    function getCurrentTaskValueOffsetSelectionSignature() {
        return surveyValueOffsetEditorController.getCurrentTaskValueOffsetSelectionSignature();
    }

    function hasManualTaskValueOffsets() {
        return surveyValueOffsetEditorController.hasManualTaskValueOffsets();
    }

    function hasIncompleteTaskValueOffsetRows() {
        return surveyValueOffsetEditorController.hasIncompleteTaskValueOffsetRows();
    }

    function hasAppliedTaskValueOffsetSelections() {
        return surveyValueOffsetEditorController.hasAppliedTaskValueOffsetSelections();
    }

    function updateTaskValueOffsetApplyState() {
        surveyValueOffsetEditorController.updateTaskValueOffsetApplyState();
    }

    function getPreferredTaskValueOffsetTask() {
        return surveyValueOffsetEditorController.getPreferredTaskValueOffsetTask();
    }

    function syncTaskValueOffsetTextFromState() {
        surveyValueOffsetEditorController.syncTaskValueOffsetTextFromState();
    }

    function setTaskValueOffsetEditorStateFromText(rawText) {
        surveyValueOffsetEditorController.setTaskValueOffsetEditorStateFromText(rawText);
    }

    function clearTaskValueOffsetEditorState() {
        surveyValueOffsetEditorController.clearTaskValueOffsetEditorState();
    }

    function ensureTaskValueOffsetEditorRow(task = '') {
        return surveyValueOffsetEditorController.ensureTaskValueOffsetEditorRow(task);
    }

    function focusTaskValueOffsetEditor(rowId = null) {
        surveyValueOffsetEditorController.focusTaskValueOffsetEditor(rowId);
    }

    function renderTaskValueOffsetEditor() {
        return surveyValueOffsetEditorController.renderTaskValueOffsetEditor();
    }

    function handleTaskValueOffsetEditorChanged() {
        surveyValueOffsetEditorController.handleTaskValueOffsetEditorChanged();
    }

    function clearManualValueOffsetAdvice() {
        surveyValueOffsetEditorController.clearManualValueOffsetAdvice();
    }

    function handleApplyTaskValueOffsetsClick() {
        surveyValueOffsetEditorController.handleApplyTaskValueOffsetsClick();
    }

    function ensureSurveyAdvancedOptionsVisible() {
        if (convertAdvancedToggle && !convertAdvancedToggle.checked) {
            convertAdvancedToggle.checked = true;
        }
        applyAdvancedOptionsState();
        if (
            surveyAdvancedOptionsPanel
            && window.bootstrap
            && window.bootstrap.Collapse
        ) {
            window.bootstrap.Collapse.getOrCreateInstance(
                surveyAdvancedOptionsPanel,
                { toggle: false },
            ).show();
        }
    }

    function openAdvancedOptionsValueOffsetEditor() {
        ensureSurveyAdvancedOptionsVisible();
        focusTaskValueOffsetEditor();
    }

    function parseTaskValueOffsetsText(rawText) {
        return parseTaskValueOffsetsTextWithNormalizer(rawText, normalizeNearMatchTaskName);
    }

    function getManualTaskValueOffsets() {
        return surveyValueOffsetEditorController.getManualTaskValueOffsets();
    }

    function getManualValueOffsetReviewMessage(payload, mode) {
        const modeLabel = mode === 'convert' ? 'conversion' : 'preview';
        const task = normalizeNearMatchTaskName(payload && payload.task) || 'unknown task';
        const itemId = String(payload && payload.item_id || '').trim();
        const rawValue = payload && payload.raw_value;
        const backendMessage = String(payload && payload.message || '').trim();
        const expectedLevels = Array.isArray(payload && payload.expected_levels)
            ? payload.expected_levels.map((entry) => String(entry)).filter(Boolean)
            : [];
        const suggestedOffsets = collectSuggestedValueOffsets(payload);
        const configuredOffset = parseNumericOffsetValue(payload && payload.configured_offset);
        const offsetEvidence = (
            payload
            && payload.offset_evidence
            && typeof payload.offset_evidence === 'object'
        ) ? payload.offset_evidence : null;
        const summary = offsetEvidence && typeof offsetEvidence.summary_message === 'string'
            ? offsetEvidence.summary_message.trim()
            : '';
        const evidenceClassification = offsetEvidence && typeof offsetEvidence.classification === 'string'
            ? offsetEvidence.classification.trim().toLowerCase()
            : '';
        const classificationHint = evidenceClassification === 'structural_offset_likely'
            ? 'Flag: this pattern looks like a possible task-wide scale offset.'
            : evidenceClassification === 'item_issues_likely'
                ? 'Flag: this pattern may not be a single task-wide scale offset.'
                : '';
        const reviewSummary = summary || classificationHint || backendMessage;

        const lines = [
            `Survey ${modeLabel} stopped because task ${task} has values outside the template scale.`,
            itemId ? `Item: ${itemId}` : null,
            rawValue !== undefined ? `Observed value: ${String(rawValue)}` : null,
            expectedLevels.length > 0 ? `Expected levels: ${expectedLevels.join(', ')}` : null,
            configuredOffset !== null
                ? `Current manual offset: ${formatSignedOffset(configuredOffset)} (did not resolve this dataset)`
                : null,
            suggestedOffsets.length > 0
                ? `Suggested offset${suggestedOffsets.length === 1 ? '' : 's'}: ${suggestedOffsets.map((entry) => formatSignedOffset(entry)).join(', ')}`
                : null,
            reviewSummary || null,
            'If you are certain this task is coded on the wrong numeric scale, enter a manual task offset below and run Preview again.',
        ].filter(Boolean);

        return lines.join('\n');
    }

    function showManualValueOffsetReview(payload, mode, selectedValueOffsets = {}) {
        ensureSurveyAdvancedOptionsVisible();
        if (convertValueOffsetAdvice) {
            convertValueOffsetAdvice.textContent = getManualValueOffsetReviewMessage(payload, mode);
            convertValueOffsetAdvice.classList.remove('d-none');
        }

        const task = normalizeNearMatchTaskName(payload && payload.task);
        const configuredOffset = parseNumericOffsetValue(payload && payload.configured_offset);
        if (
            task
            && configuredOffset !== null
            && isConfiguredOffsetFailureForCurrentSelection(payload, selectedValueOffsets)
        ) {
            convertInfo.textContent = `Manual task offset ${formatSignedOffset(configuredOffset)} for ${task} did not resolve this dataset. Update Advanced options and run Preview again.`;
        } else {
            convertInfo.textContent = 'Review the task value offset guidance in Advanced options, then run Preview again if you want to apply a manual scale adjustment.';
        }
        convertInfo.classList.remove('d-none');
        appendLog(getManualValueOffsetReviewMessage(payload, mode), 'warning');
        const rowId = ensureTaskValueOffsetEditorRow(task);
        focusTaskValueOffsetEditor(rowId);
    }

    function clearRetryResolutionState() {
        confirmedNearMatchTasks = [];
    }

    function isAbortError(error) {
        if (!error) {
            return false;
        }
        const errorName = String(error.name || '').toLowerCase();
        if (errorName === 'aborterror') {
            return true;
        }
        const errorMessage = String(error.message || '').toLowerCase();
        return errorMessage.includes('aborted') || errorMessage.includes('aborterror');
    }

    function setActiveSurveyRun(mode, controller) {
        activeRunMode = mode;
        activeRunAbortController = controller;
        activeRunCancelledByUser = false;
    }

    function clearActiveSurveyRun(mode = null) {
        if (mode && activeRunMode && activeRunMode !== mode) {
            return;
        }
        activeRunMode = null;
        activeRunAbortController = null;
        activeRunCancelledByUser = false;
    }

    function cancelActiveSurveyRun() {
        if (!activeRunAbortController) {
            return false;
        }
        activeRunCancelledByUser = true;
        activeRunAbortController.abort();
        return true;
    }

    function setSurveyRunProgress(options) {
        surveyWorkflowProgressController.setSurveyRunProgress(options);
    }

    function hideSurveyRunProgress() {
        surveyWorkflowProgressController.hideSurveyRunProgress();
    }

    function startSurveyRunProgress(mode) {
        surveyWorkflowProgressController.startSurveyRunProgress(mode);
    }

    function advanceSurveyRunProgress(mode, percent, label) {
        surveyWorkflowProgressController.advanceSurveyRunProgress(mode, percent, label);
    }

    function pauseSurveyRunProgress(mode, label) {
        surveyWorkflowProgressController.pauseSurveyRunProgress(mode, label);
    }

    function resumeSurveyRunProgress(mode, percent, label) {
        surveyWorkflowProgressController.resumeSurveyRunProgress(mode, percent, label);
    }

    function finishSurveyRunProgress(mode, outcome) {
        surveyWorkflowProgressController.finishSurveyRunProgress(mode, outcome);
    }

    function mergeNearMatchTasks(existingTasks, nextTasks) {
        return [...new Set(
            ([])
                .concat(Array.isArray(existingTasks) ? existingTasks : [])
                .concat(Array.isArray(nextTasks) ? nextTasks : [])
                .map((task) => normalizeNearMatchTaskName(task))
                .filter(Boolean)
        )];
    }

    function offsetsAreEqual(left, right, tolerance = 1e-9) {
        const leftValue = Number(left);
        const rightValue = Number(right);
        if (!Number.isFinite(leftValue) || !Number.isFinite(rightValue)) {
            return false;
        }
        return Math.abs(leftValue - rightValue) <= tolerance;
    }

    function getAppliedTaskOffset(offsetMap, taskName) {
        const normalizedOffsets = normalizeTaskValueOffsets(offsetMap);
        const normalizedTask = normalizeNearMatchTaskName(taskName);
        if (normalizedTask && Object.prototype.hasOwnProperty.call(normalizedOffsets, normalizedTask)) {
            return normalizedOffsets[normalizedTask];
        }
        if (Object.prototype.hasOwnProperty.call(normalizedOffsets, '*')) {
            return normalizedOffsets['*'];
        }
        return null;
    }

    function isConfiguredOffsetFailureForCurrentSelection(payload, selectedOffsets) {
        const configuredOffset = parseNumericOffsetValue(payload && payload.configured_offset);
        if (configuredOffset === null) {
            return false;
        }
        const task = normalizeNearMatchTaskName(payload && payload.task);
        const appliedOffset = getAppliedTaskOffset(selectedOffsets, task);
        if (appliedOffset === null) {
            return false;
        }
        return offsetsAreEqual(configuredOffset, appliedOffset);
    }

    function getEffectiveNearMatchTasks(nextTasks = null) {
        return mergeNearMatchTasks(
            confirmedNearMatchTasks,
            Array.isArray(nextTasks) ? nextTasks : []
        );
    }

    function getEffectiveTaskValueOffsets(retryOffsets = null) {
        const appliedManualOffsets = hasAppliedTaskValueOffsetSelections()
            ? getManualTaskValueOffsets()
            : {};
        return normalizeTaskValueOffsets({
            ...appliedManualOffsets,
            ...normalizeTaskValueOffsets(retryOffsets),
        });
    }

    function hasCompleteVersionWizardSelections() {
        const multivariantTasks = (
            versionWizardState
            && versionWizardState.multivariantTasks
            && typeof versionWizardState.multivariantTasks === 'object'
        )
            ? versionWizardState.multivariantTasks
            : {};

        const entries = Object.entries(multivariantTasks).filter(([, info]) => {
            return Array.isArray(info?.versions) && info.versions.length > 1;
        });
        if (entries.length === 0) {
            return true;
        }

        const contexts = deriveDetectedContexts(
            versionWizardState?.taskRuns || {},
            versionWizardState?.previewParticipants || [],
            versionWizardState?.detectedSessions || []
        );
        const effectiveContexts = Array.isArray(contexts) && contexts.length > 0
            ? contexts
            : [{ session: null, run: null }];

        return entries.every(([task, info]) => {
            const allowedVersions = info.versions
                .map((value) => String(value || '').trim())
                .filter(Boolean);

            if (allowedVersions.length <= 1) {
                return true;
            }

            return effectiveContexts.every((context) => {
                const selectionKey = buildVersionSelectionKey({
                    task,
                    session: context && Object.prototype.hasOwnProperty.call(context, 'session')
                        ? context.session
                        : null,
                    run: context && Object.prototype.hasOwnProperty.call(context, 'run')
                        ? context.run
                        : null,
                });
                const selectedVersion = String(selectedTemplateVersions[selectionKey] || '').trim();
                return Boolean(selectedVersion && allowedVersions.includes(selectedVersion));
            });
        });
    }

    function applyPreparedSurveyWorkflowContext(data) {
        const multivariantTasks = (data && typeof data.multivariant_tasks === 'object' && data.multivariant_tasks)
            ? data.multivariant_tasks
            : {};
        if (Object.keys(multivariantTasks).length > 0) {
            buildVersionWizard(
                multivariantTasks,
                (data && typeof data.task_runs === 'object' && data.task_runs) || {},
                Array.isArray(data?.preview_participants) ? data.preview_participants : [],
                Array.isArray(data?.detected_sessions) ? data.detected_sessions : []
            );
        } else {
            hideVersionWizard();
        }

        templateWorkflowGate = (
            data
            && data.workflow_gate
            && typeof data.workflow_gate === 'object'
        ) ? data.workflow_gate : null;
        setTemplateEditorErrorCtaVisible(Boolean(templateWorkflowGate && templateWorkflowGate.blocked));

        return multivariantTasks;
    }

    function prefersServerPicker() {
        return Boolean(
            window.PrismFileSystemMode
            && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
            && window.PrismFileSystemMode.prefersServerPicker()
        );
    }

    function applySurveyPickerUiState() {
        const connectedToServer = prefersServerPicker();

        if (browseServerSurveyFileBtn) {
            browseServerSurveyFileBtn.classList.toggle('d-none', !connectedToServer);
        }

        if (convertExcelFile) {
            convertExcelFile.disabled = connectedToServer;
            convertExcelFile.title = connectedToServer ? 'Connected-to-server mode: use Browse Server File.' : '';
        }
    }

    async function pickServerSurveyFile() {
        if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFile === 'function')) {
            return '';
        }
        return window.PrismFileSystemMode.pickFile({
            title: 'Select Survey File on Server',
            confirmLabel: 'Use This File',
            extensions: '.xlsx,.lsa,.csv,.tsv,.sav,.rds,.rdata,.rda',
            startPath: convertServerFilePath || ''
        });
    }

    function normalizeVersionSelectionSession(session) {
        const value = String(session || '').trim();
        if (!value) return null;
        const label = value.replace(/^ses-/i, '').replace(/[^a-zA-Z0-9]+/g, '');
        if (!label) return null;
        return `ses-${label}`;
    }

    function normalizeVersionSelectionRun(run) {
        if (run === null || run === undefined || run === '') return null;
        const value = String(run || '').trim();
        if (!value) return null;
        const label = value.replace(/^run-/i, '').replace(/[^a-zA-Z0-9]+/g, '');
        if (!label) return null;
        return `run-${label}`;
    }

    function buildVersionSelectionKey({ task, session = null, run = null }) {
        const normalizedTask = String(task || '').trim().toLowerCase();
        const normalizedSession = normalizeVersionSelectionSession(session) || 'base';
        const normalizedRunValue = normalizeVersionSelectionRun(run);
        const normalizedRun = normalizedRunValue === null ? 'base' : normalizedRunValue;
        return `${normalizedTask}::${normalizedSession}::${normalizedRun}`;
    }

    function getTimelineRunSortMeta(value) {
        const normalizedValue = normalizeVersionSelectionRun(value);
        if (!normalizedValue) {
            return { group: 2, order: Number.MAX_SAFE_INTEGER, token: '' };
        }

        const token = normalizedValue.replace(/^run-/i, '');
        const numericMatch = token.match(/^0*(\d+)$/);
        if (numericMatch) {
            return { group: 0, order: Number(numericMatch[1]), token };
        }

        return { group: 1, order: Number.MAX_SAFE_INTEGER, token: token.toLowerCase() };
    }

    function getTemplateVersionSelections() {
        return Object.entries(selectedTemplateVersions)
            .map(([key, version]) => {
                const [task, sessionToken, runToken] = String(key).split('::');
                const cleanTask = String(task || '').trim().toLowerCase();
                const cleanVersion = String(version || '').trim();
                const normalizedRun = normalizeVersionSelectionRun(runToken);
                if (!cleanTask || !cleanVersion) return null;
                return {
                    task: cleanTask,
                    session: sessionToken && sessionToken !== 'base' ? sessionToken : null,
                    run: normalizedRun,
                    version: cleanVersion
                };
            })
            .filter(Boolean);
    }

    function hasMultiVersionWizardTasks() {
        return Object.values(versionWizardState?.multivariantTasks || {}).some((info) => {
            return Array.isArray(info?.versions) && info.versions.length > 1;
        });
    }

    function getCurrentTemplateVersionSelectionSignature() {
        if (!hasMultiVersionWizardTasks()) {
            return '';
        }

        const multivariantTasks = Object.entries(versionWizardState?.multivariantTasks || {})
            .map(([task, info]) => {
                const versions = Array.isArray(info?.versions)
                    ? info.versions.map((value) => String(value || '').trim()).filter(Boolean).sort()
                    : [];

                return {
                    task: normalizeSurveyTaskName(task),
                    versions,
                };
            })
            .filter((entry) => entry.task && entry.versions.length > 1)
            .sort((left, right) => left.task.localeCompare(right.task));

        const selections = getTemplateVersionSelections()
            .map((entry) => ({
                task: normalizeSurveyTaskName(entry && entry.task),
                session: entry && entry.session ? String(entry.session) : '',
                run: entry && entry.run ? String(entry.run) : '',
                version: entry && entry.version ? String(entry.version) : '',
            }))
            .sort((left, right) => {
                const leftKey = `${left.task}::${left.session}::${left.run}::${left.version}`;
                const rightKey = `${right.task}::${right.session}::${right.run}::${right.version}`;
                return leftKey.localeCompare(rightKey);
            });

        return JSON.stringify({ multivariantTasks, selections });
    }

    function hasAppliedVersionWizardSelections() {
        if (!hasMultiVersionWizardTasks()) {
            return true;
        }
        if (!hasCompleteVersionWizardSelections()) {
            return false;
        }

        const currentSignature = getCurrentTemplateVersionSelectionSignature();
        return Boolean(
            currentSignature
            && appliedTemplateVersionSelectionSignature
            && currentSignature === appliedTemplateVersionSelectionSignature
        );
    }

    function updateVersionWizardActionState() {
        const wizardVisible = Boolean(
            surveyVersionWizard
            && !surveyVersionWizard.classList.contains('d-none')
            && hasMultiVersionWizardTasks()
        );
        const hasCompleteSelections = hasCompleteVersionWizardSelections();
        const hasAppliedSelections = wizardVisible && hasAppliedVersionWizardSelections();

        if (surveyVersionWizardApplyBtn) {
            surveyVersionWizardApplyBtn.classList.toggle('d-none', !wizardVisible);
            surveyVersionWizardApplyBtn.disabled = !wizardVisible || !hasCompleteSelections || isConvertRunning || isPreviewRunning;
            surveyVersionWizardApplyBtn.innerHTML = hasAppliedSelections
                ? '<i class="fas fa-check me-2"></i>Questionnaire Versions Applied'
                : '<i class="fas fa-list-check me-2"></i>Use These Versions';
            surveyVersionWizardApplyBtn.classList.remove('btn-outline-primary', 'btn-success');
            surveyVersionWizardApplyBtn.classList.add(hasAppliedSelections ? 'btn-success' : 'btn-outline-primary');

            if (!wizardVisible) {
                surveyVersionWizardApplyBtn.removeAttribute('title');
            } else if (!hasCompleteSelections) {
                surveyVersionWizardApplyBtn.title = 'Choose a version for each questionnaire context first.';
            } else if (isConvertRunning || isPreviewRunning) {
                surveyVersionWizardApplyBtn.title = 'Wait for the current run to finish.';
            } else if (hasAppliedSelections) {
                surveyVersionWizardApplyBtn.title = 'Preview is unlocked for the current questionnaire version selection.';
            } else {
                surveyVersionWizardApplyBtn.title = 'Apply these questionnaire versions before Preview validation can run.';
            }
        }

        if (surveyVersionWizardStatus) {
            surveyVersionWizardStatus.classList.toggle('d-none', !wizardVisible);
            surveyVersionWizardStatus.classList.remove('text-muted', 'text-success');

            if (!wizardVisible) {
                surveyVersionWizardStatus.textContent = '';
            } else if (hasAppliedSelections) {
                surveyVersionWizardStatus.classList.add('text-success');
                surveyVersionWizardStatus.textContent = 'Selections applied. Preview validation is available.';
            } else {
                surveyVersionWizardStatus.classList.add('text-muted');
                surveyVersionWizardStatus.textContent = 'Review the selectors, then click Use These Versions before running Preview validation.';
            }
        }
    }

    function hideVersionWizard() {
        if (surveyVersionWizard) surveyVersionWizard.classList.add('d-none');
        if (surveyVersionWizardBody) surveyVersionWizardBody.innerHTML = '';
        if (surveyVersionWizardCount) surveyVersionWizardCount.textContent = '';
        selectedTemplateVersions = {};
        appliedTemplateVersionSelectionSignature = '';
        versionWizardState = { multivariantTasks: {}, taskRuns: {}, previewParticipants: [], detectedSessions: [] };
        updateVersionWizardActionState();
    }

    function normalizeTimelineSessionToken(value) {
        return String(value || '')
            .trim()
            .replace(/^ses-/, '')
            .replace(/[_\s]+/g, '-');
    }

    function getTimelineSessionSortMeta(value) {
        const token = normalizeTimelineSessionToken(value);
        if (!token) {
            return { group: 2, order: Number.MAX_SAFE_INTEGER, token: '' };
        }

        const aliasOrder = [
            'screening',
            'baseline',
            'base',
            'pre',
            'pretest',
            'before',
            'start',
            'mid',
            'during',
            'post',
            'posttest',
            'after',
            'followup',
            'follow-up',
            'fu',
            'end'
        ];
        const aliasIndex = aliasOrder.indexOf(token.toLowerCase());
        if (aliasIndex >= 0) {
            return { group: 0, order: aliasIndex, token };
        }

        return { group: 1, order: Number.MAX_SAFE_INTEGER, token };
    }

    function compareTimelineSessions(left, right) {
        const leftMeta = getTimelineSessionSortMeta(left);
        const rightMeta = getTimelineSessionSortMeta(right);
        if (leftMeta.group !== rightMeta.group) {
            return leftMeta.group - rightMeta.group;
        }
        if (leftMeta.order !== rightMeta.order) {
            return leftMeta.order - rightMeta.order;
        }
        return String(left || '').localeCompare(String(right || ''));
    }

    function compareTimelineContexts(left, right) {
        const sessionCompare = compareTimelineSessions(left?.session, right?.session);
        if (sessionCompare !== 0) {
            return sessionCompare;
        }
        const leftMeta = getTimelineRunSortMeta(left?.run);
        const rightMeta = getTimelineRunSortMeta(right?.run);
        if (leftMeta.group !== rightMeta.group) {
            return leftMeta.group - rightMeta.group;
        }
        if (leftMeta.order !== rightMeta.order) {
            return leftMeta.order - rightMeta.order;
        }
        return leftMeta.token.localeCompare(rightMeta.token);
    }

    function deriveDetectedContexts(taskRuns, previewParticipants, detectedSessions = []) {
        const participants = Array.isArray(previewParticipants) ? previewParticipants : [];
        const fallbackSessions = [...new Set((Array.isArray(detectedSessions) ? detectedSessions : []).map((value) => String(value || '').trim()).filter(Boolean))].sort(compareTimelineSessions);
        const sessions = [...new Set(participants.map((item) => String(item?.session_id || '').trim()).filter(Boolean))].sort(compareTimelineSessions);
        const effectiveSessions = sessions.length > 0 ? sessions : fallbackSessions;
        const runs = [...new Set(participants.map((item) => normalizeVersionSelectionRun(item && item.run_id)).filter(Boolean))].sort((left, right) => compareTimelineContexts({ session: null, run: left }, { session: null, run: right }));
        const maxRun = Math.max(
            0,
            ...Object.values(taskRuns || {}).map((value) => (Number.isInteger(value) && value > 1 ? value : 0))
        );
        const hasSessionContexts = effectiveSessions.length > 1;
        const hasRunContexts = runs.length > 1 || maxRun > 1;

        if (!hasSessionContexts && !hasRunContexts) {
            return [{ session: null, run: null }];
        }

        const observedContexts = [...new Set(
            participants.map((item) => JSON.stringify({
                session: hasSessionContexts ? String(item?.session_id || '').trim() || null : null,
                run: hasRunContexts ? normalizeVersionSelectionRun(item?.run_id) : null
            }))
        )]
            .map((value) => {
                try {
                    return JSON.parse(value);
                } catch (_error) {
                    return null;
                }
            })
            .filter((value) => value && (value.session !== null || value.run !== null));

        if (observedContexts.length > 0) {
            return observedContexts.sort(compareTimelineContexts);
        }

        const runValues = hasRunContexts
            ? (runs.length > 0 ? runs : Array.from({ length: maxRun }, (_, index) => `run-${index + 1}`))
            : [null];
        const sessionValues = hasSessionContexts ? effectiveSessions : [null];
        const fallbackContexts = [];
        sessionValues.forEach((sessionValue) => {
            runValues.forEach((runValue) => {
                fallbackContexts.push({ session: sessionValue, run: runValue });
            });
        });
        return fallbackContexts;
    }

    function getCurrentSessionLabel() {
        const currentSession = getSurveySessionValue();
        if (!currentSession) return 'current session';
        return currentSession === 'all' ? 'all detected sessions' : `session ${currentSession}`;
    }

    function buildVariantDefinitionBadges(variantDefinitions, selectedVersion) {
        if (!Array.isArray(variantDefinitions) || variantDefinitions.length === 0) {
            return '';
        }

        return variantDefinitions
            .map((entry) => {
                if (!entry || typeof entry !== 'object') return '';
                const variantId = String(entry.VariantID || '').trim();
                if (!variantId) return '';
                const itemCount = entry.ItemCount ? `, ${entry.ItemCount} items` : '';
                const scaleType = entry.ScaleType ? `, ${entry.ScaleType}` : '';
                const badgeClass = variantId === selectedVersion ? 'text-bg-primary' : 'text-bg-light';
                return `<span class="badge ${badgeClass}">${variantId}${itemCount}${scaleType}</span>`;
            })
            .filter(Boolean)
            .join(' ');
    }

    function formatVersionWizardSessionLabel(session, fallbackLabel) {
        const rawValue = String(session || fallbackLabel || '').trim();
        if (!rawValue) return 'Session current';
        if (rawValue.toLowerCase() === 'all detected sessions') return rawValue;
        const normalizedValue = rawValue.replace(/^ses-/i, '').replace(/[-_]+/g, ' ').trim();
        if (!normalizedValue) return 'Session current';
        return `Session ${normalizedValue}`;
    }

    function formatVersionWizardRunLabel(run) {
        const normalizedRun = normalizeVersionSelectionRun(run);
        if (!normalizedRun) return 'Single run';
        const token = normalizedRun.replace(/^run-/i, '');
        return /^\d+$/.test(token) ? `Run ${token.padStart(2, '0')}` : `Run ${token}`;
    }

    function buildVersionWizard(multivariantTasks, taskRuns = {}, previewParticipants = [], detectedSessions = []) {
        if (!surveyVersionWizard || !surveyVersionWizardBody) return;

        versionWizardState = { multivariantTasks, taskRuns, previewParticipants, detectedSessions };

        const entries = Object.entries(multivariantTasks || {}).filter(([, info]) => Array.isArray(info?.versions) && info.versions.length > 1);
        if (entries.length === 0) {
            hideVersionWizard();
            return;
        }

        const detectedContexts = deriveDetectedContexts(taskRuns, previewParticipants, detectedSessions);
        const sessionLabel = getCurrentSessionLabel();
        const nextSelections = {};
        let timelineStep = 0;
        surveyVersionWizardBody.innerHTML = '';

        entries.sort(([a], [b]) => a.localeCompare(b)).forEach(([task, info]) => {
            const versions = info.versions.map((value) => String(value).trim()).filter(Boolean);
            if (versions.length <= 1) return;

            const contexts = (detectedContexts.length > 0 ? detectedContexts : [{ session: null, run: null }]).slice().sort(compareTimelineContexts);
            const group = document.createElement('div');
            group.className = 'col-12';
            group.innerHTML = `
                <div class="survey-version-group survey-version-group-compact">
                    <div class="survey-version-group-header">
                        <div>
                            <div class="survey-version-group-label">Questionnaire</div>
                            <div class="survey-version-group-title">${task}</div>
                        </div>
                        <div class="survey-version-group-meta">
                            <span class="badge text-bg-light">${contexts.length} context${contexts.length === 1 ? '' : 's'}</span>
                            <span class="badge text-bg-secondary">${versions.length} versions</span>
                        </div>
                    </div>
                    <div class="survey-version-list"></div>
                </div>
            `;
            const groupList = group.querySelector('.survey-version-list');
            if (!groupList) return;

            contexts.forEach((context) => {
                timelineStep += 1;
                const selectionKey = buildVersionSelectionKey({ task, session: context.session, run: context.run });
                const existingSelection = selectedTemplateVersions[selectionKey];
                const requestedSelection = String(info.selected_version || info.default_version || versions[0]).trim() || versions[0];
                const preferredSelection = existingSelection && versions.includes(existingSelection)
                    ? existingSelection
                    : (versions.includes(requestedSelection) ? requestedSelection : versions[0]);
                nextSelections[selectionKey] = preferredSelection;

                const contextSessionLabel = formatVersionWizardSessionLabel(context.session, sessionLabel);
                const runLabel = formatVersionWizardRunLabel(context.run);
                const selectorId = `surveyVersionSelect-${task}-${String(context.session || 'base').replace(/[^a-zA-Z0-9_-]/g, '_')}-${String(context.run || 'base').replace(/[^a-zA-Z0-9_-]/g, '_')}`;
                const row = document.createElement('div');
                row.className = 'survey-version-row';
                row.innerHTML = `
                    <div class="row g-2 align-items-center">
                        <div class="col-12 col-lg-6">
                            <div class="small text-uppercase text-muted fw-semibold mb-1">Step ${timelineStep}</div>
                            <div class="survey-version-context-line" aria-label="${contextSessionLabel}, ${runLabel}">
                                <span class="survey-version-context-chip survey-version-context-chip-session">${contextSessionLabel}</span>
                                <span class="survey-version-context-chip survey-version-context-chip-run">${runLabel}</span>
                            </div>
                        </div>
                        <div class="col-12 col-lg-6">
                            <label class="form-label small mb-1" for="${selectorId}">Version</label>
                            <select class="form-select form-select-sm survey-version-select" id="${selectorId}" data-task="${task}" data-session="${context.session || ''}" data-run="${context.run === null ? '' : context.run}">
                                ${versions.map((version) => `<option value="${version}"${version === preferredSelection ? ' selected' : ''}>${version}</option>`).join('')}
                            </select>
                            <div class="small text-muted mt-2">${buildVariantDefinitionBadges(info.variant_definitions, preferredSelection)}</div>
                        </div>
                    </div>
                `;
                groupList.appendChild(row);
            });

            surveyVersionWizardBody.appendChild(group);
        });

        selectedTemplateVersions = nextSelections;
        if (surveyVersionWizardCount) {
            surveyVersionWizardCount.textContent = `${Object.keys(selectedTemplateVersions).length} selector(s)`;
        }
        surveyVersionWizardBody.querySelectorAll('.survey-version-select').forEach((selectEl) => {
            selectEl.addEventListener('change', () => {
                const task = String(selectEl.dataset.task || '').trim().toLowerCase();
                const sessionValue = String(selectEl.dataset.session || '').trim();
                const rawRun = String(selectEl.dataset.run || '').trim();
                if (!task) return;
                const selectionKey = buildVersionSelectionKey({ task, session: sessionValue || null, run: rawRun || null });
                selectedTemplateVersions[selectionKey] = selectEl.value;
                updateVersionWizardActionState();
                updateConvertBtn();
            });
        });
        surveyVersionWizard.classList.remove('d-none');
        updateVersionWizardActionState();
        updateConvertBtn();
    }

    function rebuildVersionWizardFromState() {
        if (!versionWizardState || !versionWizardState.multivariantTasks || Object.keys(versionWizardState.multivariantTasks).length === 0) {
            return;
        }
        buildVersionWizard(
            versionWizardState.multivariantTasks,
            versionWizardState.taskRuns,
            versionWizardState.previewParticipants,
            versionWizardState.detectedSessions
        );
    }

    function appendTemplateVersionSelections(formData) {
        const selections = getTemplateVersionSelections();
        if (selections.length > 0) {
            formData.append('template_versions', JSON.stringify(selections));
        }
        return selections;
    }

    function buildSurveyWorkflowRequestFormData({
        allowNearItemMatch = false,
        nearMatchTasks = null,
        taskValueOffsets = null,
        includeValidation = false,
        includeIdMap = true,
    } = {}) {
        const formData = new FormData();
        const inputSelection = appendSurveyInputToFormData(formData);
        const filename = inputSelection.filename || getSelectedSurveyFilename();
        if (!inputSelection.filename) {
            return {
                formData,
                inputSelection,
                filename: '',
                templateSelections: [],
                selectedNearMatchTasks: [],
                normalizedOffsets: {},
            };
        }

        const idMap = isAdvancedOptionsEnabled() && convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
        if (includeIdMap && idMap) {
            formData.append('id_map', idMap);
        }

        const idValue = String(document.getElementById('convertIdColumn')?.value || '').trim();
        if (idValue && idValue !== 'auto') {
            formData.append('id_column', idValue);
        }

        const sessionVal = getSurveySessionValue();
        if (sessionVal) {
            formData.append('session', sessionVal);
        }

        const sessionColVal = (convertSessionColumnOverride && convertSessionColumnOverride.value.trim()) || '';
        const runColVal = (convertRunColumnOverride && convertRunColumnOverride.value.trim()) || '';
        if (sessionColVal) {
            formData.append('session_column', sessionColVal);
        }
        if (runColVal) {
            formData.append('run_column', runColVal);
        }

        if (isAdvancedOptionsEnabled() && convertDatasetName && convertDatasetName.value.trim()) {
            formData.append('survey', convertDatasetName.value.trim());
        }
        formData.append('language', (isAdvancedOptionsEnabled() && convertLanguage) ? convertLanguage.value : 'auto');
        formData.append('separator', getSelectedSeparator(filename.toLowerCase()));

        const templateSelections = getTemplateVersionSelections();
        if (templateSelections.length > 0) {
            formData.append('template_versions', JSON.stringify(templateSelections));
        }

        const selectedNearMatchTasks = Array.isArray(nearMatchTasks)
            ? [...new Set(
                nearMatchTasks
                    .map((task) => normalizeNearMatchTaskName(task))
                    .filter(Boolean)
            )]
            : [];
        if (allowNearItemMatch) {
            formData.append('allow_near_item_match', 'true');
            if (selectedNearMatchTasks.length > 0) {
                formData.append('near_match_tasks', JSON.stringify(selectedNearMatchTasks));
            }
        }

        const normalizedOffsets = normalizeTaskValueOffsets(taskValueOffsets);
        if (Object.keys(normalizedOffsets).length > 0) {
            formData.append('value_offsets', JSON.stringify(normalizedOffsets));
        }

        if (!includeValidation) {
            formData.append('validate', 'false');
        }

        return {
            formData,
            inputSelection,
            filename,
            templateSelections,
            selectedNearMatchTasks,
            normalizedOffsets,
        };
    }

    function cancelVersionWizardSync() {
        versionWizardSyncRequestId += 1;
        if (versionWizardSyncTimer) {
            clearTimeout(versionWizardSyncTimer);
            versionWizardSyncTimer = null;
        }
    }

    function shouldSyncVersionWizardContext() {
        const filename = getSelectedSurveyFilename();
        if (!filename || filename.toLowerCase().endsWith('.lss')) {
            return false;
        }
        const idValue = String(document.getElementById('convertIdColumn')?.value || '').trim();
        return Boolean(idValue && idValue !== 'auto');
    }

    async function syncVersionWizardContext({
        showErrors = false,
        allowNearItemMatch = false,
        nearMatchTasks = null,
        taskValueOffsets = null,
    } = {}) {
        if (!shouldSyncVersionWizardContext()) {
            hideVersionWizard();
            return { hasMultivariant: false, skipped: true };
        }

        const requestId = ++versionWizardSyncRequestId;
        const workflowRequest = buildSurveyWorkflowRequestFormData({
            allowNearItemMatch,
            nearMatchTasks,
            taskValueOffsets,
            includeValidation: false,
            includeIdMap: false,
        });
        if (!workflowRequest.filename) {
            hideVersionWizard();
            return { hasMultivariant: false, skipped: true };
        }

        try {
            const response = await fetch('/api/survey-detect-version-contexts', {
                method: 'POST',
                body: workflowRequest.formData,
            });
            const data = await parseJsonResponse(response, 'Version context sync');
            if (requestId !== versionWizardSyncRequestId) {
                return;
            }
            if (!response.ok) {
                hideVersionWizard();
                if (showErrors && data?.error && data.error !== 'id_column_required') {
                    convertError.textContent = data.error;
                    convertError.classList.remove('d-none');
                }
                return { hasMultivariant: false, error: true };
            }

            const mvTasks = (data && typeof data.multivariant_tasks === 'object' && data.multivariant_tasks)
                ? data.multivariant_tasks
                : {};
            const hasMultivariant = Object.keys(mvTasks).length > 0;
            if (Object.keys(mvTasks).length > 0) {
                buildVersionWizard(
                    mvTasks,
                    (data && typeof data.task_runs === 'object' && data.task_runs) || {},
                    Array.isArray(data?.preview_participants) ? data.preview_participants : [],
                    Array.isArray(data.detected_sessions) ? data.detected_sessions : []
                );
            } else {
                hideVersionWizard();
            }
            return { hasMultivariant };
        } catch (error) {
            if (requestId !== versionWizardSyncRequestId) {
                return { hasMultivariant: false, skipped: true };
            }
            hideVersionWizard();
            if (showErrors) {
                convertError.textContent = error.message;
                convertError.classList.remove('d-none');
            }
            return { hasMultivariant: false, error: true };
        }
    }

    function scheduleVersionWizardContextSync(options = {}) {
        cancelVersionWizardSync();
        versionWizardSyncTimer = setTimeout(() => {
            versionWizardSyncTimer = null;
            syncVersionWizardContext(options);
        }, 150);
    }

    function setTemplateEditorErrorCtaVisible(visible) {
        if (!templateEditorErrorCta) return;
        templateEditorErrorCta.classList.toggle('d-none', !visible);
    }

    function isAdvancedOptionsEnabled() {
        return Boolean(convertAdvancedToggle && convertAdvancedToggle.checked);
    }

    const surveyValueOffsetEditorController = createSurveyValueOffsetEditorController({
        convertAdvancedToggle,
        convertDatasetName,
        convertLanguage,
        convertIdMapFile,
        clearIdMapFileBtn,
        convertValueOffsets,
        convertValueOffsetsEditor,
        convertValueOffsetRows,
        convertAddValueOffsetRowBtn,
        convertApplyValueOffsetsBtn,
        convertValueOffsetsKnownTasks,
        convertValueOffsetsEmptyState,
        convertValueOffsetsStatus,
        convertValueOffsetAdvice,
        convertError,
        convertInfo,
        isAdvancedOptionsEnabled,
        getTemplateWorkflowGate: () => templateWorkflowGate,
        getIsConvertRunning: () => isConvertRunning,
        getIsPreviewRunning: () => isPreviewRunning,
        getAppliedTaskValueOffsetSelectionSignature: () => appliedTaskValueOffsetSelectionSignature,
        setAppliedTaskValueOffsetSelectionSignature: (value) => {
            appliedTaskValueOffsetSelectionSignature = value;
        },
        updateConvertBtn,
        getNextTaskValueOffsetRowId: () => ++taskValueOffsetRowSequence,
        getSurveyPreviewSelectionState: () => surveyPreviewSelectionState,
        getTemplateVersionSelections,
        getLastPreviewSurveyTasks: () => {
            return Array.isArray(window.lastPreviewData && window.lastPreviewData.survey_tasks)
                ? window.lastPreviewData.survey_tasks
                : [];
        },
        getTaskValueOffsetEditorState: () => taskValueOffsetEditorState,
        setTaskValueOffsetEditorState: (nextState) => {
            taskValueOffsetEditorState = Array.isArray(nextState) ? nextState : [];
        },
        normalizeSurveyTaskName,
        parseTaskValueOffsetsText,
        normalizeTaskValueOffsets,
        parseNumericOffsetValue,
        formatOffsetMagnitude,
        formatSignedOffset,
        escapeHtml,
    });

    function applyAdvancedOptionsState() {
        surveyValueOffsetEditorController.applyAdvancedOptionsState();
    }

    if (convertDatasetName) {
        convertDatasetName.addEventListener('input', () => {
            updateConvertBtn();
        });
    }

    if (convertLanguage) {
        convertLanguage.addEventListener('change', () => {
            updateConvertBtn();
        });
    }

    surveyValueOffsetEditorController.initialize();

    // ID Map file handlers
    if (convertIdMapFile) {
        const updateIdMapClearButtonState = () => {
            const hasFile = Boolean(convertIdMapFile.files && convertIdMapFile.files[0]);
            clearIdMapFileBtn?.classList.toggle('d-none', !hasFile);
        };

        convertIdMapFile.addEventListener('change', () => {
            const f = convertIdMapFile.files && convertIdMapFile.files[0];
            if (f) {
                console.log(`ID map file selected: ${f.name} (${f.size} bytes)`);
            }
            updateIdMapClearButtonState();
            updateConvertBtn();
        });

        clearIdMapFileBtn?.addEventListener('click', () => {
            convertIdMapFile.value = '';
            updateIdMapClearButtonState();
           convertError?.classList.add('d-none');
            convertError.textContent = '';
        });

        updateIdMapClearButtonState();
    }

    // Library path browser
    if (convertBrowseLibraryBtn && convertLibraryPathInput) {
        convertBrowseLibraryBtn.addEventListener('click', function() {
            if (prefersServerPicker() && window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFolder === 'function') {
                window.PrismFileSystemMode.pickFolder({
                    title: 'Select Template Library Root',
                    confirmLabel: 'Use This Folder',
                    startPath: convertLibraryPathInput.value || ''
                }).then((pickedPath) => {
                    if (!pickedPath) return;
                    convertLibraryPathInput.value = pickedPath;
                    refreshConvertLanguages();
                });
                return;
            }

            fetch('/api/browse-folder')
                .then(r => r.json())
                .then(data => {
                    if (data.path) {
                        convertLibraryPathInput.value = data.path;
                        refreshConvertLanguages();
                    } else if (data.error) {
                        alert('Folder picker unavailable: ' + data.error);
                    }
                })
                .catch(err => {
                    console.error('Browse error:', err);
                    alert('Failed to open folder picker. Please enter path manually.');
                });
        });
    }

    function refreshConvertLanguages() {
        const libraryPath = convertLibraryPathInput ? convertLibraryPathInput.value.trim() : '';
        const surveyI18nWarning = document.getElementById('surveyI18nWarning');
        const surveyI18nMessage = document.getElementById('surveyI18nMessage');
        const surveyStructureWarning = document.getElementById('surveyStructureWarning');
        const surveyStructureMessage = document.getElementById('surveyStructureMessage');
        
        if (!libraryPath) {
            if (surveyI18nWarning) surveyI18nWarning.classList.add('d-none');
            if (surveyStructureWarning) surveyStructureWarning.classList.add('d-none');
            return;
        }
        
        const url = `/api/survey-languages?library_path=${encodeURIComponent(libraryPath)}`;
        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (!convertLanguage) return;
                const current = convertLanguage.value || 'auto';

                convertLanguage.innerHTML = '';
                const autoOpt = document.createElement('option');
                autoOpt.value = 'auto';
                autoOpt.textContent = 'Auto (template default)';
                convertLanguage.appendChild(autoOpt);

                const langs = (data && data.languages) ? data.languages : [];
                langs.forEach(lang => {
                    const opt = document.createElement('option');
                    opt.value = lang;
                    opt.textContent = lang;
                    convertLanguage.appendChild(opt);
                });

                const preferred = (data && data.default) ? data.default : null;
                if (preferred && langs.includes(preferred)) {
                    convertLanguage.value = preferred;
                } else if (langs.includes(current)) {
                    convertLanguage.value = current;
                } else {
                    convertLanguage.value = 'auto';
                }

                if (surveyStructureWarning && surveyStructureMessage && data.structure) {
                    const missing = data.structure.missing_items || [];
                    if (missing.length > 0) {
                        surveyStructureMessage.textContent = `The selected folder is missing: ${missing.join(', ')}. Expected library structure: survey/, biometrics/, participants.json`;
                        surveyStructureWarning.classList.remove('d-none');
                    } else {
                        surveyStructureWarning.classList.add('d-none');
                    }
                } else if (surveyStructureWarning) {
                    surveyStructureWarning.classList.add('d-none');
                }

                if (surveyI18nWarning && surveyI18nMessage) {
                    const hasI18n = langs.length > 0;
                    const templateCount = data.template_count || 0;
                    const i18nCount = data.i18n_count || 0;
                    
                    if (!hasI18n || (templateCount > 0 && i18nCount < templateCount)) {
                        const missing = templateCount - i18nCount;
                        if (!hasI18n) {
                            surveyI18nMessage.textContent = 'No templates with multilanguage (I18n) configuration found. Consider adding I18n block with Languages array to your templates.';
                        } else if (missing > 0) {
                            surveyI18nMessage.textContent = `${missing} of ${templateCount} templates lack multilanguage (I18n) configuration. Available languages: ${langs.join(', ')}`;
                        }
                        surveyI18nWarning.classList.remove('d-none');
                    } else {
                        surveyI18nWarning.classList.add('d-none');
                    }
                }
            })
            .catch(() => {
                if (surveyI18nWarning) surveyI18nWarning.classList.add('d-none');
                if (surveyStructureWarning) surveyStructureWarning.classList.add('d-none');
            });
    }

    if (convertLibraryPathInput) {
        convertLibraryPathInput.addEventListener('change', function() {
            refreshConvertLanguages();
            updateConvertBtn();
        });
        convertLibraryPathInput.addEventListener('blur', function() {
            refreshConvertLanguages();
            updateConvertBtn();
        });
    }

    // Session picker functions
    function populateSurveySessionPickerFromDetected(detectedSessions) {
        if (!convertSessionSelect || !Array.isArray(detectedSessions) || detectedSessions.length === 0) {
            return false;
        }

        const normalizedSessions = [...new Set(
            detectedSessions
                .map((value) => String(value || '').trim())
                .filter(Boolean)
        )];
        if (normalizedSessions.length === 0) {
            return false;
        }

        while (convertSessionSelect.options.length > 1) {
            convertSessionSelect.remove(1);
        }

        const allOpt = document.createElement('option');
        allOpt.value = 'all';
        allOpt.textContent = '✓ All sessions';
        convertSessionSelect.appendChild(allOpt);

        normalizedSessions.forEach((ses) => {
            const opt = document.createElement('option');
            opt.value = ses;
            opt.textContent = ses;
            convertSessionSelect.appendChild(opt);
        });

        if (!getSurveySessionValue()) {
            convertSessionSelect.value = normalizedSessions.length === 1 ? normalizedSessions[0] : 'all';
        }
        if (convertSessionCustom) {
            convertSessionCustom.value = '';
        }

        return true;
    }

    function getSessionValue(selectEl, customEl) {
        const selVal = selectEl ? selectEl.value.trim() : '';
        const custVal = customEl ? customEl.value.trim() : '';
        return selVal || custVal;
    }

    function getSurveySessionValue() {
        return getSessionValue(convertSessionSelect, convertSessionCustom);
    }

    function getBiometricsSessionValue() {
        return getSessionValue(biometricsSessionSelect, biometricsSessionCustom);
    }

    function getProjectSaveSummary(data) {
        const outputPaths = Array.isArray(data && data.project_output_paths)
            ? data.project_output_paths.filter((value) => typeof value === 'string' && value.trim())
            : [];
        const target = (data && (data.project_output_path || outputPaths[0] || data.project_output_root)) || 'the active project';
        const outputCount = Number.isFinite(data && data.project_output_count)
            ? data.project_output_count
            : outputPaths.length;
        const countNote = outputCount > 1 ? ` (${outputCount} files)` : '';

        return { target, countNote };
    }

    function openConverterTab(target) {
        const normalizedTarget = String(target || '').trim().toLowerCase();
        if (!normalizedTarget) {
            return false;
        }

        const tabButton = document.getElementById(`${normalizedTarget}-tab`);
        if (!tabButton) {
            return false;
        }

        if (window.bootstrap && window.bootstrap.Tab && typeof window.bootstrap.Tab.getOrCreateInstance === 'function') {
            window.bootstrap.Tab.getOrCreateInstance(tabButton).show();
        } else {
            tabButton.click();
        }

        if (typeof tabButton.focus === 'function') {
            tabButton.focus();
        }
        return true;
    }

    function showConvertInfoMessage(message, options = {}) {
        if (!convertInfo) {
            return;
        }

        const {
            variant = 'info',
            iconClass = 'fas fa-info-circle',
            action = null,
        } = options;

        convertInfo.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
        convertInfo.classList.add('alert', `alert-${variant}`);
        convertInfo.innerHTML = '';

        const wrapper = document.createElement('div');
        if (action && action.type === 'open_converter_tab') {
            wrapper.className = 'd-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2';
        }

        const messageContainer = document.createElement('div');
        const icon = document.createElement('i');
        icon.className = `${iconClass} me-2`;
        messageContainer.appendChild(icon);

        const messageText = document.createElement('span');
        messageText.textContent = String(message || '');
        messageContainer.appendChild(messageText);
        wrapper.appendChild(messageContainer);

        if (action && action.type === 'open_converter_tab') {
            const actionButton = document.createElement('button');
            actionButton.type = 'button';
            actionButton.className = 'btn btn-sm btn-outline-dark align-self-start align-self-md-center';

            const buttonIcon = document.createElement('i');
            buttonIcon.className = 'fas fa-users me-1';
            actionButton.appendChild(buttonIcon);
            actionButton.appendChild(document.createTextNode(String(action.label || 'Open')));
            actionButton.addEventListener('click', () => {
                if (!openConverterTab(action.target)) {
                    appendLog('Could not open the requested converter tab.', 'warning');
                }
            });
            wrapper.appendChild(actionButton);
        }

        convertInfo.appendChild(wrapper);
        convertInfo.classList.remove('d-none');
    }

    function getParticipantRegistryWarning(payload) {
        if (payload && typeof payload.participant_registry_warning === 'object' && payload.participant_registry_warning) {
            return payload.participant_registry_warning;
        }

        if (payload && payload.conversion_summary && typeof payload.conversion_summary.participant_registry_warning === 'object') {
            return payload.conversion_summary.participant_registry_warning;
        }

        if (payload && payload.preview && typeof payload.preview.participant_registry_warning === 'object') {
            return payload.preview.participant_registry_warning;
        }

        const previewIssues = payload && payload.preview && Array.isArray(payload.preview.data_issues)
            ? payload.preview.data_issues
            : [];
        return previewIssues.find((issue) => issue && issue.type === 'missing_from_participants_tsv') || null;
    }

    function showParticipantRegistryWarning(messagePrefix, warning) {
        if (!warning) {
            return;
        }

        const parts = [messagePrefix, warning.message, warning.details].filter((value) => typeof value === 'string' && value.trim());
        showConvertInfoMessage(parts.join(' '), {
            variant: 'warning',
            iconClass: 'fas fa-exclamation-triangle',
            action: warning.action || null,
        });
    }

    function isDelimitedSurveyFilename(filename) {
        return filename.endsWith('.csv') || filename.endsWith('.tsv');
    }

    function getSelectedSeparator(filename = '') {
        if (!isDelimitedSurveyFilename(filename)) {
            return 'auto';
        }
        if (!convertSeparator) {
            return 'auto';
        }
        return (convertSeparator.value || 'auto').toLowerCase();
    }

    function updateSeparatorVisibility(filename = '') {
        if (!surveySeparatorGroup) return;
        surveySeparatorGroup.classList.toggle('d-none', !isDelimitedSurveyFilename(filename));
    }

    if (convertSessionSelect) {
        convertSessionSelect.addEventListener('change', function() {
            if (this.value && convertSessionCustom) convertSessionCustom.value = '';
            rebuildVersionWizardFromState();
            scheduleVersionWizardContextSync();
            updateConvertBtn();
        });
    }
    if (convertSessionCustom) {
        convertSessionCustom.addEventListener('input', function() {
            if (this.value && convertSessionSelect) convertSessionSelect.value = '';
            rebuildVersionWizardFromState();
            scheduleVersionWizardContextSync();
            updateConvertBtn();
        });
    }
    if (biometricsSessionSelect) {
        biometricsSessionSelect.addEventListener('change', function() {
            if (this.value && biometricsSessionCustom) biometricsSessionCustom.value = '';
        });
    }
    if (biometricsSessionCustom) {
        biometricsSessionCustom.addEventListener('input', function() {
            if (this.value && biometricsSessionSelect) biometricsSessionSelect.value = '';
        });
    }

    const registerSessionInProject = createSessionRegistrar(populateSessionPickers);

    // Mode handling
    function getConvertMode() {
        return 'data';
    }

    function handleModeSwitch() {
        convertIdColumnGroup?.classList.remove('d-none');
        convertTemplateExportGroup?.classList.add('d-none');
        convertLanguageGroup?.classList.remove('d-none');
        convertAliasGroup?.classList.remove('d-none');
        convertSessionGroup?.classList.remove('d-none');

        const libPathLabel = convertLibraryPathInput?.closest('.col-12')?.querySelector('.form-label');
        if (libPathLabel) {
            libPathLabel.innerHTML = 'Template Library Root <span class="text-danger">*</span>';
        }

        updateConvertBtn();
    }

    // Column detection
    function resetDetectedColumnsState() {
        const idColumnSelect = document.getElementById('convertIdColumn');
        const idColumnStatus = document.getElementById('idColumnStatus');
        const idColumnHelp = document.getElementById('idColumnHelp');
        if (!idColumnSelect) return;

        window._isPrismData = false;
        idColumnSelect.innerHTML = '<option value="auto" selected>Auto-detect (PRISM surveys only)</option>';
        idColumnSelect.classList.remove('border-danger');
        if (idColumnStatus) idColumnStatus.innerHTML = '';
        if (idColumnHelp) idColumnHelp.innerHTML = '<i class="fas fa-info-circle me-1"></i>Upload a file to detect available columns';

        if (convertSessionColumnOverride) {
            convertSessionColumnOverride.innerHTML = '<option value="">Auto-detect</option>';
        }
        if (convertRunColumnOverride) {
            convertRunColumnOverride.innerHTML = '<option value="">Auto-detect</option>';
        }
        ['convertSessionColumnHint', 'convertRunColumnHint'].forEach(id => {
            const el = document.getElementById(id);
            if (el) { el.textContent = ''; el.classList.add('d-none'); }
        });
    }

    async function detectFileColumns(file, sourceFilePath = '') {
        const filename = file && file.name
            ? file.name.toLowerCase()
            : String(sourceFilePath || '').toLowerCase();
        const idColumnSelect = document.getElementById('convertIdColumn');
        const idColumnStatus = document.getElementById('idColumnStatus');
        const idColumnHelp = document.getElementById('idColumnHelp');
        if (!idColumnSelect) return;

        const previousIdSelection = String(idColumnSelect.value || '').trim();
        const hadManualIdSelection = previousIdSelection !== '' && previousIdSelection !== 'auto';

        resetDetectedColumnsState();

        if (filename.endsWith('.lss')) {
            if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-muted">(structure only)</span>';
            if (idColumnHelp) idColumnHelp.innerHTML = '<i class="fas fa-info-circle me-1"></i>.lss files have no response data';
            lastDetectedSurveyFingerprint = getSelectedSurveyFingerprint();
            return;
        }

        if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-info"><i class="fas fa-spinner fa-spin me-1"></i>Loading...</span>';

        if (filename.endsWith('.lsa') || filename.endsWith('.xlsx') || filename.endsWith('.csv') || filename.endsWith('.tsv')) {
            try {
                const formData = new FormData();
                if (file) {
                    formData.append('file', file);
                } else if (sourceFilePath) {
                    formData.append('source_file_path', sourceFilePath);
                }
                formData.append('separator', getSelectedSeparator(filename));

                const response = await fetch('/api/detect-columns', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    window._isPrismData = !!data.is_prism_data;

                    const sessionsLoaded = populateSurveySessionPickerFromDetected(data.detected_sessions);
                    if (!sessionsLoaded) {
                        populateSessionPickers();
                    }

                    if (data.columns && data.columns.length > 0) {
                        data.columns.forEach(col => {
                            const opt = document.createElement('option');
                            opt.value = col;
                            opt.textContent = col;
                            if (data.suggested_id_column && col === data.suggested_id_column) {
                                opt.textContent += ' \u2605';
                            }
                            idColumnSelect.appendChild(opt);
                        });

                        // Populate session/run column selects with same columns
                        const _colOverrideMap = [
                            { sel: convertSessionColumnOverride, detected: data.session_column, hintId: 'convertSessionColumnHint' },
                            { sel: convertRunColumnOverride,     detected: data.run_column,     hintId: 'convertRunColumnHint'     },
                        ];
                        _colOverrideMap.forEach(({ sel, detected, hintId }) => {
                            if (!sel) return;
                            const current = sel.value;
                            sel.innerHTML = '<option value="">Auto-detect</option>';
                            data.columns.forEach(col => {
                                const opt = document.createElement('option');
                                opt.value = col;
                                opt.textContent = col;
                                sel.appendChild(opt);
                            });
                            // Restore prior manual selection; otherwise pre-select auto-detected column.
                            if (current && data.columns.includes(current)) {
                                sel.value = current;
                            } else if (detected && data.columns.includes(detected)) {
                                sel.value = detected;
                            }
                            // Show/clear hint
                            const hintEl = document.getElementById(hintId);
                            if (hintEl) {
                                if (detected) {
                                    hintEl.textContent = `\u2713 Auto-detected: ${detected}`;
                                    hintEl.className = 'text-success small';
                                    hintEl.classList.remove('d-none');
                                } else {
                                    hintEl.textContent = '';
                                    hintEl.classList.add('d-none');
                                }
                            }
                        });

                        if (data.is_prism_data && data.suggested_id_column) {
                            idColumnSelect.value = data.suggested_id_column;
                            if (idColumnStatus) {
                                idColumnStatus.textContent = `PRISM data (${data.columns.length} columns)`;
                                idColumnStatus.className = 'text-success';
                            }
                            if (idColumnHelp) {
                                idColumnHelp.replaceChildren();
                                const icon = document.createElement('i');
                                icon.className = 'fas fa-check-circle me-1 text-success';
                                idColumnHelp.appendChild(icon);
                                idColumnHelp.appendChild(document.createTextNode('PRISM ID column detected: '));
                                const strong = document.createElement('strong');
                                strong.textContent = data.suggested_id_column;
                                idColumnHelp.appendChild(strong);
                            }
                        } else if (!data.is_prism_data) {
                            idColumnSelect.querySelector('option[value="auto"]').textContent = '-- Select ID column --';
                            idColumnSelect.value = 'auto';
                            if (idColumnStatus) {
                                idColumnStatus.textContent = `${data.columns.length} columns`;
                                idColumnStatus.className = 'text-warning';
                            }
                            if (idColumnHelp) {
                                idColumnHelp.innerHTML = '<i class="fas fa-exclamation-triangle me-1 text-warning"></i>No PRISM ID column found. Please select the participant ID column manually.';
                            }
                        } else {
                            if (idColumnStatus) {
                                idColumnStatus.textContent = `${data.columns.length} columns`;
                                idColumnStatus.className = 'text-success';
                            }
                            if (idColumnHelp) {
                                idColumnHelp.replaceChildren();
                                if (data.suggested_id_column) {
                                    const icon = document.createElement('i');
                                    icon.className = 'fas fa-lightbulb me-1 text-warning';
                                    idColumnHelp.appendChild(icon);
                                    idColumnHelp.appendChild(document.createTextNode('Suggested: '));
                                    const strong = document.createElement('strong');
                                    strong.textContent = data.suggested_id_column;
                                    idColumnHelp.appendChild(strong);
                                } else {
                                    const icon = document.createElement('i');
                                    icon.className = 'fas fa-exclamation-triangle me-1 text-warning';
                                    idColumnHelp.appendChild(icon);
                                    idColumnHelp.appendChild(document.createTextNode('No common ID column found. Please select manually.'));
                                }
                            }
                            if (data.suggested_id_column) {
                                idColumnSelect.value = data.suggested_id_column;
                            }
                        }

                        if (hadManualIdSelection && data.columns.includes(previousIdSelection)) {
                            idColumnSelect.value = previousIdSelection;
                        }
                    } else {
                        if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-warning">No columns found</span>';
                    }

                    lastDetectedSurveyFingerprint = getSelectedSurveyFingerprint();
                    scheduleVersionWizardContextSync();
                } else {
                    try {
                        const err = await response.json();
                        console.error('Server returned error:', response.status, err);
                        if (idColumnStatus) {
                            idColumnStatus.textContent = err.error || 'Error';
                            idColumnStatus.className = 'text-danger';
                        }
                    } catch (jsonError) {
                        console.error('Failed to parse error response:', response.status, jsonError);
                        if (idColumnStatus) idColumnStatus.innerHTML = `<span class="text-danger">Server error (${response.status})</span>`;
                    }
                }
            } catch (e) {
                console.error('Failed to detect columns:', e.message, e.stack);
                if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-danger">Failed to load</span>';
            }
        }
    }

    function updateConvertBtn() {
        const hasFile = hasSelectedSurveyInput();
        const blockedByTemplateGate = Boolean(templateWorkflowGate && templateWorkflowGate.blocked);
        const hasProjectLoaded = resolveCurrentProjectPath() !== '';
        const hasRunningRequest = isConvertRunning || isPreviewRunning;
        const isAwaitingConfirmation = hasRunningRequest && surveyWorkflowProgressController.getIsSurveyRunAwaitingConfirmation();
        const versionSelectionsPending = hasMultiVersionWizardTasks() && !hasAppliedVersionWizardSelections();
        const valueOffsetSelectionsPending = hasManualTaskValueOffsets() && !hasAppliedTaskValueOffsetSelections();
        const hasFreshPreviewReview = hasFreshSurveyPreviewSelectionState();
        const selectedPreviewTasks = getSelectedSurveyTasksForConversion();
        const hasSelectedPreviewTasks = selectedPreviewTasks.length > 0;

        convertBtn.disabled = !hasFile
            || blockedByTemplateGate
            || versionSelectionsPending
            || valueOffsetSelectionsPending
            || !hasFreshPreviewReview
            || !hasSelectedPreviewTasks;
        if (checkProjectTemplatesBtn) {
            checkProjectTemplatesBtn.disabled = !hasProjectLoaded;
            if (!hasProjectLoaded) {
                checkProjectTemplatesBtn.title = 'Load a project first to check local templates.';
            } else {
                checkProjectTemplatesBtn.removeAttribute('title');
            }
        }
        
        if (previewBtn) {
            previewBtn.disabled = !hasFile || versionSelectionsPending || valueOffsetSelectionsPending;
            previewBtn.style.display = '';
            previewBtn.innerHTML = '<i class="fas fa-eye me-2"></i>Step 4: Preview (Dry-Run)';
            convertBtn.parentElement.classList.remove('col-12');
            convertBtn.parentElement.classList.add('col-md-6');

            if (!hasFile) {
                previewBtn.title = 'Select a survey file first.';
            } else if (versionSelectionsPending) {
                previewBtn.title = 'Apply questionnaire version selections first.';
            } else if (valueOffsetSelectionsPending) {
                previewBtn.title = 'Apply manual offsets first.';
            } else {
                previewBtn.removeAttribute('title');
            }
        }

        if (convertBtn) {
            convertBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Step 5: Convert';
            convertBtn.classList.remove('btn-success');
            convertBtn.classList.add('btn-warning');
            if (blockedByTemplateGate) {
                convertBtn.title = 'Complete required project template fields first, then run Preview again.';
            } else if (!hasFile) {
                convertBtn.title = 'Select a survey file first.';
            } else if (versionSelectionsPending) {
                convertBtn.title = 'Apply questionnaire version selections and rerun Preview before converting.';
            } else if (valueOffsetSelectionsPending) {
                convertBtn.title = 'Apply manual offsets and rerun Preview before converting.';
            } else if (!hasFreshPreviewReview) {
                convertBtn.title = 'Run Preview after the latest changes before converting.';
            } else if (!hasSelectedPreviewTasks) {
                convertBtn.title = 'Select at least one survey in the Preview review list.';
            } else {
                convertBtn.removeAttribute('title');
            }
        }

        // Keep a visible in-flight indicator while preview/convert requests are running.
        if (isConvertRunning) {
            convertBtn.disabled = true;
            convertBtn.innerHTML = isAwaitingConfirmation
                ? '<i class="fas fa-pause-circle me-2"></i>Awaiting confirmation...'
                : '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Converting...';
            if (previewBtn) {
                previewBtn.disabled = true;
            }
        }

        if (isPreviewRunning) {
            if (previewBtn) {
                previewBtn.disabled = true;
                previewBtn.innerHTML = isAwaitingConfirmation
                    ? '<i class="fas fa-pause-circle me-2"></i>Awaiting confirmation...'
                    : '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Running...';
            }
            convertBtn.disabled = true;
        }

        if (surveyRunCancelBtn) {
            if (hasRunningRequest) {
                const modeLabel = isConvertRunning ? 'Conversion' : 'Preview';
                surveyRunCancelBtn.classList.remove('d-none');
                surveyRunCancelBtn.disabled = !activeRunAbortController;
                surveyRunCancelBtn.innerHTML = `<i class="fas fa-stop-circle me-2"></i>Cancel ${modeLabel}`;
            } else {
                surveyRunCancelBtn.classList.add('d-none');
                surveyRunCancelBtn.disabled = true;
                surveyRunCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Run';
            }
        }

        updateTaskValueOffsetApplyState();

        updateSurveyWorkflowHint({
            hasFile,
            blockedByTemplateGate,
            versionSelectionsPending,
            valueOffsetSelectionsPending,
            hasFreshPreviewReview,
            hasSelectedPreviewTasks,
            isConvertRunning,
            isPreviewRunning,
        });

        clearConvertExcelFileBtn?.classList.toggle('d-none', !hasFile);
    }

    if (surveyRunCancelBtn) {
        surveyRunCancelBtn.addEventListener('click', function() {
            const mode = activeRunMode || surveyWorkflowProgressController.getRunProgressMode();
            const modeLabel = mode === 'convert' ? 'conversion' : 'preview';
            const canceled = cancelActiveSurveyRun();
            if (!canceled) {
                return;
            }
            appendLog(`Cancel requested: stopping current ${modeLabel} run...`, 'warning');
            setSurveyRunProgress({
                mode: mode || 'preview',
                percent: Math.max(15, surveyWorkflowProgressController.getRunProgressPercent()),
                label: `Canceling ${modeLabel}...`,
                variant: 'warning',
                animated: true,
            });
            surveyRunCancelBtn.disabled = true;
        });
    }

    convertExcelFile.addEventListener('change', async function() {
        convertServerFilePath = '';
        resetSurveyRefreshFingerprint();
        const file = this.files?.[0];
        templateWorkflowGate = null;
        cancelVersionWizardSync();
        hideVersionWizard();
        setTemplateEditorErrorCtaVisible(false);
        updateConvertBtn();

        if (file) {
            const filename = file.name.toLowerCase();
            updateSeparatorVisibility(filename);

            if (filename.endsWith('.lss')) {
                convertInfo.innerHTML = '<i class="fas fa-info-circle me-1"></i>.lss files contain structure only (no response data). Use <a href="/template-editor" class="alert-link">Template Editor</a> to generate templates.';
                convertInfo.classList.remove('d-none');
            } else {
                convertInfo.classList.add('d-none');
            }

            await detectFileColumns(file);
        } else {
            convertInfo.classList.add('d-none');
            resetDetectedColumnsState();
            populateSessionPickers();
            updateSeparatorVisibility('');
        }
        updateConvertBtn();
    });

    function resetSurveyImportFormState() {
        templateWorkflowGate = null;
        cancelVersionWizardSync();
        setTemplateEditorErrorCtaVisible(false);
        resetConversionUI();
        resetSurveyRefreshFingerprint();

        currentTemplateData = null;
        window.lastPreviewData = null;
        window.lastParticipantsPreviewData = null;

        // Reset separator to default for next import.
        if (convertSeparator) {
            const hasAuto = Array.from(convertSeparator.options || []).some(o => o.value === 'auto');
            if (hasAuto) {
                convertSeparator.value = 'auto';
            } else if (convertSeparator.options.length > 0) {
                convertSeparator.selectedIndex = 0;
            }
        }

        // Reset detected columns / ID mapping state.
        resetDetectedColumnsState();
        if (convertIdMapFile) convertIdMapFile.value = '';
        clearIdMapFileBtn?.classList.add('d-none');

        // Reset session selections so user starts fresh.
        if (convertSessionSelect) {
            if (convertSessionSelect.options.length > 0) {
                convertSessionSelect.selectedIndex = 0;
            } else {
                convertSessionSelect.value = '';
            }
        }
        if (convertSessionCustom) convertSessionCustom.value = '';

        // Reset optional inputs to their initial state.
        if (convertAdvancedToggle) {
            convertAdvancedToggle.checked = false;
        }
        applyAdvancedOptionsState();

        surveySourcedataQuickSelectController.clearSelectedFile();

        // Hide stale results from previous preview/convert runs.
        if (templateResultsContainer) {
            templateResultsContainer.classList.add('d-none');
            document.getElementById('templateResultSingle')?.classList.add('d-none');
            document.getElementById('templateResultGroups')?.classList.add('d-none');
            document.getElementById('templateResultQuestions')?.classList.add('d-none');
            document.getElementById('participantMetadataSection')?.classList.add('d-none');
        }

        convertInfo.classList.add('d-none');
        convertInfo.textContent = '';
        convertError.classList.add('d-none');
        convertError.textContent = '';

        populateSessionPickers();
        updateSeparatorVisibility('');
        updateConvertBtn();
    }

    clearConvertExcelFileBtn?.addEventListener('click', function() {
        convertServerFilePath = '';
        resetSurveyRefreshFingerprint();
        convertExcelFile.value = '';
        convertExcelFile.dispatchEvent(new Event('change', { bubbles: true }));
        resetSurveyImportFormState();
    });

    const idColSelect = document.getElementById('convertIdColumn');
    if (idColSelect) {
        idColSelect.addEventListener('change', function() {
            this.classList.remove('border-danger');
            convertError.classList.add('d-none');
            scheduleVersionWizardContextSync();
            updateConvertBtn();
        });
    }

    if (convertSessionColumnOverride) {
        convertSessionColumnOverride.addEventListener('change', function() {
            scheduleVersionWizardContextSync();
            updateConvertBtn();
        });
    }

    if (convertRunColumnOverride) {
        convertRunColumnOverride.addEventListener('change', function() {
            scheduleVersionWizardContextSync();
            updateConvertBtn();
        });
    }

    if (convertSeparator) {
        convertSeparator.addEventListener('change', async function() {
            const currentFile = getSelectedSurveyFile();
            const currentFilename = getSelectedSurveyFilename();
            if (currentFilename && isDelimitedSurveyFilename(currentFilename.toLowerCase())) {
                await detectFileColumns(currentFile, currentFile ? '' : convertServerFilePath);
            }
            updateConvertBtn();
        });
    }

    handleModeSwitch();
    updateConvertBtn();
    applySurveyPickerUiState();

    if (browseServerSurveyFileBtn) {
        if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
            window.PrismFileSystemMode.init().then(() => {
                applySurveyPickerUiState();
            }).catch(() => {
                // Keep default host picker behavior on init failures.
            });
        }

        window.addEventListener('prism-library-settings-changed', () => {
            applySurveyPickerUiState();
        });

        browseServerSurveyFileBtn.addEventListener('click', async () => {
            const pickedPath = await pickServerSurveyFile();
            if (!pickedPath) return;

            convertServerFilePath = pickedPath;
            resetSurveyRefreshFingerprint();
            if (convertExcelFile) {
                convertExcelFile.value = '';
            }

            templateWorkflowGate = null;
            cancelVersionWizardSync();
            hideVersionWizard();
            setTemplateEditorErrorCtaVisible(false);

            const filename = getSelectedSurveyFilename().toLowerCase();
            updateSeparatorVisibility(filename);
            if (filename.endsWith('.lss')) {
                convertInfo.innerHTML = '<i class="fas fa-info-circle me-1"></i>.lss files contain structure only (no response data). Use <a href="/template-editor" class="alert-link">Template Editor</a> to generate templates.';
                convertInfo.classList.remove('d-none');
            } else {
                convertInfo.classList.add('d-none');
            }

            await detectFileColumns(null, pickedPath);
            updateConvertBtn();
        });
    }

    surveyWorkflowTemplateCheckController.initialize();

    convertApplyValueOffsetsBtn?.addEventListener('click', function() {
        handleApplyTaskValueOffsetsClick();
    });

    surveySourcedataQuickSelectController.initialize();
    surveyConversionLogController.initialize();

    function appendLog(message, type = 'info', logElement = null) {
        surveyConversionLogController.appendLog(message, type, logElement);
    }

    function resetConversionUI() {
        surveyConversionLogController.resetConversionUI();
    }

    function displayConversionSummary(summary) {
        surveyConversionSummaryController.displayConversionSummary(summary);
    }

    function displayUnmatchedGroupsError(data) {
        let html = `
            <div class="alert alert-warning mb-3">
                <h6 class="mb-1"><i class="fas fa-exclamation-triangle me-1"></i>Templates Required</h6>
                <p class="mb-0">${data.message}</p>
            </div>
            <table class="table table-sm table-bordered">
                <thead><tr>
                    <th>Group</th><th>Task Key</th><th>Items</th><th>Action</th>
                </tr></thead><tbody>`;

        data.unmatched.forEach((g, i) => {
            html += `<tr id="unmatched-row-${i}">
                <td>${g.group_name}</td>
                <td><code>survey-${g.task_key}</code></td>
                <td>${g.item_count}</td>
                <td><button class="btn btn-sm btn-outline-primary" onclick="saveUnmatchedTemplate(${i})">
                    <i class="fas fa-save me-1"></i>Save Template
                </button></td>
            </tr>`;
        });

        html += `</tbody></table>
            <div class="d-flex gap-2 mt-2">
                <button class="btn btn-primary btn-sm" onclick="saveAllUnmatchedTemplates()">
                    <i class="fas fa-save me-1"></i>Save All Templates
                </button>
                <button class="btn btn-success btn-sm" id="rerunConversionBtn" disabled>
                    <i class="fas fa-redo me-1"></i>Re-run Conversion
                </button>
            </div>`;

        window._unmatchedGroupsData = data.unmatched;

        appendLog('Templates required for unmatched groups \u2014 see below', 'error');
        conversionSummaryBody.innerHTML = html;
        conversionSummaryContainer.classList.remove('d-none');
    }

    window.saveUnmatchedTemplate = async function(index) {
        const g = window._unmatchedGroupsData[index];
        const btn = document.querySelector(`#unmatched-row-${index} button`);
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

        try {
            const resp = await fetch('/api/save-unmatched-template', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task_key: g.task_key, prism_json: g.prism_json}),
            });
            const result = await resp.json();

            if (result.success) {
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Saved';
                btn.classList.replace('btn-outline-primary', 'btn-outline-success');
                g._saved = true;
                appendLog(`Template saved: ${result.filename}`, 'success');
                checkAllGroupsSaved();
            } else {
                btn.innerHTML = '<i class="fas fa-times me-1"></i>Failed';
                btn.classList.replace('bn-outline-primary', 'btn-outline-danger');
                btn.disabled = false;
                appendLog(`Failed to save template for ${g.group_name}: ${result.error}`, 'error');
            }
        } catch (err) {
            btn.innerHTML = '<i class="fas fa-times me-1"></i>Error';
            btn.classList.replace('btn-outline-primary', 'btn-outline-danger');
            btn.disabled = false;
            appendLog(`Error saving template: ${err.message}`, 'error');
        }
    };

    window.saveAllUnmatchedTemplates = async function() {
        for (let i = 0; i < window._unmatchedGroupsData.length; i++) {
            if (!window._unmatchedGroupsData[i]._saved) {
                await window.saveUnmatchedTemplate(i);
            }
        }
    };

    function checkAllGroupsSaved() {
        const allSaved = window._unmatchedGroupsData.every(g => g._saved);
        const rerunBtn = document.getElementById('rerunConversionBtn');
        if (rerunBtn) {
            rerunBtn.disabled = !allSaved;
            if (allSaved) {
                rerunBtn.onclick = () => {
                    const previewBtn = document.getElementById('previewBtn');
                    if (previewBtn) previewBtn.click();
                };
            }
        }
    }

    function displayValidationResults(validation, prefix = '') {
        surveyValidationResultsController.displayValidationResults(validation, prefix);
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    const participantsMetadataController = createSurveyParticipantsMetadataController({
        escapeHtml,
    });

    const surveyWorkflowPrepareController = createSurveyWorkflowPrepareController({
        parseJsonResponse,
        buildSurveyWorkflowRequestFormData,
        getEffectiveNearMatchTasks,
        normalizeTaskValueOffsets,
        advanceSurveyRunProgress,
        pauseSurveyRunProgress,
        resumeSurveyRunProgress,
        isAbortError,
        enrichSurveyRunErrorMessage,
        showManualValueOffsetReview,
        promptNearMatchSelection,
        mergeNearMatchTasks,
        applyPreparedSurveyWorkflowContext,
        hasAppliedVersionWizardSelections,
        convertError,
        convertInfo,
        appendLog,
        setTemplateEditorErrorCtaVisible,
        clearActiveSurveyRun,
        finishSurveyRunProgress,
        updateConvertBtn,
        setIsConvertRunning: (value) => {
            isConvertRunning = Boolean(value);
        },
        setIsPreviewRunning: (value) => {
            isPreviewRunning = Boolean(value);
        },
        getTemplateWorkflowGate: () => templateWorkflowGate,
        setTemplateWorkflowGate: (value) => {
            templateWorkflowGate = (value && typeof value === 'object') ? value : null;
        },
        setVersionWizardRetryGateMode: (value) => {
            versionWizardRetryGateMode = value;
        },
        getConfirmedNearMatchTasks: () => confirmedNearMatchTasks,
        setConfirmedNearMatchTasks: (value) => {
            confirmedNearMatchTasks = Array.isArray(value) ? value : [];
        },
        isConfiguredOffsetFailureForCurrentSelection,
        normalizeNearMatchTaskName,
        parseNumericOffsetValue,
        formatSignedOffset,
    });

    const surveyWorkflowPreviewController = createSurveyWorkflowPreviewController({
        convertError,
        convertInfo,
        surveyVersionWizardApplyBtn,
        convertApplyValueOffsetsBtn,
        convertIdMapFile,
        convertSessionColumnOverride,
        convertRunColumnOverride,
        convertLanguage,
        convertDatasetName,
        conversionLogContainer,
        conversionLogBody,
        toggleLogBtn,
        surveyWorkflowPrepareController,
        clearManualValueOffsetAdvice,
        setTemplateEditorErrorCtaVisible,
        hasMultiVersionWizardTasks,
        hasAppliedVersionWizardSelections,
        updateVersionWizardActionState,
        updateConvertBtn,
        hasManualTaskValueOffsets,
        hasAppliedTaskValueOffsetSelections,
        updateTaskValueOffsetApplyState,
        clearSurveyPreviewSelectionState,
        resetConversionUI,
        getEffectiveNearMatchTasks,
        getEffectiveTaskValueOffsets,
        ensureSurveyAdvancedOptionsVisible,
        focusTaskValueOffsetEditor,
        getSurveyPreviewContextKey,
        getSelectedSurveyFilename,
        getSelectedSurveyFile,
        isAdvancedOptionsEnabled,
        refreshSurveyColumnsBeforeRun,
        setActiveSurveyRun,
        startSurveyRunProgress,
        setIsPreviewRunning: (value) => {
            isPreviewRunning = Boolean(value);
        },
        appendSurveyInputToFormData,
        getSurveySessionValue,
        getSelectedSeparator,
        appendTemplateVersionSelections,
        appendLog,
        formatSignedOffset,
        setTemplateWorkflowGate: (value) => {
            templateWorkflowGate = (value && typeof value === 'object') ? value : null;
        },
        getTemplateWorkflowGate: () => templateWorkflowGate,
        getConvertServerFilePath: () => convertServerFilePath,
        advanceSurveyRunProgress,
        parseJsonResponse,
        displayUnmatchedGroupsError,
        populateSurveySessionPickerFromDetected,
        getParticipantRegistryWarning,
        setSurveyPreviewSelectionState,
        displayConversionSummary,
        normalizeSurveyTaskName,
        displayValidationResults,
        formatVersionWizardRunLabel,
        showParticipantRegistryWarning,
        buildVersionWizard,
        hideVersionWizard,
        enrichSurveyRunErrorMessage,
        isAbortError,
        clearActiveSurveyRun,
        finishSurveyRunProgress,
        getActiveRunMode: () => activeRunMode,
        getActiveRunCancelledByUser: () => activeRunCancelledByUser,
        getVersionWizardRetryGateMode: () => versionWizardRetryGateMode,
        setVersionWizardRetryGateMode: (value) => {
            versionWizardRetryGateMode = value;
        },
    });

    const surveyWorkflowConvertController = createSurveyWorkflowConvertController({
        convertError,
        convertInfo,
        surveyVersionWizardApplyBtn,
        convertApplyValueOffsetsBtn,
        convertSessionCustom,
        convertSessionSelect,
        convertIdMapFile,
        convertDatasetName,
        convertLanguage,
        convertIdColumn,
        convertSessionColumnOverride,
        convertRunColumnOverride,
        conversionLogContainer,
        conversionLogBody,
        toggleLogBtn,
        templateResultsContainer,
        surveyWorkflowPrepareController,
        clearManualValueOffsetAdvice,
        setTemplateEditorErrorCtaVisible,
        hasMultiVersionWizardTasks,
        hasAppliedVersionWizardSelections,
        updateVersionWizardActionState,
        updateConvertBtn,
        hasManualTaskValueOffsets,
        hasAppliedTaskValueOffsetSelections,
        updateTaskValueOffsetApplyState,
        hasFreshSurveyPreviewSelectionState,
        getSelectedSurveyTasksForConversion,
        resetConversionUI,
        getEffectiveNearMatchTasks,
        getEffectiveTaskValueOffsets,
        ensureSurveyAdvancedOptionsVisible,
        focusTaskValueOffsetEditor,
        getSelectedSurveyFilename,
        getSelectedSurveyFile,
        getSurveySessionValue,
        isAdvancedOptionsEnabled,
        refreshSurveyColumnsBeforeRun,
        setActiveSurveyRun,
        startSurveyRunProgress,
        setIsConvertRunning: (value) => {
            isConvertRunning = Boolean(value);
        },
        appendSurveyInputToFormData,
        getConvertServerFilePath: () => convertServerFilePath,
        appendLog,
        getSelectedSeparator,
        appendTemplateVersionSelections,
        formatSignedOffset,
        advanceSurveyRunProgress,
        displayUnmatchedGroupsError,
        displayConversionSummary,
        registerSessionInProject,
        getProjectSaveSummary,
        getParticipantRegistryWarning,
        showParticipantRegistryWarning,
        displayValidationResults,
        isAbortError,
        enrichSurveyRunErrorMessage,
        clearActiveSurveyRun,
        finishSurveyRunProgress,
        getActiveRunMode: () => activeRunMode,
        getActiveRunCancelledByUser: () => activeRunCancelledByUser,
        getVersionWizardRetryGateMode: () => versionWizardRetryGateMode,
        setVersionWizardRetryGateMode: (value) => {
            versionWizardRetryGateMode = value;
        },
        getTemplateWorkflowGate: () => templateWorkflowGate,
        setTemplateWorkflowGate: (value) => {
            templateWorkflowGate = (value && typeof value === 'object') ? value : null;
        },
    });

    const surveyTemplateResultsController = createSurveyTemplateResultsController({
        escapeHtml,
    });

    const surveyConversionSummaryController = createSurveyConversionSummaryController({
        conversionSummaryContainer,
        conversionSummaryBody,
        toggleSummaryBtn,
        convertDatasetName,
        getSurveyPreviewSelectionState: () => surveyPreviewSelectionState,
        setSurveyPreviewSelectedTasks,
        normalizeSurveyTaskName,
        formatSignedOffset,
        escapeHtml,
        openAdvancedOptionsValueOffsetEditor,
        updateConvertBtn,
    });

    const surveyConversionLogController = createSurveyConversionLogController({
        toggleLogBtn,
        conversionLogBody,
        conversionLogContainer,
        validationResultsContainer,
        conversionSummaryContainer,
        conversionSummaryBody,
        conversionLog,
        validationSummary,
        validationDetails,
        hideSurveyRunProgress,
    });

    const surveyValidationResultsController = createSurveyValidationResultsController({
        escapeHtml,
    });

    // ===== TEMPLATE GENERATION =====

    async function handleTemplateGeneration(file) {
        const exportMode = document.getElementById('convertTemplateExport')?.value || 'groups';
        const taskName = document.getElementById('convertDatasetName')?.value.trim() || '';

        convertBtn.disabled = true;
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');

        // Show and clear logs
        if (conversionLogContainer) {
            conversionLogContainer.classList.remove('d-none');
        }
        if (conversionLog) {
            conversionLog.innerHTML = '';
        }

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', exportMode);
            if (taskName) {
                formData.append('task_name', taskName);
            }

            const response = await fetch('/api/limesurvey-to-prism', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            // Process logs if returned
            if (data.log && Array.isArray(data.log)) {
                data.log.forEach(entry => {
                    appendLog(entry.message, entry.type, conversionLog);
                });
            }

            if (!response.ok || data.error) {
                throw new Error(data.error || 'Template generation failed');
            }

            currentTemplateData = data;

            // Show results container
            if (templateResultsContainer) {
                templateResultsContainer.classList.remove('d-none');
            }

            // Display results based on mode
            if (data.mode === 'combined') {
                surveyTemplateResultsController.displayTemplateSingle(data);
            } else if (data.mode === 'groups') {
                surveyTemplateResultsController.displayTemplateGroups(data);
            } else if (data.mode === 'questions') {
                surveyTemplateResultsController.displayTemplateQuestions(data);
            }

            // Show participant metadata section for marking fields
            participantsMetadataController.displayParticipantMetadataSection(data);

            convertInfo.textContent = 'Template generation complete!';
            convertInfo.classList.remove('d-none');

        } catch (err) {
            convertError.textContent = err.message;
            convertError.classList.remove('d-none');
            appendLog(`Error: ${err.message}`, 'error', conversionLog);
        } finally {
            updateConvertBtn();
        }
    }

    // ===== PARTICIPANT METADATA MARKING =====

    // ===== MAIN CONVERT HANDLER =====

    let currentTemplateData = null;

    convertBtn.addEventListener('click', () => {
        surveyWorkflowConvertController.handleConvertClick();
    });

    // ===== PREVIEW HANDLER (DRY-RUN) =====

    previewBtn.addEventListener('click', () => {
        surveyWorkflowPreviewController.handlePreviewClick();
    });
}
