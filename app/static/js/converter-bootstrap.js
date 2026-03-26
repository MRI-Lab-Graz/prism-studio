import { initSurveyConvert } from './modules/converter/survey-convert.js';
import { initBiometrics } from './modules/converter/biometrics.js';
import { initPhysio } from './modules/converter/physio.js';
import { initEyetracking } from './modules/converter/eyetracking.js';
import { initEnvironment } from './modules/converter/environment.js';
import { downloadBase64Zip } from './shared/download.js';
import { escapeHtml } from './shared/dom.js';
import { createSessionRegistrar } from './shared/session-register.js';

document.addEventListener('DOMContentLoaded', function() {
    function appendLog(message, type = 'info', logElement = null) {
        const colors = {
            info: '#17a2b8',
            success: '#28a745',
            warning: '#ffc107',
            error: '#dc3545',
            step: '#6c757d'
        };

        const fallbackLog = document.getElementById('conversionLog');
        const targetLog = logElement || fallbackLog;
        if (!targetLog) return;

        const timestamp = new Date().toLocaleTimeString();
        const color = colors[type] || colors.info;
        const line = document.createElement('span');
        line.style.color = color;
        line.textContent = `[${timestamp}] ${String(message)}`;
        targetLog.appendChild(line);
        targetLog.appendChild(document.createTextNode('\n'));
        targetLog.scrollTop = targetLog.scrollHeight;
    }

    function displayValidationResults(validation, prefix = '') {
        const toId = (id) => (prefix ? `${prefix}${id.charAt(0).toUpperCase()}${id.slice(1)}` : id);
        const container = document.getElementById(toId('validationResultsContainer'));
        const card = document.getElementById(toId('validationResultsCard'));
        const header = document.getElementById(toId('validationResultsHeader'));
        const badge = document.getElementById(toId('validationBadge'));
        const summaryEl = document.getElementById(toId('validationSummary'));
        const detailsEl = document.getElementById(toId('validationDetails'));
        const downloadSection = document.getElementById(toId('downloadSection'));
        const downloadWarningSection = document.getElementById(toId('downloadWarningSection'));

        if (!container || !card || !header || !badge || !summaryEl || !detailsEl || !downloadSection || !downloadWarningSection) {
            return;
        }

        const errors = validation.errors || [];
        const warnings = validation.warnings || [];
        const isValid = errors.length === 0;

        container.classList.remove('d-none');

        card.classList.remove('border-success', 'border-warning', 'border-danger');
        header.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'text-white', 'text-dark');

        if (isValid && warnings.length === 0) {
            card.classList.add('border-success');
            header.classList.add('bg-success', 'text-white');
            badge.className = 'badge bg-light text-success';
            badge.textContent = '✓ Valid';
        } else if (isValid) {
            card.classList.add('border-warning');
            header.classList.add('bg-warning', 'text-dark');
            badge.className = 'badge bg-light text-warning';
            badge.textContent = `⚠ ${warnings.length} Warning(s)`;
        } else {
            card.classList.add('border-danger');
            header.classList.add('bg-danger', 'text-white');
            badge.className = 'badge bg-light text-danger';
            badge.textContent = `✗ ${errors.length} Error(s)`;
        }

        const summary = validation.summary || {};
        summaryEl.innerHTML = `
            <div class="row text-center">
                <div class="col-4">
                    <div class="h4 mb-0 ${errors.length > 0 ? 'text-danger' : 'text-success'}">${errors.length}</div>
                    <small class="text-muted">Errors</small>
                </div>
                <div class="col-4">
                    <div class="h4 mb-0 ${warnings.length > 0 ? 'text-warning' : 'text-success'}">${warnings.length}</div>
                    <small class="text-muted">Warnings</small>
                </div>
                <div class="col-4">
                    <div class="h4 mb-0 text-info">${summary.total_files || summary.files_created || 'n/a'}</div>
                    <small class="text-muted">Files</small>
                </div>
            </div>
        `;

        const formatted = validation.formatted;
        if (formatted && (formatted.errors || formatted.warnings)) {
            let detailsHtml = '';
            if (Array.isArray(formatted.errors) && formatted.errors.length > 0) {
                detailsHtml += '<h6 class="text-danger mt-3"><i class="fas fa-times-circle me-1"></i>Errors</h6>';
                formatted.errors.forEach(group => {
                    detailsHtml += `<div class="small mb-2"><strong>${escapeHtml(group.code || 'ERROR')}</strong>: ${escapeHtml(group.message || '')}</div>`;
                });
            }
            if (Array.isArray(formatted.warnings) && formatted.warnings.length > 0) {
                detailsHtml += '<h6 class="text-warning mt-3"><i class="fas fa-exclamation-triangle me-1"></i>Warnings</h6>';
                formatted.warnings.forEach(group => {
                    detailsHtml += `<div class="small mb-2"><strong>${escapeHtml(group.code || 'WARN')}</strong>: ${escapeHtml(group.message || '')}</div>`;
                });
            }
            detailsEl.innerHTML = detailsHtml;
        } else {
            detailsEl.innerHTML = [
                errors.length > 0
                    ? `<h6 class="text-danger mt-3"><i class="fas fa-times-circle me-1"></i>Errors</h6><ul class="list-unstyled">${errors.map(e => `<li class="text-danger small"><i class="fas fa-times me-1"></i>${escapeHtml(e)}</li>`).join('')}</ul>`
                    : '',
                warnings.length > 0
                    ? `<h6 class="text-warning mt-3"><i class="fas fa-exclamation-triangle me-1"></i>Warnings</h6><ul class="list-unstyled">${warnings.map(w => `<li class="text-warning small"><i class="fas fa-exclamation me-1"></i>${escapeHtml(w)}</li>`).join('')}</ul>`
                    : ''
            ].join('');
        }

        if (isValid && warnings.length === 0) {
            downloadSection.classList.remove('d-none');
            downloadWarningSection.classList.add('d-none');
        } else if (isValid) {
            downloadSection.classList.add('d-none');
            downloadWarningSection.classList.remove('d-none');
        } else {
            downloadSection.classList.add('d-none');
            downloadWarningSection.classList.add('d-none');
        }
    }

    function getSessionValue(selectEl, customEl) {
        const selVal = selectEl ? selectEl.value.trim() : '';
        const custVal = customEl ? customEl.value.trim() : '';
        return selVal || custVal;
    }

    function getBiometricsSessionValue() {
        return getSessionValue(
            document.getElementById('biometricsSessionSelect'),
            document.getElementById('biometricsSessionCustom')
        );
    }

    function populateSessionPickers() {
        const convertSessionSelect = document.getElementById('convertSessionSelect');
        const biometricsSessionSelect = document.getElementById('biometricsSessionSelect');

        fetch('/api/projects/sessions/declared')
            .then(r => r.json())
            .then(data => {
                const sessions = data.sessions || [];
                [convertSessionSelect, biometricsSessionSelect].forEach(sel => {
                    if (!sel) return;
                    while (sel.options.length > 1) sel.remove(1);
                    sessions.forEach(s => {
                        const opt = document.createElement('option');
                        opt.value = s.id.replace(/^ses-/, '');
                        opt.textContent = s.label !== s.id ? `${s.id} — ${s.label}` : s.id;
                        sel.appendChild(opt);
                    });
                });
            })
            .catch(() => {});
    }

    const convertExcelFile = document.getElementById('convertExcelFile');
    const convertBtn = document.getElementById('convertBtn');
    const previewBtn = document.getElementById('previewBtn');
    const biometricsDataFile = document.getElementById('biometricsDataFile');
    const physioBatchFiles = document.getElementById('physioBatchFiles');
    const eyetrackingBatchFiles = document.getElementById('eyetrackingBatchFiles');

    // Bind registerSessionInProject to the local populateSessionPickers
    const registerSessionInProject = createSessionRegistrar(populateSessionPickers);

    populateSessionPickers();

    if (convertExcelFile && convertBtn) {
        initSurveyConvert({
            convertLibraryPathInput: document.getElementById('convertLibraryPath'),
            convertBrowseLibraryBtn: document.getElementById('convertBrowseLibraryBtn'),
            convertExcelFile,
            convertSeparator: document.getElementById('convertSeparator'),
            surveySeparatorGroup: document.getElementById('surveySeparatorGroup'),
            clearConvertExcelFileBtn: document.getElementById('clearConvertExcelFileBtn'),
            convertIdMapFile: document.getElementById('convertIdMapFile'),
            clearIdMapFileBtn: document.getElementById('clearIdMapFileBtn'),
            checkProjectTemplatesBtn: document.getElementById('checkProjectTemplatesBtn'),
            convertBtn,
            previewBtn,
            convertDatasetName: document.getElementById('convertDatasetName'),
            convertLanguage: document.getElementById('convertLanguage'),
            convertError: document.getElementById('convertError'),
            convertInfo: document.getElementById('convertInfo'),
            convertIdColumnGroup: document.getElementById('convertIdColumnGroup'),
            convertIdColumn: document.getElementById('convertIdColumn'),
            convertTemplateExportGroup: document.getElementById('convertTemplateExportGroup'),
            convertLanguageGroup: document.getElementById('convertLanguageGroup'),
            convertAliasGroup: document.getElementById('convertAliasGroup'),
            convertSessionGroup: document.getElementById('convertSessionGroup'),
            templateResultsContainer: document.getElementById('templateResultsContainer'),
            convertSessionSelect: document.getElementById('convertSessionSelect'),
            convertSessionCustom: document.getElementById('convertSessionCustom'),
            biometricsSessionSelect: document.getElementById('biometricsSessionSelect'),
            biometricsSessionCustom: document.getElementById('biometricsSessionCustom'),
            sourcedataQuickSelect: document.getElementById('sourcedataQuickSelect'),
            sourcedataFileSelect: document.getElementById('sourcedataFileSelect'),
            conversionLogContainer: document.getElementById('conversionLogContainer'),
            conversionLog: document.getElementById('conversionLog'),
            conversionLogBody: document.getElementById('conversionLogBody'),
            templateEditorErrorCta: document.getElementById('templateEditorErrorCta'),
            toggleLogBtn: document.getElementById('toggleLogBtn'),
            validationResultsContainer: document.getElementById('validationResultsContainer'),
            validationResultsCard: document.getElementById('validationResultsCard'),
            validationResultsHeader: document.getElementById('validationResultsHeader'),
            validationBadge: document.getElementById('validationBadge'),
            validationSummary: document.getElementById('validationSummary'),
            validationDetails: document.getElementById('validationDetails'),
            downloadSection: document.getElementById('downloadSection'),
            downloadWarningSection: document.getElementById('downloadWarningSection'),
            downloadZipBtn: document.getElementById('downloadZipBtn'),
            downloadZipWarningBtn: document.getElementById('downloadZipWarningBtn'),
            conversionSummaryContainer: document.getElementById('conversionSummaryContainer'),
            conversionSummaryBody: document.getElementById('conversionSummaryBody'),
            toggleSummaryBtn: document.getElementById('toggleSummaryBtn'),
            downloadBase64Zip,
            populateSessionPickers
        });
    }

    if (biometricsDataFile) {
        initBiometrics({
            biometricsDataFile,
            clearBiometricsDataFileBtn: document.getElementById('clearBiometricsDataFileBtn'),
            biometricsPreviewBtn: document.getElementById('biometricsPreviewBtn'),
            biometricsConvertBtn: document.getElementById('biometricsConvertBtn'),
            biometricsError: document.getElementById('biometricsError'),
            biometricsInfo: document.getElementById('biometricsInfo'),
            biometricsLogContainer: document.getElementById('biometricsLogContainer'),
            biometricsLog: document.getElementById('biometricsLog'),
            biometricsLogBody: document.getElementById('biometricsLogBody'),
            toggleBiometricsLogBtn: document.getElementById('toggleBiometricsLogBtn'),
            biometricsValidationResultsContainer: document.getElementById('biometricsValidationResultsContainer'),
            biometricsValidationResultsCard: document.getElementById('biometricsValidationResultsCard'),
            biometricsValidationResultsHeader: document.getElementById('biometricsValidationResultsHeader'),
            biometricsValidationBadge: document.getElementById('biometricsValidationBadge'),
            biometricsValidationSummary: document.getElementById('biometricsValidationSummary'),
            biometricsValidationDetails: document.getElementById('biometricsValidationDetails'),
            biometricsDownloadSection: document.getElementById('biometricsDownloadSection'),
            biometricsDownloadWarningSection: document.getElementById('biometricsDownloadWarningSection'),
            biometricsDownloadZipBtn: document.getElementById('biometricsDownloadZipBtn'),
            biometricsDownloadZipWarningBtn: document.getElementById('biometricsDownloadZipWarningBtn'),
            biometricsDetectedContainer: document.getElementById('biometricsDetectedContainer'),
            biometricsDetectedList: document.getElementById('biometricsDetectedList'),
            biometricsConfirmBtn: document.getElementById('biometricsConfirmBtn'),
            biometricsSelectAll: document.getElementById('biometricsSelectAll'),
            biometricsSessionSelect: document.getElementById('biometricsSessionSelect'),
            biometricsSessionCustom: document.getElementById('biometricsSessionCustom'),
            appendLog,
            displayValidationResults,
            downloadBase64Zip,
            registerSessionInProject,
            getBiometricsSessionValue
        });
    }

    if (physioBatchFiles) {
        initPhysio({
            physioRawFile: document.getElementById('physioRawFile'),
            physioTask: document.getElementById('physioTask'),
            physioSamplingRate: document.getElementById('physioSamplingRate'),
            physioConvertBtn: document.getElementById('physioConvertBtn'),
            physioError: document.getElementById('physioError'),
            physioInfo: document.getElementById('physioInfo'),
            physioBatchFiles,
            clearPhysioBatchFilesBtn: document.getElementById('clearPhysioBatchFilesBtn'),
            physioBatchFolder: document.getElementById('physioBatchFolder'),
            clearPhysioBatchFolderBtn: document.getElementById('clearPhysioBatchFolderBtn'),
            physioBatchSamplingRate: document.getElementById('physioBatchSamplingRate'),
            physioGenerateReports: document.getElementById('physioGenerateReports'),
            physioBatchDryRun: document.getElementById('physioBatchDryRun'),
            physioBatchPreviewBtn: document.getElementById('physioBatchPreviewBtn'),
            physioBatchConvertBtn: document.getElementById('physioBatchConvertBtn'),
            physioBatchCancelBtn: document.getElementById('physioBatchCancelBtn'),
            physioBatchError: document.getElementById('physioBatchError'),
            physioBatchInfo: document.getElementById('physioBatchInfo'),
            physioBatchProgress: document.getElementById('physioBatchProgress'),
            physioBatchLogContainer: document.getElementById('physioBatchLogContainer'),
            physioBatchLog: document.getElementById('physioBatchLog'),
            physioBatchLogClearBtn: document.getElementById('physioBatchLogClearBtn'),
            autoDetectPhysioBtn: document.getElementById('autoDetectPhysioBtn'),
            autoDetectHint: document.getElementById('autoDetectHint'),
            physioBatchFolderPath: document.getElementById('physioBatchFolderPath'),
            appendLog
        });
    }

    if (eyetrackingBatchFiles) {
        initEyetracking({
            eyetrackingSingleFile: document.getElementById('eyetrackingSingleFile'),
            eyetrackingSubject: document.getElementById('eyetrackingSubject'),
            eyetrackingSession: document.getElementById('eyetrackingSession'),
            eyetrackingTask: document.getElementById('eyetrackingTask'),
            eyetrackingSingleConvertBtn: document.getElementById('eyetrackingSingleConvertBtn'),
            eyetrackingSingleError: document.getElementById('eyetrackingSingleError'),
            eyetrackingSingleInfo: document.getElementById('eyetrackingSingleInfo'),
            eyetrackingBatchFiles,
            clearEyetrackingBatchFilesBtn: document.getElementById('clearEyetrackingBatchFilesBtn'),
            eyetrackingBatchDatasetName: document.getElementById('eyetrackingBatchDatasetName'),
            eyetrackingBatchPreviewBtn: document.getElementById('eyetrackingBatchPreviewBtn'),
            eyetrackingBatchConvertBtn: document.getElementById('eyetrackingBatchConvertBtn'),
            eyetrackingBatchError: document.getElementById('eyetrackingBatchError'),
            eyetrackingBatchInfo: document.getElementById('eyetrackingBatchInfo'),
            eyetrackingBatchProgress: document.getElementById('eyetrackingBatchProgress'),
            eyetrackingBatchLogContainer: document.getElementById('eyetrackingBatchLogContainer'),
            eyetrackingBatchLog: document.getElementById('eyetrackingBatchLog'),
            eyetrackingBatchLogClearBtn: document.getElementById('eyetrackingBatchLogClearBtn'),
            eyetrackingBatchDryRunCheckbox: document.getElementById('eyetrackingBatchDryRun'),
            downloadBase64Zip
        });
    }

    const envDataFile = document.getElementById('envDataFile');
    if (envDataFile) {
        initEnvironment({
            envDataFile,
            clearEnvDataFileBtn: document.getElementById('clearEnvDataFileBtn'),
            envPreviewBtn: document.getElementById('envPreviewBtn'),
            envSeparatorGroup: document.getElementById('envSeparatorGroup'),
            envSeparator: document.getElementById('envSeparator'),
            envTimestampCol: document.getElementById('envTimestampCol'),
            envParticipantCol: document.getElementById('envParticipantCol'),
            envParticipantOverride: document.getElementById('envParticipantOverride'),
            envSessionCol: document.getElementById('envSessionCol'),
            envSessionOverride: document.getElementById('envSessionOverride'),
            envLocationCol: document.getElementById('envLocationCol'),
            envLatCol: document.getElementById('envLatCol'),
            envLonCol: document.getElementById('envLonCol'),
            envLocationQuery: document.getElementById('envLocationQuery'),
            envLocationSearchBtn: document.getElementById('envLocationSearchBtn'),
            envLocationResults: document.getElementById('envLocationResults'),
            envLocationLabel: document.getElementById('envLocationLabel'),
            envLat: document.getElementById('envLat'),
            envLon: document.getElementById('envLon'),
            envConvertBackground: document.getElementById('envConvertBackground'),
            envPilotRunBtn: document.getElementById('envPilotRunBtn'),
            envConvertBtn: document.getElementById('envConvertBtn'),
            envCancelBtn: document.getElementById('envCancelBtn'),
            envError: document.getElementById('envError'),
            envInfo: document.getElementById('envInfo'),
            envProgressContainer: document.getElementById('envProgressContainer'),
            envProgressBar: document.getElementById('envProgressBar'),
            envProgressText: document.getElementById('envProgressText'),
            envCompatibilityInfo: document.getElementById('envCompatibilityInfo'),
            envCompatibilityText: document.getElementById('envCompatibilityText'),
            envColumnMapping: document.getElementById('envColumnMapping'),
            envDataPreview: document.getElementById('envDataPreview'),
            envPreviewHead: document.getElementById('envPreviewHead'),
            envPreviewBody: document.getElementById('envPreviewBody'),
            envLogContainer: document.getElementById('envLogContainer'),
            envLog: document.getElementById('envLog'),
            envLogBody: document.getElementById('envLogBody'),
            envOutputPreview: document.getElementById('envOutputPreview'),
            envOutputPreviewHead: document.getElementById('envOutputPreviewHead'),
            envOutputPreviewBody: document.getElementById('envOutputPreviewBody'),
            toggleEnvLogBtn: document.getElementById('toggleEnvLogBtn'),
            appendLog,
        });
    }
});
