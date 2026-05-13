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
import { createSurveyWorkflowConvertResultsController } from './survey-workflow-convert-results.js';
import { createSurveyWorkflowProgressController } from './survey-workflow-progress.js';
import { createSurveySourcedataQuickSelectController } from './survey-sourcedata-quick-select.js';
import { createSurveyTemplateResultsController } from './survey-template-results.js';
import { createSurveyTemplateGenerationController } from './survey-template-generation.js';
import { createSurveyConversionSummaryController } from './survey-conversion-summary.js';
import { createSurveyConversionLogController } from './survey-conversion-log.js';
import { createSurveyConvertFeedbackController } from './survey-convert-feedback.js';
import {
    getSelectedSeparator as getSelectedSeparatorWithSeparatorUtils,
    isDelimitedSurveyFilename as isDelimitedSurveyFilenameWithSeparatorUtils,
    updateSeparatorVisibility as updateSeparatorVisibilityWithSeparatorUtils,
} from './survey-file-separator-utils.js';
import { createSurveyUnmatchedTemplatesController } from './survey-unmatched-templates.js';
import { createSurveyImportFormStateController } from './survey-import-form-state.js';
import { createSurveyNearItemMatchReviewController } from './survey-near-item-match-review.js';
import { createSurveyValidationResultsController } from './survey-validation-results.js';
import { createSurveyValueOffsetEditorController } from './survey-value-offset-editor.js';
import {
    buildVersionSelectionKey as buildVersionSelectionKeyWithUtils,
    compareTimelineContexts as compareTimelineContextsWithUtils,
    compareTimelineSessions as compareTimelineSessionsWithUtils,
    deriveDetectedContexts as deriveDetectedContextsWithUtils,
    getTimelineRunSortMeta as getTimelineRunSortMetaWithUtils,
    getTimelineSessionSortMeta as getTimelineSessionSortMetaWithUtils,
    normalizeTimelineSessionToken as normalizeTimelineSessionTokenWithUtils,
    normalizeVersionSelectionRun as normalizeVersionSelectionRunWithUtils,
    normalizeVersionSelectionSession as normalizeVersionSelectionSessionWithUtils,
} from './survey-version-context-utils.js';
import {
    parseJsonResponse as parseJsonResponseWithWorkflowUtils,
    summarizeServerResponseText as summarizeServerResponseTextWithWorkflowUtils,
} from './survey-workflow-response-utils.js';
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
        convertExcelFile,
        convertSeparator,
        surveySeparatorGroup,
        clearConvertExcelFileBtn,
        convertIdMapFile,
        clearIdMapFileBtn,
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
    let surveyConvertFeedbackController = null;
    let currentTemplateData = null;
    let surveyNearItemMatchReviewController = null;
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
            resetSurveyImportFormState({ clearSelectedInput: true });
        },
    });

    const surveyWorkflowTemplateCheckController = createSurveyWorkflowTemplateCheckController({
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
        return summarizeServerResponseTextWithWorkflowUtils(rawText);
    }

    async function parseJsonResponse(response, requestLabel = 'Request') {
        return parseJsonResponseWithWorkflowUtils(response, requestLabel);
    }

    function normalizeNearMatchTaskName(value) {
        return String(value || '').trim().toLowerCase();
    }

    function collectNearMatchCandidates(payload) {
        if (!surveyNearItemMatchReviewController) {
            return [];
        }
        return surveyNearItemMatchReviewController.collectNearMatchCandidates(payload);
    }

    function buildNearMatchConfirmationMessage(payload, actionLabel) {
        if (!surveyNearItemMatchReviewController) {
            return '';
        }
        return surveyNearItemMatchReviewController.buildNearMatchConfirmationMessage(payload, actionLabel);
    }

    function promptNearMatchSelection(payload, actionLabel) {
        if (!surveyNearItemMatchReviewController) {
            return Promise.resolve({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
        }
        return surveyNearItemMatchReviewController.promptNearMatchSelection(payload, actionLabel);
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
            'Recommended first: fix out-of-range source values, then run Preview again.',
            'Manual task offsets are applied to observed data values (value + offset), not to template scales.',
            'Optional fallback: if you are certain this task is coded on a shifted numeric scale, enter a manual task offset and run Preview again.',
        ].filter(Boolean);

        return lines.join('\n');
    }

    function showManualValueOffsetReview(payload, mode, selectedValueOffsets = {}) {
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
            ensureSurveyAdvancedOptionsVisible();
        } else {
            convertInfo.textContent = 'Out-of-range values were found. Fix source values first, then run Preview again. Manual task offsets are optional in Advanced options.';
        }
        convertInfo.classList.remove('d-none');
        appendLog(getManualValueOffsetReviewMessage(payload, mode), 'warning');
        if (
            task
            && configuredOffset !== null
            && isConfiguredOffsetFailureForCurrentSelection(payload, selectedValueOffsets)
        ) {
            const rowId = ensureTaskValueOffsetEditorRow(task);
            focusTaskValueOffsetEditor(rowId);
        }
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
        return normalizeVersionSelectionSessionWithUtils(session);
    }

    function normalizeVersionSelectionRun(run) {
        return normalizeVersionSelectionRunWithUtils(run);
    }

    function buildVersionSelectionKey({ task, session = null, run = null }) {
        return buildVersionSelectionKeyWithUtils({ task, session, run });
    }

    function getTimelineRunSortMeta(value) {
        return getTimelineRunSortMetaWithUtils(value);
    }

    function getTemplateVersionSelections() {
        const contextualSelections = Object.entries(selectedTemplateVersions)
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

        const selectionsByTask = new Map();
        contextualSelections.forEach((entry) => {
            const task = String(entry?.task || '').trim().toLowerCase();
            const version = String(entry?.version || '').trim();
            if (!task || !version) return;
            if (!selectionsByTask.has(task)) {
                selectionsByTask.set(task, new Set());
            }
            selectionsByTask.get(task).add(version);
        });

        const fallbackSelections = [];
        selectionsByTask.forEach((versionSet, task) => {
            if (!(versionSet instanceof Set) || versionSet.size !== 1) {
                return;
            }
            const onlyVersion = Array.from(versionSet)[0];
            if (!onlyVersion) {
                return;
            }
            fallbackSelections.push({
                task,
                session: null,
                run: null,
                version: onlyVersion,
            });
        });

        const merged = [...contextualSelections, ...fallbackSelections];
        const deduped = [];
        const seen = new Set();
        merged.forEach((entry) => {
            if (!entry) return;
            const key = [
                String(entry.task || '').trim().toLowerCase(),
                entry.session ? String(entry.session).trim() : '',
                entry.run ? String(entry.run).trim() : '',
                String(entry.version || '').trim(),
            ].join('::');
            if (!key || seen.has(key)) return;
            seen.add(key);
            deduped.push(entry);
        });

        return deduped;
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
        return normalizeTimelineSessionTokenWithUtils(value);
    }

    function getTimelineSessionSortMeta(value) {
        return getTimelineSessionSortMetaWithUtils(value);
    }

    function compareTimelineSessions(left, right) {
        return compareTimelineSessionsWithUtils(left, right);
    }

    function compareTimelineContexts(left, right) {
        return compareTimelineContextsWithUtils(left, right);
    }

    function deriveDetectedContexts(taskRuns, previewParticipants, detectedSessions = []) {
        return deriveDetectedContextsWithUtils(taskRuns, previewParticipants, detectedSessions);
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
                const badgeClass = variantId === selectedVersion
                    ? 'survey-version-variant-badge survey-version-variant-badge-active'
                    : 'survey-version-variant-badge';
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

        const updateVersionSelectionFromSelect = (selectEl, selectedVersion, variantDefinitions = []) => {
            const task = String(selectEl.dataset.task || '').trim().toLowerCase();
            const sessionValue = String(selectEl.dataset.session || '').trim();
            const rawRun = String(selectEl.dataset.run || '').trim();
            if (!task) return;
            const normalizedSelection = String(selectedVersion || '').trim();
            const selectionKey = buildVersionSelectionKey({
                task,
                session: sessionValue || null,
                run: rawRun || null,
            });
            selectedTemplateVersions[selectionKey] = normalizedSelection;
            selectEl.value = normalizedSelection;
            const badgeContainer = selectEl.closest('.survey-version-row')?.querySelector('.survey-version-variant-badges');
            if (badgeContainer) {
                badgeContainer.innerHTML = buildVariantDefinitionBadges(variantDefinitions, normalizedSelection);
            }
        };

        entries.sort(([a], [b]) => a.localeCompare(b)).forEach(([task, info]) => {
            const versions = info.versions.map((value) => String(value).trim()).filter(Boolean);
            if (versions.length <= 1) return;

            const contexts = (detectedContexts.length > 0 ? detectedContexts : [{ session: null, run: null }]).slice().sort(compareTimelineContexts);
            const requestedSelection = String(info.selected_version || info.default_version || versions[0]).trim() || versions[0];
            const normalizedRequestedSelection = versions.includes(requestedSelection) ? requestedSelection : versions[0];

            const contextSelections = contexts.map((context) => {
                const selectionKey = buildVersionSelectionKey({ task, session: context.session, run: context.run });
                const existingSelection = String(selectedTemplateVersions[selectionKey] || '').trim();
                const normalizedExistingSelection = existingSelection && versions.includes(existingSelection)
                    ? existingSelection
                    : '';
                return {
                    context,
                    selectionKey,
                    preferredSelection: normalizedExistingSelection || normalizedRequestedSelection,
                    existingSelection: normalizedExistingSelection,
                };
            });

            const existingDistinctSelections = new Set(
                contextSelections
                    .map((entry) => entry.existingSelection)
                    .filter(Boolean)
            );
            const useSharedSelectionByDefault = existingDistinctSelections.size <= 1;
            const sharedSelection = existingDistinctSelections.size === 1
                ? Array.from(existingDistinctSelections)[0]
                : normalizedRequestedSelection;

            if (useSharedSelectionByDefault) {
                contextSelections.forEach((entry) => {
                    entry.preferredSelection = sharedSelection;
                });
            }

            const taskToken = String(task).replace(/[^a-zA-Z0-9_-]/g, '_');
            const bulkToggleId = `surveyVersionBulkMode-${taskToken}`;
            const bulkSelectId = `surveyVersionBulkSelect-${taskToken}`;
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
                            <span class="badge survey-version-meta-badge">${contexts.length} context${contexts.length === 1 ? '' : 's'}</span>
                            <span class="badge survey-version-meta-badge survey-version-meta-badge-strong">${versions.length} versions</span>
                        </div>
                    </div>
                    <div class="survey-version-bulk-controls">
                        <div class="form-check form-switch survey-version-bulk-toggle">
                            <input class="form-check-input survey-version-bulk-mode" type="checkbox" id="${bulkToggleId}" ${useSharedSelectionByDefault ? 'checked' : ''}>
                            <label class="form-check-label small survey-version-bulk-label" for="${bulkToggleId}">Use one version for all sessions/runs (recommended)</label>
                        </div>
                        <div class="survey-version-bulk-row">
                            <label class="form-label small" for="${bulkSelectId}">All sessions/runs</label>
                            <select class="form-select form-select-sm survey-version-bulk-select" id="${bulkSelectId}">
                                ${versions.map((version) => `<option value="${version}"${version === sharedSelection ? ' selected' : ''}>${version}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                    <div class="survey-version-list"></div>
                </div>
            `;
            const groupList = group.querySelector('.survey-version-list');
            if (!groupList) return;

            contextSelections.forEach((entry) => {
                timelineStep += 1;
                const { context, selectionKey, preferredSelection } = entry;
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
                            <div class="small mt-2 survey-version-variant-badges">${buildVariantDefinitionBadges(info.variant_definitions, preferredSelection)}</div>
                        </div>
                    </div>
                `;
                groupList.appendChild(row);
            });

            const contextSelectors = Array.from(groupList.querySelectorAll('.survey-version-select'));
            const bulkModeToggle = group.querySelector('.survey-version-bulk-mode');
            const bulkSelect = group.querySelector('.survey-version-bulk-select');

            const setContextSelectorsLocked = (locked) => {
                contextSelectors.forEach((selectEl) => {
                    selectEl.disabled = locked;
                    selectEl.classList.toggle('survey-version-select-locked', locked);
                });
            };

            const applySharedSelection = (value) => {
                const normalizedValue = String(value || '').trim() || versions[0];
                contextSelectors.forEach((selectEl) => {
                    updateVersionSelectionFromSelect(selectEl, normalizedValue, info.variant_definitions);
                });
                if (bulkSelect) {
                    bulkSelect.value = normalizedValue;
                }
            };

            contextSelectors.forEach((selectEl) => {
                selectEl.addEventListener('change', () => {
                    updateVersionSelectionFromSelect(selectEl, selectEl.value, info.variant_definitions);

                    if (bulkModeToggle && bulkModeToggle.checked) {
                        applySharedSelection(selectEl.value);
                    } else if (bulkSelect) {
                        const values = new Set(contextSelectors.map((entryEl) => String(entryEl.value || '').trim()));
                        if (values.size === 1) {
                            bulkSelect.value = Array.from(values)[0];
                        }
                    }

                    updateVersionWizardActionState();
                    updateConvertBtn();
                });
            });

            bulkSelect?.addEventListener('change', () => {
                applySharedSelection(bulkSelect.value);
                updateVersionWizardActionState();
                updateConvertBtn();
            });

            bulkModeToggle?.addEventListener('change', () => {
                const useSharedSelection = Boolean(bulkModeToggle.checked);
                setContextSelectorsLocked(useSharedSelection);
                if (useSharedSelection) {
                    applySharedSelection(bulkSelect ? bulkSelect.value : versions[0]);
                }
                updateVersionWizardActionState();
                updateConvertBtn();
            });

            setContextSelectorsLocked(Boolean(bulkModeToggle && bulkModeToggle.checked));

            surveyVersionWizardBody.appendChild(group);
        });

        selectedTemplateVersions = nextSelections;
        if (surveyVersionWizardCount) {
            surveyVersionWizardCount.textContent = `${Object.keys(selectedTemplateVersions).length} selector(s)`;
        }
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
        selectedTasks = null,
        includeValidation = false,
        includeIdMap = true,
    } = {}) {
        const formData = new FormData();
        const currentProjectPath = resolveCurrentProjectPath();
        if (currentProjectPath) {
            formData.append('project_path', currentProjectPath);
        }
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
                selectedSurveyTasks: [],
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

        const selectedSurveyTasks = Array.isArray(selectedTasks)
            ? [...new Set(
                selectedTasks
                    .map((task) => normalizeSurveyTaskName(task))
                    .filter(Boolean)
            )]
            : [];
        if (selectedSurveyTasks.length > 0) {
            formData.append('selected_tasks', JSON.stringify(selectedSurveyTasks));
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
            selectedSurveyTasks,
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
        if (!surveyConvertFeedbackController) {
            return { target: 'the active project', countNote: '' };
        }
        return surveyConvertFeedbackController.getProjectSaveSummary(data);
    }

    function openConverterTab(target) {
        if (!surveyConvertFeedbackController) {
            return false;
        }
        return surveyConvertFeedbackController.openConverterTab(target);
    }

    function showConvertInfoMessage(message, options = {}) {
        if (!surveyConvertFeedbackController) {
            return;
        }
        surveyConvertFeedbackController.showConvertInfoMessage(message, options);
    }

    function getParticipantRegistryWarning(payload) {
        if (!surveyConvertFeedbackController) {
            return null;
        }
        return surveyConvertFeedbackController.getParticipantRegistryWarning(payload);
    }

    function showParticipantRegistryWarning(messagePrefix, warning) {
        if (!surveyConvertFeedbackController) {
            return;
        }
        surveyConvertFeedbackController.showParticipantRegistryWarning(messagePrefix, warning);
    }

    function isDelimitedSurveyFilename(filename) {
        return isDelimitedSurveyFilenameWithSeparatorUtils(filename);
    }

    function getSelectedSeparator(filename = '') {
        return getSelectedSeparatorWithSeparatorUtils(filename, convertSeparator);
    }

    function updateSeparatorVisibility(filename = '') {
        updateSeparatorVisibilityWithSeparatorUtils(filename, surveySeparatorGroup);
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

    function resetSurveyImportFormState({ clearSelectedInput = false } = {}) {
        surveyImportFormStateController.resetSurveyImportFormState({ clearSelectedInput });
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
        surveyUnmatchedTemplatesController.displayUnmatchedGroupsError(data);
    }

    function displayValidationResults(validation, prefix = '') {
        surveyValidationResultsController.displayValidationResults(validation, prefix);
    }

    surveyConvertFeedbackController = createSurveyConvertFeedbackController({
        convertInfo,
        appendLog,
    });

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
        resolveCurrentProjectPath,
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
        resolveCurrentProjectPath,
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
        handleConvertSuccess: (data, options) => {
            surveyWorkflowConvertResultsController.handleConvertSuccess(data, options);
        },
        getSelectedSeparator,
        appendTemplateVersionSelections,
        formatSignedOffset,
        advanceSurveyRunProgress,
        displayUnmatchedGroupsError,
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

    const surveyTemplateGenerationController = createSurveyTemplateGenerationController({
        convertBtn,
        convertDatasetName,
        convertError,
        convertInfo,
        conversionLog,
        conversionLogContainer,
        appendLog,
        setCurrentTemplateData: (value) => {
            currentTemplateData = value;
        },
        showTemplateResultsContainer: () => {
            if (templateResultsContainer) {
                templateResultsContainer.classList.remove('d-none');
            }
        },
        displayTemplateSingle: (data) => {
            surveyTemplateResultsController.displayTemplateSingle(data);
        },
        displayTemplateGroups: (data) => {
            surveyTemplateResultsController.displayTemplateGroups(data);
        },
        displayTemplateQuestions: (data) => {
            surveyTemplateResultsController.displayTemplateQuestions(data);
        },
        displayParticipantMetadataSection: (data) => {
            participantsMetadataController.displayParticipantMetadataSection(data);
        },
        updateConvertBtn,
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

    const surveyUnmatchedTemplatesController = createSurveyUnmatchedTemplatesController({
        conversionSummaryBody,
        conversionSummaryContainer,
        appendLog,
    });

    const surveyImportFormStateController = createSurveyImportFormStateController({
        convertSeparator,
        convertIdMapFile,
        clearIdMapFileBtn,
        convertSessionSelect,
        convertSessionCustom,
        convertAdvancedToggle,
        convertExcelFile,
        templateResultsContainer,
        convertInfo,
        convertError,
        surveySourcedataQuickSelectController,
        cancelVersionWizardSync,
        hideVersionWizard,
        clearManualValueOffsetAdvice,
        setTemplateEditorErrorCtaVisible,
        resetConversionUI,
        resetSurveyRefreshFingerprint,
        setCurrentTemplateData: (value) => {
            currentTemplateData = value;
        },
        resetDetectedColumnsState,
        applyAdvancedOptionsState,
        populateSessionPickers,
        updateSeparatorVisibility,
        updateConvertBtn,
        setTemplateWorkflowGate: (value) => {
            templateWorkflowGate = (value && typeof value === 'object') ? value : null;
        },
        setVersionWizardRetryGateMode: (value) => {
            versionWizardRetryGateMode = value;
        },
        setAppliedTaskValueOffsetSelectionSignature: (value) => {
            appliedTaskValueOffsetSelectionSignature = String(value || '');
        },
        setConvertServerFilePath: (value) => {
            convertServerFilePath = String(value || '');
        },
    });

    const surveyValidationResultsController = createSurveyValidationResultsController({
        escapeHtml,
    });

    surveyNearItemMatchReviewController = createSurveyNearItemMatchReviewController({
        normalizeNearMatchTaskName,
        escapeHtml,
    });

    const surveyWorkflowConvertResultsController = createSurveyWorkflowConvertResultsController({
        convertInfo,
        setTemplateEditorErrorCtaVisible,
        appendLog,
        displayConversionSummary,
        getSurveySessionValue,
        registerSessionInProject,
        getProjectSaveSummary,
        getParticipantRegistryWarning,
        showParticipantRegistryWarning,
        displayValidationResults,
    });

    surveyConversionLogController.initialize();
    surveyUnmatchedTemplatesController.initialize();

    // ===== TEMPLATE GENERATION =====

    async function handleTemplateGeneration(file) {
        await surveyTemplateGenerationController.handleTemplateGeneration(file);
    }

    // ===== PARTICIPANT METADATA MARKING =====

    // ===== MAIN CONVERT HANDLER =====

    convertBtn.addEventListener('click', () => {
        surveyWorkflowConvertController.handleConvertClick();
    });

    // ===== PREVIEW HANDLER (DRY-RUN) =====

    previewBtn.addEventListener('click', () => {
        surveyWorkflowPreviewController.handlePreviewClick();
    });
}
