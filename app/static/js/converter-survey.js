import { initSurveyConvert } from './modules/converter/survey-convert.js';

document.addEventListener('DOMContentLoaded', function() {
    function downloadBase64Zip(base64Data, filename) {
        const binaryString = window.atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: 'application/zip' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    }

    function populateSessionPickers() {
        const convertSessionSelect = document.getElementById('convertSessionSelect');
        fetch('/api/projects/sessions/declared')
            .then(r => r.json())
            .then(data => {
                const sessions = data.sessions || [];
                [convertSessionSelect].forEach(sel => {
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
    populateSessionPickers();

    if (convertExcelFile && convertBtn) {
        initSurveyConvert({
            convertLibraryPathInput: document.getElementById('convertLibraryPath'),
            convertBrowseLibraryBtn: document.getElementById('convertBrowseLibraryBtn'),
            convertExcelFile,
            clearConvertExcelFileBtn: document.getElementById('clearConvertExcelFileBtn'),
            convertIdMapFile: document.getElementById('convertIdMapFile'),
            clearIdMapFileBtn: document.getElementById('clearIdMapFileBtn'),
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
            sourcedataQuickSelect: document.getElementById('sourcedataQuickSelect'),
            sourcedataFileSelect: document.getElementById('sourcedataFileSelect'),
            conversionLogContainer: document.getElementById('conversionLogContainer'),
            conversionLog: document.getElementById('conversionLog'),
            conversionLogBody: document.getElementById('conversionLogBody'),
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
});
