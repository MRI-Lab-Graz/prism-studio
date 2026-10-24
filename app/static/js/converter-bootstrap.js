import { initSurveyConvert } from './modules/converter/survey-convert.js';
import { initParticipants } from './modules/converter/participants.js';
import { initBiometrics } from './modules/converter/biometrics.js';
import { initPhysio } from './modules/converter/physio.js';
import { initEnvironment } from './modules/converter/environment.js';
import { appendConverterLogBatch, appendConverterLogLine } from './modules/converter/log-renderer.js';
import { createConverterSessionPickerController, getSessionInputValue } from './modules/converter/session-picker.js';
import { activateConverterTabFromQuery } from './modules/converter/tab-activation.js';
import { displayConverterValidationResults } from './modules/converter/validation-results-renderer.js';
import { downloadBase64Zip } from './shared/download.js';
import { escapeHtml } from './shared/dom.js';
import { createSessionRegistrar } from './shared/session-register.js';
import { installApiFetchFallback } from './shared/api.js';
import { resolveCurrentProjectPath } from './shared/project-state.js';
import { lockSessionControls, refreshTimepoints } from './modules/converter/single-timepoint.js';

installApiFetchFallback();

if (window.__prismConverterBootstrapInitialized) {
    // Guard against duplicate module imports re-binding event handlers.
} else {
    window.__prismConverterBootstrapInitialized = true;

document.addEventListener('DOMContentLoaded', function() {
    const sessionPickerController = createConverterSessionPickerController({
        resolveCurrentProjectPath,
    });

    function appendLog(message, type = 'info', logElement = null) {
        appendConverterLogLine(
            message,
            type,
            logElement,
            document.getElementById('conversionLog')
        );
    }

    function appendLogBatch(entries, defaultType = 'info', logElement = null) {
        appendConverterLogBatch(
            entries,
            defaultType,
            logElement,
            document.getElementById('conversionLog')
        );
    }

    function populateSessionPickers(projectPath = resolveCurrentProjectPath()) {
        sessionPickerController.populateSessionPickers(projectPath);
    }

    const convertSurveyFile = document.getElementById('convertSurveyFile');
    const convertBtn = document.getElementById('convertBtn');
    const previewBtn = document.getElementById('previewBtn');
    const participantsDataFile = document.getElementById('participantsDataFile');
    const biometricsDataFile = document.getElementById('biometricsDataFile');
    const physioBatchFiles = document.getElementById('physioBatchFiles');

    // Bind registerSessionInProject to the local populateSessionPickers
    const registerSessionInProject = createSessionRegistrar(populateSessionPickers);

    // A cross-sectional project writes ses-1: grey out the session controls of the other converters
    // (the survey page does it in its own session-mode code, next to the "from dates" mode).
    window.addEventListener('prism-timepoints-changed', function(event) {
        const locked = Boolean(event.detail && event.detail.single);
        const byId = (id) => document.getElementById(id);
        lockSessionControls({
            controls: [byId('biometricsSessionSelect'), byId('biometricsSessionCustom')],
            badge: byId('biometricsSessionBadge'), hint: byId('biometricsSessionHint'), label: byId('biometricsSessionLabel'),
        }, locked);
        lockSessionControls({
            controls: [byId('envSessionCol'), byId('envSessionOverride')],
            badge: byId('envSessionBadge'), hint: byId('envSessionHint'),
        }, locked);
        const override = byId('envSessionOverride');
        if (override && locked) {  // the environment page wants a session; the backend writes ses-1 anyway
            override.value = override.value || '1';
            override.dataset.autofilled = '1';
            override.dispatchEvent(new Event('input'));
        } else if (override && override.dataset.autofilled) {
            override.value = '';
            delete override.dataset.autofilled;
            override.dispatchEvent(new Event('input'));
        }
        const split = byId('participantsSessionModeSplit');
        if (split) {
            split.disabled = locked;
            split.title = locked ? 'This project has one timepoint, so values cannot be kept per session.' : '';
        }
    });
    populateSessionPickers();
    activateConverterTabFromQuery();
    refreshTimepoints();
    window.addEventListener('prism-project-changed', function() {
        populateSessionPickers();
        refreshTimepoints();
    });
    window.addEventListener('prism-session-register-failed', function(event) {
        const detail = event && event.detail ? event.detail : {};
        const modality = String(detail.modality || 'converter').trim();
        const message = String(detail.error || 'Session registration failed.').trim();
        appendLog(`[${modality}] ${message}`, 'warning');
    });

    if (convertSurveyFile && convertBtn) {
        initSurveyConvert({
            convertSurveyFile,
            convertSeparator: document.getElementById('convertSeparator'),
            surveySeparatorGroup: document.getElementById('surveySeparatorGroup'),
            clearConvertExcelFileBtn: document.getElementById('clearConvertExcelFileBtn'),
            convertIdMapFile: document.getElementById('convertIdMapFile'),
            clearIdMapFileBtn: document.getElementById('clearIdMapFileBtn'),
            convertBtn,
            previewBtn,
            convertDatasetName: document.getElementById('convertDatasetName'),
            convertLanguage: document.getElementById('convertLanguage'),
            convertError: document.getElementById('convertError'),
            convertInfo: document.getElementById('convertInfo'),
            surveyRunProgressContainer: document.getElementById('surveyRunProgressContainer'),
            surveyRunProgressBar: document.getElementById('surveyRunProgressBar'),
            surveyRunProgressLabel: document.getElementById('surveyRunProgressLabel'),
            surveyRunProgressPercent: document.getElementById('surveyRunProgressPercent'),
            surveyRunCancelBtn: document.getElementById('surveyRunCancelBtn'),
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
            validationSummary: document.getElementById('validationSummary'),
            validationDetails: document.getElementById('validationDetails'),
            conversionSummaryContainer: document.getElementById('conversionSummaryContainer'),
            conversionSummaryBody: document.getElementById('conversionSummaryBody'),
            toggleSummaryBtn: document.getElementById('toggleSummaryBtn'),
            appendLog,
            populateSessionPickers
        });
    }

    if (participantsDataFile) {
        initParticipants();
    }

    if (biometricsDataFile) {
        initBiometrics({
            biometricsDataFile,
            browseBiometricsFileBtn: document.getElementById('browseBiometricsFileBtn'),
            clearBiometricsDataFileBtn: document.getElementById('clearBiometricsDataFileBtn'),
            biometricsPreviewBtn: document.getElementById('biometricsPreviewBtn'),
            biometricsConvertBtn: document.getElementById('biometricsConvertBtn'),
            biometricsError: document.getElementById('biometricsError'),
            biometricsInfo: document.getElementById('biometricsInfo'),
            biometricsProgress: document.getElementById('biometricsProgress'),
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
            biometricsDetectedContainer: document.getElementById('biometricsDetectedContainer'),
            biometricsDetectedList: document.getElementById('biometricsDetectedList'),
            biometricsConfirmBtn: document.getElementById('biometricsConfirmBtn'),
            biometricsSelectAll: document.getElementById('biometricsSelectAll'),
            biometricsSessionSelect: document.getElementById('biometricsSessionSelect'),
            biometricsSessionCustom: document.getElementById('biometricsSessionCustom'),
            biometricsIdColumn: document.getElementById('biometricsIdColumn'),
            biometricsIdColumnStatus: document.getElementById('biometricsIdColumnStatus'),
            biometricsIdColumnHelp: document.getElementById('biometricsIdColumnHelp'),
            appendLog,
            appendLogBatch,
            displayValidationResults: (validation, prefix = '') => {
                displayConverterValidationResults(validation, prefix, escapeHtml);
            },
            registerSessionInProject,
            getBiometricsSessionValue: () => getSessionInputValue(
                document.getElementById('biometricsSessionSelect'),
                document.getElementById('biometricsSessionCustom')
            )
        });
    }

    if (physioBatchFiles) {
        initPhysio({
            physioBatchFiles,
            clearPhysioBatchFilesBtn: document.getElementById('clearPhysioBatchFilesBtn'),
            physioBatchFolder: document.getElementById('physioBatchFolder'),
            browsePhysioFolderBtn: document.getElementById('browsePhysioFolderBtn'),
            clearPhysioBatchFolderBtn: document.getElementById('clearPhysioBatchFolderBtn'),
            physioBatchSamplingRate: document.getElementById('physioBatchSamplingRate'),
            physioBatchDestination: document.getElementById('physioBatchDestination'),
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


    const envDataFile = document.getElementById('envDataFile');
    if (envDataFile) {
        initEnvironment({
            envDataFile,
            envScanMriBtn: document.getElementById('envScanMriBtn'),
            envRescanMriBtn: document.getElementById('envRescanMriBtn'),
            browseEnvFileBtn: document.getElementById('browseEnvFileBtn'),
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
            appendLogBatch,
        });
    }
});
}
