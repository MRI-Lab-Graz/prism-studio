import { initLimeSurveyQuickImport } from './modules/converter/limesurvey.js';
import { initBiometrics } from './modules/converter/biometrics.js';
import { initPhysio } from './modules/converter/physio.js';

document.addEventListener('DOMContentLoaded', function() {
    // --- LimeSurvey Quick Import ---
    // Initialize LimeSurvey module with DOM elements
    const lssElements = {
        lssFile: document.getElementById('lssFile'),
        lssTaskName: document.getElementById('lssTaskName'),
        lssConvertBtn: document.getElementById('lssConvertBtn'),
        lssError: document.getElementById('lssError'),
        lssResultSingle: document.getElementById('lssResultSingle'),
        lssQuestionCount: document.getElementById('lssQuestionCount'),
        lssPreviewBtn: document.getElementById('lssPreviewBtn'),
        lssDownloadBtn: document.getElementById('lssDownloadBtn'),
        lssPreview: document.getElementById('lssPreview'),
        lssPreviewContent: document.getElementById('lssPreviewContent'),
        lssResultMultiple: document.getElementById('lssResultMultiple'),
        lssGroupCount: document.getElementById('lssGroupCount'),
        lssTotalQuestions: document.getElementById('lssTotalQuestions'),
        lssDownloadAllBtn: document.getElementById('lssDownloadAllBtn'),
        lssQuestionnaireList: document.getElementById('lssQuestionnaireList'),
        lssResultQuestions: document.getElementById('lssResultQuestions'),
        lssIndividualCount: document.getElementById('lssIndividualCount'),
        lssDownloadAllQuestionsBtn: document.getElementById('lssDownloadAllQuestionsBtn'),
        lssQuestionsList: document.getElementById('lssQuestionsList'),
        lssSaveGroupsToProjectBtn: document.getElementById('lssSaveGroupsToProjectBtn'),
        lssSaveQuestionsToProjectBtn: document.getElementById('lssSaveQuestionsToProjectBtn'),
        lssSaveSuccess: document.getElementById('lssSaveSuccess'),
        lssSaveSuccessMessage: document.getElementById('lssSaveSuccessMessage')
    };
    
    // Only initialize if lssFile exists (page guard)
    if (lssElements.lssFile) {
        initLimeSurveyQuickImport(lssElements);
    }
    
    // --- Landgig: Survey Convert ---
    const convertLibraryPathInput = document.getElementById('convertLibraryPath');
    const convertBrowseLibraryBtn = document.getElementById('convertBrowseLibraryBtn');
    const convertExcelFile = document.getElementById('convertExcelFile');
    const clearConvertExcelFileBtn = document.getElementById('clearConvertExcelFileBtn');
    const convertIdMapFile = document.getElementById('convertIdMapFile');
    const clearIdMapFileBtn = document.getElementById('clearIdMapFileBtn');
    const convertBtn = document.getElementById('convertBtn');
    const previewBtn = document.getElementById('previewBtn');
    const convertDatasetName = document.getElementById('convertDatasetName');
    const convertLanguage = document.getElementById('convertLanguage');
    const convertError = document.getElementById('convertError');
    const convertInfo = document.getElementById('convertInfo');

    if (convertIdMapFile) {
        const updateIdMapClearButtonState = () => {
            const hasFile = Boolean(convertIdMapFile.files && convertIdMapFile.files[0]);
            clearIdMapFileBtn?.classList.toggle('d-none', !hasFile);
        };

        convertIdMapFile.addEventListener('change', () => {
            const f = convertIdMapFile.files && convertIdMapFile.files[0];
            if (f) {
                // Just log selection, don't validate (avoids stream issues)
                console.log(`ID map file selected: ${f.name} (${f.size} bytes)`);
            }
            updateIdMapClearButtonState();
        });

        clearIdMapFileBtn?.addEventListener('click', () => {
            convertIdMapFile.value = '';
            updateIdMapClearButtonState();
            convertError?.classList.add('d-none');
            convertError.textContent = '';
        });

        updateIdMapClearButtonState();
    }

    // --- Biometrics Convert ---
    const biometricsDataFile = document.getElementById('biometricsDataFile');
    const clearBiometricsDataFileBtn = document.getElementById('clearBiometricsDataFileBtn');
    const biometricsPreviewBtn = document.getElementById('biometricsPreviewBtn');
    const biometricsConvertBtn = document.getElementById('biometricsConvertBtn');
    const biometricsError = document.getElementById('biometricsError');
    const biometricsInfo = document.getElementById('biometricsInfo');
    const biometricsLogContainer = document.getElementById('biometricsLogContainer');
    const biometricsLog = document.getElementById('biometricsLog');
    const biometricsLogBody = document.getElementById('biometricsLogBody');
    const toggleBiometricsLogBtn = document.getElementById('toggleBiometricsLogBtn');
    const biometricsValidationResultsContainer = document.getElementById('biometricsValidationResultsContainer');
    const biometricsValidationResultsCard = document.getElementById('biometricsValidationResultsCard');
    const biometricsValidationResultsHeader = document.getElementById('biometricsValidationResultsHeader');
    const biometricsValidationBadge = document.getElementById('biometricsValidationBadge');
    const biometricsValidationSummary = document.getElementById('biometricsValidationSummary');
    const biometricsValidationDetails = document.getElementById('biometricsValidationDetails');
    const biometricsDownloadSection = document.getElementById('biometricsDownloadSection');
    const biometricsDownloadWarningSection = document.getElementById('biometricsDownloadWarningSection');
    const biometricsDownloadZipBtn = document.getElementById('biometricsDownloadZipBtn');
    const biometricsDownloadZipWarningBtn = document.getElementById('biometricsDownloadZipWarningBtn');
    const biometricsDetectedContainer = document.getElementById('biometricsDetectedContainer');
    const biometricsDetectedList = document.getElementById('biometricsDetectedList');
    const biometricsConfirmBtn = document.getElementById('biometricsConfirmBtn');
    const biometricsSelectAll = document.getElementById('biometricsSelectAll');

    // --- Physio Convert (Single) ---
    const physioRawFile = document.getElementById('physioRawFile');
    const physioTask = document.getElementById('physioTask');
    const physioSamplingRate = document.getElementById('physioSamplingRate');
    const physioConvertBtn = document.getElementById('physioConvertBtn');
    const physioError = document.getElementById('physioError');
    const physioInfo = document.getElementById('physioInfo');

    // --- Physio Convert (Batch) ---
    const physioBatchFiles = document.getElementById('physioBatchFiles');
    const clearPhysioBatchFilesBtn = document.getElementById('clearPhysioBatchFilesBtn');
    const physioBatchFolder = document.getElementById('physioBatchFolder');
    const clearPhysioBatchFolderBtn = document.getElementById('clearPhysioBatchFolderBtn');
    const physioBatchSamplingRate = document.getElementById('physioBatchSamplingRate');
    const physioBatchDryRun = document.getElementById('physioBatchDryRun');
    const physioBatchConvertBtn = document.getElementById('physioBatchConvertBtn');
    const physioBatchError = document.getElementById('physioBatchError');
    const physioBatchInfo = document.getElementById('physioBatchInfo');
    const physioBatchProgress = document.getElementById('physioBatchProgress');
    const physioBatchLogContainer = document.getElementById('physioBatchLogContainer');
    const physioBatchLog = document.getElementById('physioBatchLog');
    const physioBatchLogClearBtn = document.getElementById('physioBatchLogClearBtn');
    const autoDetectPhysioBtn = document.getElementById('autoDetectPhysioBtn');
    const autoDetectHint = document.getElementById('autoDetectHint');

    // --- Eyetracking Convert (Single) ---
    const eyetrackingSingleFile = document.getElementById('eyetrackingSingleFile');
    const eyetrackingSubject = document.getElementById('eyetrackingSubject');
    const eyetrackingSession = document.getElementById('eyetrackingSession');
    const eyetrackingTask = document.getElementById('eyetrackingTask');
    const eyetrackingSingleConvertBtn = document.getElementById('eyetrackingSingleConvertBtn');
    const eyetrackingSingleError = document.getElementById('eyetrackingSingleError');
    const eyetrackingSingleInfo = document.getElementById('eyetrackingSingleInfo');

    // --- Eyetracking Convert (Batch) ---
    const eyetrackingBatchFiles = document.getElementById('eyetrackingBatchFiles');
    const clearEyetrackingBatchFilesBtn = document.getElementById('clearEyetrackingBatchFilesBtn');
    const eyetrackingBatchDatasetName = document.getElementById('eyetrackingBatchDatasetName');
    const eyetrackingBatchConvertBtn = document.getElementById('eyetrackingBatchConvertBtn');
    const eyetrackingBatchError = document.getElementById('eyetrackingBatchError');
    const eyetrackingBatchInfo = document.getElementById('eyetrackingBatchInfo');
    const eyetrackingBatchProgress = document.getElementById('eyetrackingBatchProgress');
    const eyetrackingBatchLogContainer = document.getElementById('eyetrackingBatchLogContainer');
    const eyetrackingBatchLog = document.getElementById('eyetrackingBatchLog');
    const eyetrackingBatchLogClearBtn = document.getElementById('eyetrackingBatchLogClearBtn');

    // --- Organize (Batch) ---
    const organizeFiles = document.getElementById('organizeFiles');
    const organizeDatasetName = document.getElementById('organizeDatasetName');
    const organizeModality = document.getElementById('organizeModality');
    const organizeBtn = document.getElementById('organizeBtn');
    const organizeError = document.getElementById('organizeError');
    const organizeInfo = document.getElementById('organizeInfo');
    const organizeProgress = document.getElementById('organizeProgress');
    const organizeLogContainer = document.getElementById('organizeLogContainer');
    const organizeLog = document.getElementById('organizeLog');
    const organizeLogClearBtn = document.getElementById('organizeLogClearBtn');

    // --- Physio Renamer ---
    const renamerFiles = document.getElementById('renamerFiles');
    const renamerPattern = document.getElementById('renamerPattern');
    const renamerReplacement = document.getElementById('renamerReplacement');
    const renamerTask = document.getElementById('renamerTask');
    const renamerDryRunBtn = document.getElementById('renamerDryRunBtn');
    const renamerDownloadBtn = document.getElementById('renamerDownloadBtn');
    const renamerResetBtn = document.getElementById('renamerResetBtn');
    const renamerPreview = document.getElementById('renamerPreview');
    const renamerPreviewBody = document.getElementById('renamerPreviewBody');
    const renamerFilterAll = document.getElementById('renamerFilterAll');
    const renamerFilterUnmatched = document.getElementById('renamerFilterUnmatched');
    const renamerError = document.getElementById('renamerError');
    const renamerInfo = document.getElementById('renamerInfo');

    if (convertBrowseLibraryBtn && convertLibraryPathInput) {
        convertBrowseLibraryBtn.addEventListener('click', function() {
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

    function downloadBase64Zip(base64Data, filename) {
        const binaryString = window.atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], {type: 'application/zip'});
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    }

    function refreshConvertLanguages() {
        const libraryPath = convertLibraryPathInput ? convertLibraryPathInput.value.trim() : '';
        const surveyI18nWarning = document.getElementById('surveyI18nWarning');
        const surveyI18nMessage = document.getElementById('surveyI18nMessage');
        const surveyStructureWarning = document.getElementById('surveyStructureWarning');
        const surveyStructureMessage = document.getElementById('surveyStructureMessage');
        
        if (!libraryPath) {
            // Hide warnings and reset languages if no path
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

                // Reset options (keep Auto)
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
                
                // Show structure warning if missing folders/files
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
                
                // Show I18n warning if templates don't have multilanguage support
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
                // If this fails, keep the dropdown as-is (Auto only)
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

    // --- Conversion Elements ---
    const convertIdColumnGroup = document.getElementById('convertIdColumnGroup');
    const convertIdColumn = document.getElementById('convertIdColumn');
    const convertTemplateExportGroup = document.getElementById('convertTemplateExportGroup');
    const convertLanguageGroup = document.getElementById('convertLanguageGroup');
    const convertAliasGroup = document.getElementById('convertAliasGroup');
    const convertSessionGroup = document.getElementById('convertSessionGroup');
    const templateResultsContainer = document.getElementById('templateResultsContainer');

    // --- Session Picker: populate from declared sessions ---
    const convertSessionSelect = document.getElementById('convertSessionSelect');
    const convertSessionCustom = document.getElementById('convertSessionCustom');
    const biometricsSessionSelect = document.getElementById('biometricsSessionSelect');
    const biometricsSessionCustom = document.getElementById('biometricsSessionCustom');

    function populateSessionPickers() {
        fetch('/api/projects/sessions/declared')
            .then(r => r.json())
            .then(data => {
                const sessions = data.sessions || [];
                [convertSessionSelect, biometricsSessionSelect].forEach(sel => {
                    if (!sel) return;
                    // Clear existing options except the first placeholder
                    while (sel.options.length > 1) sel.remove(1);
                    sessions.forEach(s => {
                        const opt = document.createElement('option');
                        // Strip ses- prefix for display value (converter adds it back)
                        opt.value = s.id.replace(/^ses-/, '');
                        opt.textContent = s.label !== s.id ? `${s.id} — ${s.label}` : s.id;
                        sel.appendChild(opt);
                    });
                });
            })
            .catch(() => {});
    }

    function populateSurveySessionPickerFromDetected(detectedSessions) {
        if (!convertSessionSelect || !Array.isArray(detectedSessions) || detectedSessions.length === 0) {
            return false;
        }

        while (convertSessionSelect.options.length > 1) {
            convertSessionSelect.remove(1);
        }

        const allOpt = document.createElement('option');
        allOpt.value = 'all';
        allOpt.textContent = '✓ All sessions';
        convertSessionSelect.appendChild(allOpt);

        detectedSessions.forEach((ses) => {
            const opt = document.createElement('option');
            opt.value = ses;
            opt.textContent = ses;
            convertSessionSelect.appendChild(opt);
        });

        if (!getSurveySessionValue()) {
            convertSessionSelect.value = 'all';
        }
        if (convertSessionCustom) {
            convertSessionCustom.value = '';
        }

        return true;
    }

    // Resolve the effective session value: select wins if set, otherwise custom input
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

    // Clear custom input when a declared session is selected
    if (convertSessionSelect) {
        convertSessionSelect.addEventListener('change', function() {
            if (this.value && convertSessionCustom) convertSessionCustom.value = '';
        });
    }
    if (convertSessionCustom) {
        convertSessionCustom.addEventListener('input', function() {
            if (this.value && convertSessionSelect) convertSessionSelect.value = '';
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

    // Register conversion result in project.json
    function registerSessionInProject(sessionId, tasks, modality, sourceFile, converter) {
        if (!sessionId || !tasks || !tasks.length) return;
        fetch('/api/projects/sessions/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: sessionId,
                tasks: tasks,
                modality: modality,
                source_file: sourceFile || '',
                converter: converter || 'manual',
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                console.log(`Registered in project.json: ${data.session_id} → ${data.registered_tasks.join(', ')}`);
                // Refresh session pickers to reflect the new registration
                populateSessionPickers();
            }
        })
        .catch(() => {});
    }

    // Populate session pickers on load
    populateSessionPickers();

    // Converter is now data-conversion only
    function getConvertMode() {
        return 'data';
    }

    // Keep conversion UI in data mode
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

    // Detect columns from file for ID column selector
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
    }

    async function detectFileColumns(file) {
        const filename = file.name.toLowerCase();
        const idColumnSelect = document.getElementById('convertIdColumn');
        const idColumnStatus = document.getElementById('idColumnStatus');
        const idColumnHelp = document.getElementById('idColumnHelp');
        if (!idColumnSelect) return;

        // Reset state
        resetDetectedColumnsState();

        // For .lss files, no columns to detect (structure only)
        if (filename.endsWith('.lss')) {
            if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-muted">(structure only)</span>';
            if (idColumnHelp) idColumnHelp.innerHTML = '<i class="fas fa-info-circle me-1"></i>.lss files have no response data';
            return;
        }

        // Show loading status
        if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-info"><i class="fas fa-spinner fa-spin me-1"></i>Loading...</span>';

        // For .lsa and other files, try to detect columns
        if (filename.endsWith('.lsa') || filename.endsWith('.xlsx') || filename.endsWith('.csv') || filename.endsWith('.tsv')) {
            try {
                const formData = new FormData();
                formData.append('file', file);

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
                        // Add detected columns
                        data.columns.forEach(col => {
                            const opt = document.createElement('option');
                            opt.value = col;
                            opt.textContent = col;
                            // Mark only the suggested column with star
                            if (data.suggested_id_column && col === data.suggested_id_column) {
                                opt.textContent += ' \u2605';
                            }
                            idColumnSelect.appendChild(opt);
                        });

                        if (data.is_prism_data && data.suggested_id_column) {
                            // PRISM data: auto-select suggested column, show green indicator
                            idColumnSelect.value = data.suggested_id_column;
                            if (idColumnStatus) {
                                idColumnStatus.innerHTML = `<span class="text-success"><i class="fas fa-check me-1"></i>PRISM data (${data.columns.length} columns)</span>`;
                            }
                            if (idColumnHelp) {
                                idColumnHelp.innerHTML = `<i class="fas fa-check-circle me-1 text-success"></i>PRISM ID column detected: <strong>${data.suggested_id_column}</strong>`;
                            }
                        } else if (!data.is_prism_data) {
                            // Non-PRISM data: require manual selection
                            idColumnSelect.querySelector('option[value="auto"]').textContent = '-- Select ID column --';
                            idColumnSelect.value = 'auto';
                            if (idColumnStatus) {
                                idColumnStatus.innerHTML = `<span class="text-warning"><i class="fas fa-exclamation-triangle me-1"></i>${data.columns.length} columns</span>`;
                            }
                            if (idColumnHelp) {
                                idColumnHelp.innerHTML = '<i class="fas fa-exclamation-triangle me-1 text-warning"></i>No PRISM ID column found. Please select the participant ID column manually.';
                            }
                        } else {
                            // PRISM data but no suggested column (shouldn't normally happen)
                            if (idColumnStatus) {
                                idColumnStatus.innerHTML = `<span class="text-success"><i class="fas fa-check me-1"></i>${data.columns.length} columns</span>`;
                            }
                            if (idColumnHelp) {
                                idColumnHelp.innerHTML = data.suggested_id_column
                                    ? `<i class="fas fa-lightbulb me-1 text-warning"></i>Suggested: <strong>${data.suggested_id_column}</strong>`
                                    : '<i class="fas fa-exclamation-triangle me-1 text-warning"></i>No common ID column found. Please select manually.';
                            }
                            if (data.suggested_id_column) {
                                idColumnSelect.value = data.suggested_id_column;
                            }
                        }
                    } else {
                        if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-warning">No columns found</span>';
                    }
                } else {
                    try {
                        const err = await response.json();
                        console.error('Server returned error:', response.status, err);
                        if (idColumnStatus) idColumnStatus.innerHTML = `<span class="text-danger">${err.error || 'Error'}</span>`;
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
        const hasFile = convertExcelFile.files && convertExcelFile.files.length === 1;

        convertBtn.disabled = !hasFile;
        
        if (previewBtn) {
            previewBtn.disabled = !hasFile;
            previewBtn.style.display = '';
            convertBtn.parentElement.classList.remove('col-12');
            convertBtn.parentElement.classList.add('col-md-6');
        }

        if (convertBtn) {
            convertBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Convert';
            convertBtn.classList.remove('btn-success');
            convertBtn.classList.add('btn-warning');
        }

        clearConvertExcelFileBtn?.classList.toggle('d-none', !hasFile);
    }

    convertExcelFile.addEventListener('change', async function() {
        const file = this.files?.[0];
        if (file) {
            const filename = file.name.toLowerCase();

            if (filename.endsWith('.lss')) {
                convertInfo.innerHTML = '<i class="fas fa-info-circle me-1"></i>.lss files contain structure only (no response data). Use <a href="/template-editor" class="alert-link">Template Editor</a> to generate templates.';
                convertInfo.classList.remove('d-none');
            } else {
                convertInfo.classList.add('d-none');
            }

            // Detect columns for ID selection
            await detectFileColumns(file);
        } else {
            convertInfo.classList.add('d-none');
            resetDetectedColumnsState();
            populateSessionPickers();
        }
        updateConvertBtn();
    });

    clearConvertExcelFileBtn?.addEventListener('click', function() {
        convertExcelFile.value = '';
        convertExcelFile.dispatchEvent(new Event('change', { bubbles: true }));
        if (sourcedataFileSelect) {
            sourcedataFileSelect.value = '';
        }
        convertError.classList.add('d-none');
        convertError.textContent = '';
    });

    // Clear error styling when ID column is changed
    const idColSelect = document.getElementById('convertIdColumn');
    if (idColSelect) {
        idColSelect.addEventListener('change', function() {
            this.classList.remove('border-danger');
            convertError.classList.add('d-none');
        });
    }

    // Initialize mode on page load
    handleModeSwitch();
    updateConvertBtn();

    // --- Sourcedata quick-select ---
    const sourcedataQuickSelect = document.getElementById('sourcedataQuickSelect');
    const sourcedataFileSelect = document.getElementById('sourcedataFileSelect');

    if (sourcedataQuickSelect && sourcedataFileSelect) {
        // Fetch sourcedata files on page load
        fetch('/api/projects/sourcedata-files')
            .then(r => r.json())
            .then(data => {
                if (data.sourcedata_exists && data.files && data.files.length > 0) {
                    sourcedataQuickSelect.classList.remove('d-none');
                    data.files.forEach(f => {
                        const opt = document.createElement('option');
                        opt.value = f.name;
                        const sizeKB = (f.size / 1024).toFixed(1);
                        opt.textContent = `${f.name} (${sizeKB} KB)`;
                        sourcedataFileSelect.appendChild(opt);
                    });
                }
            })
            .catch(() => {}); // Silently ignore if no project

        // When a sourcedata file is selected, load it into the file input
        sourcedataFileSelect.addEventListener('change', async function() {
            const filename = this.value;
            if (!filename) return;

            try {
                const resp = await fetch(`/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}`);
                if (!resp.ok) throw new Error('Failed to load file');
                const blob = await resp.blob();
                const file = new File([blob], filename, { type: blob.type });
                const dt = new DataTransfer();
                dt.items.add(file);
                convertExcelFile.files = dt.files;
                // Trigger the change event so column detection runs
                convertExcelFile.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (err) {
                console.error('Failed to load sourcedata file:', err);
                convertError.textContent = `Failed to load ${filename} from sourcedata.`;
                convertError.classList.remove('d-none');
            }
        });
    }

    // Terminal log elements
    const conversionLogContainer = document.getElementById('conversionLogContainer');
    const conversionLog = document.getElementById('conversionLog');
    const conversionLogBody = document.getElementById('conversionLogBody');
    const toggleLogBtn = document.getElementById('toggleLogBtn');
    const validationResultsContainer = document.getElementById('validationResultsContainer');
    const validationResultsCard = document.getElementById('validationResultsCard');
    const validationResultsHeader = document.getElementById('validationResultsHeader');
    const validationBadge = document.getElementById('validationBadge');
    const validationSummary = document.getElementById('validationSummary');
    const validationDetails = document.getElementById('validationDetails');
    const downloadSection = document.getElementById('downloadSection');
    const downloadWarningSection = document.getElementById('downloadWarningSection');
    const downloadZipBtn = document.getElementById('downloadZipBtn');
    const downloadZipWarningBtn = document.getElementById('downloadZipWarningBtn');
    const conversionSummaryContainer = document.getElementById('conversionSummaryContainer');
    const conversionSummaryBody = document.getElementById('conversionSummaryBody');
    const toggleSummaryBtn = document.getElementById('toggleSummaryBtn');

    // Biometrics elements
    const biometricsLogContainer = document.getElementById('biometricsLogContainer');
    const biometricsLog = document.getElementById('biometricsLog');
    const biometricsLogBody = document.getElementById('biometricsLogBody');
    const toggleBiometricsLogBtn = document.getElementById('toggleBiometricsLogBtn');
    const biometricsValidationResultsContainer = document.getElementById('biometricsValidationResultsContainer');
    const biometricsValidationResultsCard = document.getElementById('biometricsValidationResultsCard');
    const biometricsValidationResultsHeader = document.getElementById('biometricsValidationResultsHeader');
    const biometricsValidationBadge = document.getElementById('biometricsValidationBadge');
    const biometricsValidationSummary = document.getElementById('biometricsValidationSummary');
    const biometricsValidationDetails = document.getElementById('biometricsValidationDetails');
    const biometricsDownloadSection = document.getElementById('biometricsDownloadSection');
    const biometricsDownloadWarningSection = document.getElementById('biometricsDownloadWarningSection');
    const biometricsDownloadZipBtn = document.getElementById('biometricsDownloadZipBtn');
    const biometricsDownloadZipWarningBtn = document.getElementById('biometricsDownloadZipWarningBtn');
    const biometricsDetectedContainer = document.getElementById('biometricsDetectedContainer');
    const biometricsDetectedList = document.getElementById('biometricsDetectedList');
    const biometricsConfirmBtn = document.getElementById('biometricsConfirmBtn');
    const biometricsSelectAll = document.getElementById('biometricsSelectAll');

    let currentZipBlob = null;

    // Toggle log visibility
    if (toggleLogBtn) {
        toggleLogBtn.addEventListener('click', function() {
            conversionLogBody.classList.toggle('d-none');
            const icon = toggleLogBtn.querySelector('i');
            if (conversionLogBody.classList.contains('d-none')) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            } else {
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-down');
            }
        });
    }

    if (toggleBiometricsLogBtn) {
        toggleBiometricsLogBtn.addEventListener('click', function() {
            biometricsLogBody.classList.toggle('d-none');
            const icon = toggleBiometricsLogBtn.querySelector('i');
            if (biometricsLogBody.classList.contains('d-none')) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            } else {
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-down');
            }
        });
    }

    function appendLog(message, type = 'info', logElement = null) {
        const colors = {
            'info': '#17a2b8',
            'success': '#28a745',
            'warning': '#ffc107',
            'error': '#dc3545',
            'step': '#6c757d'
        };
        const targetLog = logElement || conversionLog;
        if (!targetLog) return;

        const timestamp = new Date().toLocaleTimeString();
        const color = colors[type] || colors.info;
        targetLog.innerHTML += `<span style="color: ${color}">[${timestamp}] ${message}</span>\n`;
        targetLog.scrollTop = targetLog.scrollHeight;
    }

    function resetConversionUI() {
        conversionLogContainer.classList.add('d-none');
        validationResultsContainer.classList.add('d-none');
        if (conversionSummaryContainer) conversionSummaryContainer.classList.add('d-none');
        if (conversionSummaryBody) conversionSummaryBody.innerHTML = '';
        downloadSection.classList.add('d-none');
        downloadWarningSection.classList.add('d-none');
        conversionLog.innerHTML = '';
        validationSummary.innerHTML = '';
        validationDetails.innerHTML = '';
        currentZipBlob = null;
    }

    function displayConversionSummary(summary) {
        if (!conversionSummaryContainer || !conversionSummaryBody || !summary) return;

        let html = '';

        // Matched Templates section
        const matches = summary.template_matches;
        if (matches && Object.keys(matches).length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-puzzle-piece me-1"></i>Matched Templates</h6>`;
            html += `<table class="table table-sm table-bordered mb-3"><thead><tr><th>Survey Group</th><th>Template</th><th>Confidence</th></tr></thead><tbody>`;
            for (const [group, info] of Object.entries(matches)) {
                if (!info) continue;
                const tmpl = info.template_key || info.template || info.matched_template || 'None';
                const conf = info.confidence || info.match_confidence || 'unknown';
                let badgeClass = 'bg-secondary';
                if (conf === 'exact' || conf === 'high') badgeClass = 'bg-success';
                else if (conf === 'medium') badgeClass = 'bg-warning text-dark';
                else if (conf === 'low') badgeClass = 'bg-danger';
                html += `<tr><td>${group}</td><td><code>${tmpl}</code></td><td><span class="badge ${badgeClass}">${conf}</span></td></tr>`;
            }
            html += `</tbody></table>`;
        }

        // Tool-Specific Columns section
        const toolCols = summary.tool_columns;
        if (toolCols && toolCols.length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-wrench me-1"></i>Tool-Specific Columns <span class="badge bg-secondary">${toolCols.length}</span></h6>`;
            html += `<div class="mb-3"><details><summary class="text-muted small" style="cursor:pointer;">LimeSurvey system columns (click to expand)</summary>`;
            html += `<div class="mt-1"><code>${toolCols.join('</code>, <code>')}</code></div></details></div>`;
        }

        // Unmatched Columns section
        const unknownCols = summary.unknown_columns;
        if (unknownCols && unknownCols.length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-question-circle me-1 text-warning"></i>Unmatched Columns <span class="badge bg-warning text-dark">${unknownCols.length}</span></h6>`;
            html += `<div class="mb-1"><code>${unknownCols.join('</code>, <code>')}</code></div>`;
            html += `<small class="text-muted">These columns were not assigned to any template.</small>`;
        }

        if (html) {
            conversionSummaryBody.innerHTML = html;
            conversionSummaryContainer.classList.remove('d-none');

            // Wire toggle button
            if (toggleSummaryBtn) {
                toggleSummaryBtn.onclick = function() {
                    const body = conversionSummaryBody;
                    const icon = toggleSummaryBtn.querySelector('i');
                    if (body.style.display === 'none') {
                        body.style.display = '';
                        icon.className = 'fas fa-chevron-down';
                    } else {
                        body.style.display = 'none';
                        icon.className = 'fas fa-chevron-right';
                    }
                };
            }
        }
    }

    // --- Unmatched Groups Resolution UI ---

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
                btn.classList.replace('btn-outline-primary', 'btn-outline-danger');
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
        const getEl = (id) => document.getElementById(prefix ? prefix + id.charAt(0).toUpperCase() + id.slice(1) : id);
        
        const container = getEl('validationResultsContainer');
        const card = getEl('validationResultsCard');
        const header = getEl('validationResultsHeader');
        const badge = getEl('validationBadge');
        const summaryEl = getEl('validationSummary');
        const detailsEl = getEl('validationDetails');
        const dlSection = getEl('downloadSection');
        const dlWarningSection = getEl('downloadWarningSection');

        if (!container) return;
        container.classList.remove('d-none');
        
        const errors = validation.errors || [];
        const warnings = validation.warnings || [];
        const isValid = errors.length === 0;
        
        // Update card styling based on result
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
        
        // Summary
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
        
        // Details
        let detailsHtml = '';
        
        if (validation.formatted) {
            const f = validation.formatted;
            
            if (f.errors && f.errors.length > 0) {
                detailsHtml += '<h6 class="text-danger mt-3"><i class="fas fa-times-circle me-1"></i>Errors</h6>';
                f.errors.forEach(group => {
                    detailsHtml += `
                        <div class="validation-group mb-3 p-3 border rounded bg-light shadow-sm">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="fw-bold text-danger">
                                    <span class="badge bg-danger me-2">${group.code}</span>
                                    ${escapeHtml(group.message)}
                                </div>
                                ${group.documentation_url ? `
                                    <a href="${group.documentation_url}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2" style="font-size: 0.75rem;">
                                        <i class="fas fa-book me-1"></i>Docs
                                    </a>
                                ` : ''}
                            </div>
                            
                            ${group.fix_hint ? `
                                <div class="alert alert-info py-2 px-3 mb-2 smaller">
                                    <i class="fas fa-lightbulb me-2 text-warning"></i>
                                    <strong>Fix Hint:</strong> ${escapeHtml(group.fix_hint)}
                                </div>
                            ` : ''}

                            <ul class="list-unstyled ms-2 mb-0 smaller">
                                ${(group.files || []).map(file => `
                                    <li class="mb-1 border-bottom pb-1 last-child-no-border">
                                        <div class="d-flex justify-content-between">
                                            <code class="text-dark fw-bold">${escapeHtml(file.file || 'unknown')}</code>
                                            ${file.line ? `<span class="badge bg-secondary">Line ${file.line}</span>` : ''}
                                        </div>
                                        ${file.message && file.message !== group.message ? `<div class="text-muted mt-1">${escapeHtml(file.message)}</div>` : ''}
                                        ${file.evidence ? `<div class="text-muted italic ms-2 mt-1 p-1 bg-white border rounded" style="font-size: 0.85em; font-family: monospace;">${escapeHtml(file.evidence)}</div>` : ''}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    `;
                });
            }
            
            if (f.warnings && f.warnings.length > 0) {
                detailsHtml += '<h6 class="text-warning mt-3"><i class="fas fa-exclamation-triangle me-1"></i>Warnings</h6>';
                f.warnings.forEach(group => {
                    detailsHtml += `
                        <div class="validation-group mb-3 p-3 border rounded bg-light shadow-sm">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="fw-bold text-warning">
                                    <span class="badge bg-warning text-dark me-2">${group.code}</span>
                                    ${escapeHtml(group.message)}
                                </div>
                                ${group.documentation_url ? `
                                    <a href="${group.documentation_url}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2" style="font-size: 0.75rem;">
                                        <i class="fas fa-book me-1"></i>Docs
                                    </a>
                                ` : ''}
                            </div>

                            ${group.fix_hint ? `
                                <div class="alert alert-info py-2 px-3 mb-2 smaller">
                                    <i class="fas fa-lightbulb me-2 text-warning"></i>
                                    <strong>Fix Hint:</strong> ${escapeHtml(group.fix_hint)}
                                </div>
                            ` : ''}

                            <ul class="list-unstyled ms-2 mb-0 smaller">
                                ${(group.files || []).map(file => `
                                    <li class="mb-1 border-bottom pb-1 last-child-no-border">
                                        <div class="d-flex justify-content-between">
                                            <code class="text-dark fw-bold">${escapeHtml(file.file || 'unknown')}</code>
                                            ${file.line ? `<span class="badge bg-secondary">Line ${file.line}</span>` : ''}
                                        </div>
                                        ${file.message && file.message !== group.message ? `<div class="text-muted mt-1">${escapeHtml(file.message)}</div>` : ''}
                                        ${file.evidence ? `<div class="text-muted italic ms-2 mt-1 p-1 bg-white border rounded" style="font-size: 0.85em; font-family: monospace;">${escapeHtml(file.evidence)}</div>` : ''}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    `;
                });
            }
        } else {
            // Fallback to old list
            if (errors.length > 0) {
                detailsHtml += '<h6 class="text-danger mt-3"><i class="fas fa-times-circle me-1"></i>Errors</h6><ul class="list-unstyled">';
                errors.forEach(e => {
                    detailsHtml += `<li class="text-danger small"><i class="fas fa-times me-1"></i>${escapeHtml(e)}</li>`;
                });
                detailsHtml += '</ul>';
            }
            if (warnings.length > 0) {
                detailsHtml += '<h6 class="text-warning mt-3"><i class="fas fa-exclamation-triangle me-1"></i>Warnings</h6><ul class="list-unstyled">';
                warnings.forEach(w => {
                    detailsHtml += `<li class="text-warning small"><i class="fas fa-exclamation me-1"></i>${escapeHtml(w)}</li>`;
                });
                detailsHtml += '</ul>';
            }
        }
        
        detailsEl.innerHTML = detailsHtml;
        
        // Show appropriate download button
        if (isValid && warnings.length === 0) {
            dlSection.classList.remove('d-none');
            dlWarningSection.classList.add('d-none');
        } else if (isValid) {
            dlSection.classList.add('d-none');
            dlWarningSection.classList.remove('d-none');
        } else {
            dlSection.classList.add('d-none');
            dlWarningSection.classList.add('d-none');
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function downloadCurrentZip() {
        if (!currentZipBlob) return;
        const url = window.URL.createObjectURL(currentZipBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prism_survey_dataset.zip';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    }

    if (downloadZipBtn) {
        downloadZipBtn.addEventListener('click', downloadCurrentZip);
    }
    if (downloadZipWarningBtn) {
        downloadZipWarningBtn.addEventListener('click', downloadCurrentZip);
    }

    // Store template results for download
    let currentTemplateData = null;

    // Handle template generation (structure only, no data)
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
                displayTemplateSingle(data);
            } else if (data.mode === 'groups') {
                displayTemplateGroups(data);
            } else if (data.mode === 'questions') {
                displayTemplateQuestions(data);
            }

            // Show participant metadata section for marking fields
            displayParticipantMetadataSection(data);

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

    function displayTemplateSingle(data) {
        const container = document.getElementById('templateResultSingle');
        if (!container) return;

        container.classList.remove('d-none');
        document.getElementById('templateQuestionCount').textContent = `${data.question_count} questions`;

        // Show template match info if available
        const matchContainer = document.getElementById('templateSingleMatch');
        if (matchContainer) matchContainer.remove();
        const m = data.template_match;
        if (m) {
            const badgeClass = {exact: 'bg-success', high: 'bg-success', medium: 'bg-warning text-dark', low: 'bg-secondary'}[m.confidence] || 'bg-secondary';
            const icon = {exact: 'fa-check-circle', high: 'fa-check', medium: 'fa-question-circle', low: 'fa-minus-circle'}[m.confidence] || 'fa-circle';
            const actionLabel = {use_library: 'Use library template instead', review: 'Review differences', create_new: 'Create new template'}[m.suggested_action] || '';
            const details = [];
            if (m.overlap_count !== undefined) details.push(`${m.overlap_count}/${m.template_items} items match`);
            if (m.levels_match === true) details.push('levels verified');
            const matchDiv = document.createElement('div');
            matchDiv.id = 'templateSingleMatch';
            matchDiv.className = 'alert alert-info py-2 mt-2 mb-0';
            const srcLabel = m.source === 'project' ? 'project template' : 'library template';
            const srcIcon = m.source === 'project' ? 'fa-folder' : 'fa-globe';
            matchDiv.innerHTML = `<i class="fas ${icon} me-1"></i><span class="badge ${badgeClass} me-2">${m.confidence}</span>Matches ${srcLabel}: <strong>${m.template_key}</strong> <span class="badge bg-light text-dark border ms-1"><i class="fas ${srcIcon} me-1"></i>${m.source === 'project' ? 'project' : 'library'}</span> (${details.join(', ')})${actionLabel ? ` &mdash; <em>${actionLabel}</em>` : ''}`;
            container.querySelector('.alert')?.after(matchDiv);
        } else if (m === null) {
            const matchDiv = document.createElement('div');
            matchDiv.id = 'templateSingleMatch';
            matchDiv.className = 'alert alert-light py-2 mt-2 mb-0 border';
            matchDiv.innerHTML = '<i class="fas fa-plus-circle me-1"></i>No matching library template found &mdash; this will be a new template.';
            container.querySelector('.alert')?.after(matchDiv);
        }

        // Setup preview button
        const previewBtn = document.getElementById('templatePreviewBtn');
        const previewDiv = document.getElementById('templatePreview');
        const previewContent = document.getElementById('templatePreviewContent');

        if (previewBtn && previewDiv && previewContent) {
            previewBtn.onclick = () => {
                previewDiv.classList.toggle('d-none');
                previewContent.textContent = JSON.stringify(data.prism_json, null, 2);
            };
        }

        // Setup download button
        const downloadBtn = document.getElementById('templateDownloadBtn');
        if (downloadBtn) {
            downloadBtn.onclick = () => {
                const blob = new Blob([JSON.stringify(data.prism_json, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.suggested_filename || 'survey-template.json';
                a.click();
                URL.revokeObjectURL(url);
            };
        }
    }

    function displayTemplateGroups(data) {
        const container = document.getElementById('templateResultGroups');
        if (!container) return;

        container.classList.remove('d-none');
        document.getElementById('templateGroupCount').textContent = `${data.questionnaire_count} groups`;
        document.getElementById('templateTotalQuestions').textContent = `${data.total_questions} questions`;

        const listEl = document.getElementById('templateGroupList');
        if (listEl) {
            listEl.innerHTML = '';
            for (const [name, info] of Object.entries(data.questionnaires || {})) {
                const card = document.createElement('div');
                card.className = 'col-md-4';

                // Build template match badge if available
                let matchHtml = '';
                const m = info.template_match;
                if (m) {
                    const badgeClass = {
                        exact: 'bg-success',
                        high: 'bg-success',
                        medium: 'bg-warning text-dark',
                        low: 'bg-secondary'
                    }[m.confidence] || 'bg-secondary';
                    const icon = {
                        exact: 'fa-check-circle',
                        high: 'fa-check',
                        medium: 'fa-question-circle',
                        low: 'fa-minus-circle'
                    }[m.confidence] || 'fa-circle';
                    const details = [];
                    if (m.overlap_count !== undefined) details.push(`${m.overlap_count}/${m.template_items} items`);
                    if (m.levels_match === true) details.push('levels verified');
                    if (m.runs_detected > 1) details.push(`${m.runs_detected} runs`);
                    const detailStr = details.length ? details.join(', ') : '';
                    const diffParts = [];
                    if (m.only_in_import && m.only_in_import.length) diffParts.push(`+${m.only_in_import.length} extra`);
                    if (m.only_in_library && m.only_in_library.length) diffParts.push(`${m.only_in_library.length} missing`);
                    const diffHtml = diffParts.length
                        ? `<small class="d-block text-muted" style="font-size:0.7rem">${diffParts.join(', ')}</small>`
                        : '';
                    // Show "Use Library" button for exact/high matches (but not for participants matches)
                    const sourceLabel = m.source === 'project' ? 'project' : 'library';
                    const sourceIcon = m.source === 'project' ? 'fa-folder' : 'fa-globe';
                    // Don't show "Use library version" for participants matches - there's no participants template in the library
                    const useLibBtn = (m.suggested_action === 'use_library' && !m.is_participants)
                        ? `<button class="btn btn-sm btn-outline-primary use-library-btn mt-1" data-name="${name}" data-template-key="${m.template_key}" data-is-participants="${m.is_participants || false}"><i class="fas fa-book me-1"></i>Use ${sourceLabel} version</button>`
                        : '';
                    matchHtml = `
                        <div class="mt-1 pt-1 border-top">
                            <span class="badge ${badgeClass}" title="${detailStr}">
                                <i class="fas ${icon} me-1"></i>${m.confidence} match: ${m.template_key}
                            </span>
                            <span class="badge bg-light text-dark border ms-1" title="Matched from ${sourceLabel}">
                                <i class="fas ${sourceIcon} me-1"></i>${sourceLabel}
                            </span>
                            ${diffHtml}
                            ${useLibBtn}
                        </div>
                    `;
                } else if (m === null) {
                    matchHtml = `
                        <div class="mt-1 pt-1 border-top">
                            <span class="badge bg-light text-dark border">
                                <i class="fas fa-plus-circle me-1"></i>No library match
                            </span>
                        </div>
                    `;
                }

                card.innerHTML = `
                    <div class="card h-100">
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${name}</strong>
                                    <small class="d-block text-muted">${info.question_count} questions</small>
                                </div>
                                <button class="btn btn-sm btn-outline-success download-template-btn" data-name="${name}">
                                    <i class="fas fa-download"></i>
                                </button>
                            </div>
                            ${matchHtml}
                        </div>
                    </div>
                `;
                listEl.appendChild(card);
            }

            // "Use Library" button handlers - swap generated template with library version
            listEl.querySelectorAll('.use-library-btn').forEach(btn => {
                btn.onclick = async () => {
                    const groupName = btn.dataset.name;
                    const templateKey = btn.dataset.templateKey;
                    btn.disabled = true;
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Loading...';
                    try {
                        const resp = await fetch(`/api/library-template/${encodeURIComponent(templateKey)}`);
                        const result = await resp.json();
                        if (result.success && result.prism_json) {
                            // Swap the template in the data object
                            data.questionnaires[groupName].prism_json = result.prism_json;
                            data.questionnaires[groupName].suggested_filename = result.filename;
                            // Update the card visually
                            const card = btn.closest('.card');
                            const matchDiv = btn.closest('.border-top');
                            matchDiv.innerHTML = `
                                <span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>Using library: ${templateKey}</span>
                                <small class="d-block text-muted mt-1">${result.filename}</small>
                            `;
                        } else {
                            btn.disabled = false;
                            btn.innerHTML = '<i class="fas fa-book me-1"></i>Use library version';
                            alert('Error: ' + (result.error || 'Failed to load library template'));
                        }
                    } catch (e) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-book me-1"></i>Use library version';
                        alert('Error loading template: ' + e.message);
                    }
                };
            });

            // Add download handlers
            listEl.querySelectorAll('.download-template-btn').forEach(btn => {
                btn.onclick = () => {
                    const name = btn.dataset.name;
                    const info = data.questionnaires[name];
                    if (info) {
                        const blob = new Blob([JSON.stringify(info.prism_json, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = info.suggested_filename || `survey-${name}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                    }
                };
            });
        }

        // Download all as ZIP (deduplicate runs of the same template)
        const downloadAllBtn = document.getElementById('templateDownloadAllBtn');
        if (downloadAllBtn) {
            downloadAllBtn.onclick = async () => {
                const JSZip = window.JSZip;
                if (!JSZip) {
                    alert('JSZip not loaded');
                    return;
                }
                const zip = new JSZip();
                const addedKeys = new Set();
                for (const [name, info] of Object.entries(data.questionnaires || {})) {
                    const m = info.template_match;
                    // Skip participants templates
                    if (m && m.is_participants) continue;
                    // Deduplicate runs: use library filename, skip if already added
                    const filename = (m && m.template_path) ? m.template_path : (info.suggested_filename || `survey-${name}.json`);
                    const dedupeKey = (m && m.template_key) ? m.template_key : filename;
                    if (addedKeys.has(dedupeKey)) continue;
                    addedKeys.add(dedupeKey);
                    zip.file(filename, JSON.stringify(info.prism_json, null, 2));
                }
                const blob = await zip.generateAsync({ type: 'blob' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'survey-templates.zip';
                a.click();
                URL.revokeObjectURL(url);
            };
        }

        // Save to project button
        setupTemplateSaveToProject(data, 'groups');
    }

    function displayTemplateQuestions(data) {
        const container = document.getElementById('templateResultQuestions');
        if (!container) return;

        container.classList.remove('d-none');
        document.getElementById('templateIndividualCount').textContent = `${data.question_count} templates`;

        const listEl = document.getElementById('templateQuestionsList');
        if (listEl) {
            listEl.innerHTML = '';
            for (const [groupName, groupInfo] of Object.entries(data.by_group || {})) {
                const groupDiv = document.createElement('div');
                groupDiv.className = 'col-12 mb-2';
                groupDiv.innerHTML = `<h6 class="text-muted">${groupName}</h6>`;
                listEl.appendChild(groupDiv);

                for (const q of groupInfo.questions || []) {
                    const qData = data.questions[q.code];
                    if (!qData) continue;

                    const card = document.createElement('div');
                    card.className = 'col-md-3';
                    card.innerHTML = `
                        <div class="card h-100">
                            <div class="card-body py-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <strong>${q.code}</strong>
                                        <small class="d-block text-muted">${q.type} (${q.item_count} items)</small>
                                    </div>
                                    <button class="btn btn-sm btn-outline-success download-q-btn" data-code="${q.code}">
                                        <i class="fas fa-download"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    listEl.appendChild(card);
                }
            }

            // Add download handlers
            listEl.querySelectorAll('.download-q-btn').forEach(btn => {
                btn.onclick = () => {
                    const code = btn.dataset.code;
                    const qData = data.questions[code];
                    if (qData && qData.prism_json) {
                        const blob = new Blob([JSON.stringify(qData.prism_json, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = qData.suggested_filename || `survey-${code}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                    }
                };
            });
        }

        // Download all as ZIP
        const downloadBtn = document.getElementById('templateDownloadQuestionsBtn');
        if (downloadBtn) {
            downloadBtn.onclick = async () => {
                const JSZip = window.JSZip;
                if (!JSZip) {
                    alert('JSZip not loaded');
                    return;
                }
                const zip = new JSZip();
                for (const [code, qData] of Object.entries(data.questions || {})) {
                    if (qData.prism_json) {
                        zip.file(qData.suggested_filename || `survey-${code}.json`, JSON.stringify(qData.prism_json, null, 2));
                    }
                }
                const blob = await zip.generateAsync({ type: 'blob' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'survey-question-templates.zip';
                a.click();
                URL.revokeObjectURL(url);
            };
        }

        // Save to project button
        setupTemplateSaveToProject(data, 'questions');
    }

    function setupTemplateSaveToProject(data, mode) {
        const saveBtn = mode === 'groups'
            ? document.getElementById('templateSaveToProjectBtn')
            : document.getElementById('templateSaveQuestionsToProjectBtn');

        if (!saveBtn) return;

        saveBtn.onclick = async () => {
            const templates = [];
            const savedKeys = new Set();  // Deduplicate runs of same template

            if (mode === 'groups') {
                for (const [name, info] of Object.entries(data.questionnaires || {})) {
                    const m = info.template_match;

                    // Skip participants templates (handled separately)
                    if (m && m.is_participants) continue;

                    // Deduplicate: if multiple groups matched the same library
                    // template (e.g. run1/run2/run3 of BRS), save only once
                    // using the library filename
                    if (m && m.template_key) {
                        if (savedKeys.has(m.template_key)) continue;
                        savedKeys.add(m.template_key);
                        templates.push({
                            filename: m.template_path || info.suggested_filename || `survey-${name}.json`,
                            content: info.prism_json
                        });
                    } else {
                        templates.push({
                            filename: info.suggested_filename || `survey-${name}.json`,
                            content: info.prism_json
                        });
                    }
                }
            } else {
                for (const [code, qData] of Object.entries(data.questions || {})) {
                    if (qData.prism_json) {
                        templates.push({
                            filename: qData.suggested_filename || `survey-${code}.json`,
                            content: qData.prism_json
                        });
                    }
                }
            }

            if (templates.length === 0) {
                alert('No templates to save (all matched library templates or participants).');
                return;
            }

            try {
                const response = await fetch('/api/limesurvey-save-to-project', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ templates })
                });
                const result = await response.json();

                const successDiv = document.getElementById('templateSaveSuccess');
                const msgSpan = document.getElementById('templateSaveSuccessMessage');
                if (result.success) {
                    successDiv?.classList.remove('d-none');
                    const skipped = Object.keys(data.questionnaires || {}).length - templates.length;
                    let msg = `Saved ${result.saved_files?.length || templates.length} template(s) to ${result.library_path}`;
                    if (skipped > 0) msg += ` (${skipped} duplicate run(s) skipped)`;
                    msgSpan.textContent = msg;
                } else {
                    alert('Error: ' + (result.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Error saving: ' + e.message);
            }
        };
    }

    // ===== PARTICIPANT METADATA MARKING =====

    // Store selected participant fields
    let selectedParticipantFields = {};

    // BIDS standard field suggestions for auto-mapping
    const bidsFieldMappings = {
        // Common patterns -> BIDS field names
        'participant_id': ['token', 'id', 'participant', 'subject', 'subj', 'respondent'],
        'age': ['age', 'alter', 'years_old'],
        'sex': ['sex', 'gender', 'geschlecht', 'm_f', 'male_female'],
        'handedness': ['hand', 'handed', 'handedness', 'dominant_hand'],
        'education_years': ['education', 'school', 'study_years', 'ausbildung'],
        'native_language': ['language', 'native', 'mother_tongue', 'muttersprache']
    };

    // Display participant metadata section with extracted fields
    function displayParticipantMetadataSection(data) {
        const section = document.getElementById('participantMetadataSection');
        const fieldsList = document.getElementById('participantFieldsList');
        if (!section || !fieldsList) return;

        // Extract all question codes/fields from the template data
        const allFields = extractAllFields(data);

        if (allFields.length === 0) {
            section.classList.add('d-none');
            return;
        }

        section.classList.remove('d-none');
        selectedParticipantFields = {};

        // Render field checkboxes
        let html = '<div class="list-group list-group-flush">';
        for (const field of allFields) {
            const suggestedMapping = suggestBidsMapping(field.code);
            html += `
                <label class="list-group-item list-group-item-action py-2 d-flex align-items-center">
                    <input type="checkbox" class="form-check-input me-2 participant-field-checkbox"
                           data-code="${field.code}" data-description="${field.description || ''}"
                           data-type="${field.type || 'text'}">
                    <div class="flex-grow-1">
                        <code class="me-2">${field.code}</code>
                        <small class="text-muted">${field.description || field.type || ''}</small>
                        ${field.group ? `<span class="badge bg-light text-dark ms-2">${field.group}</span>` : ''}
                    </div>
                    ${suggestedMapping ? `
                        <select class="form-select form-select-sm bids-mapping-select" style="width: 140px;" data-code="${field.code}">
                            <option value="">Map to...</option>
                            <option value="${suggestedMapping}" selected>${suggestedMapping}</option>
                            <option value="participant_id">participant_id</option>
                            <option value="age">age</option>
                            <option value="sex">sex</option>
                            <option value="handedness">handedness</option>
                            <option value="custom">Custom name</option>
                        </select>
                    ` : `
                        <select class="form-select form-select-sm bids-mapping-select" style="width: 140px;" data-code="${field.code}">
                            <option value="">Map to...</option>
                            <option value="participant_id">participant_id</option>
                            <option value="age">age</option>
                            <option value="sex">sex</option>
                            <option value="handedness">handedness</option>
                            <option value="education_years">education_years</option>
                            <option value="custom">Custom name</option>
                        </select>
                    `}
                </label>
            `;
        }
        html += '</div>';
        fieldsList.innerHTML = html;

        // Add event listeners
        fieldsList.querySelectorAll('.participant-field-checkbox').forEach(cb => {
            cb.addEventListener('change', updateParticipantFieldSelection);
        });

        fieldsList.querySelectorAll('.bids-mapping-select').forEach(sel => {
            sel.addEventListener('change', function() {
                const code = this.dataset.code;
                const checkbox = fieldsList.querySelector(`.participant-field-checkbox[data-code="${code}"]`);
                if (this.value && checkbox && !checkbox.checked) {
                    checkbox.checked = true;
                    updateParticipantFieldSelection();
                }
            });
        });

        // Setup save/download button
        setupParticipantsSaveButton();
    }

    // Extract all fields from template data (works for all modes)
    function extractAllFields(data) {
        const fields = [];

        if (data.mode === 'combined' || data.mode === 'groups') {
            // Extract from prism_json Items
            const sources = data.mode === 'combined'
                ? [{ json: data.prism_json, group: null }]
                : Object.entries(data.questionnaires || {}).map(([name, info]) => ({ json: info.prism_json, group: name }));

            for (const source of sources) {
                const items = source.json?.Items || [];
                for (const item of items) {
                    if (item.SurveyItemID) {
                        fields.push({
                            code: item.SurveyItemID,
                            description: item.Prompt || item.Description || '',
                            type: item.ResponseType || 'text',
                            group: source.group
                        });
                    }
                }
            }
        } else if (data.mode === 'questions') {
            // Extract from by_group structure
            for (const [groupName, groupInfo] of Object.entries(data.by_group || {})) {
                for (const q of groupInfo.questions || []) {
                    fields.push({
                        code: q.code,
                        description: q.title || '',
                        type: q.type || 'text',
                        group: groupName
                    });
                }
            }
        }

        return fields;
    }

    // Suggest BIDS field mapping based on field code
    function suggestBidsMapping(code) {
        const lowerCode = code.toLowerCase();
        for (const [bidsField, patterns] of Object.entries(bidsFieldMappings)) {
            for (const pattern of patterns) {
                if (lowerCode.includes(pattern)) {
                    return bidsField;
                }
            }
        }
        return null;
    }

    // Update selection state and count
    function updateParticipantFieldSelection() {
        selectedParticipantFields = {};
        const checkboxes = document.querySelectorAll('.participant-field-checkbox:checked');

        checkboxes.forEach(cb => {
            const code = cb.dataset.code;
            const description = cb.dataset.description;
            const mappingSelect = document.querySelector(`.bids-mapping-select[data-code="${code}"]`);
            const bidsName = mappingSelect?.value || code;

            selectedParticipantFields[code] = {
                originalCode: code,
                bidsFieldName: bidsName || code,
                description: description
            };
        });

        // Update count
        const countEl = document.getElementById('selectedParticipantFieldsCount');
        if (countEl) {
            countEl.textContent = Object.keys(selectedParticipantFields).length;
        }

        // Enable/disable save button
        const saveBtn = document.getElementById('saveParticipantsJsonBtn') || document.getElementById('downloadParticipantsJsonBtn');
        if (saveBtn) {
            saveBtn.disabled = Object.keys(selectedParticipantFields).length === 0;
        }
    }

    // Build participants.json schema from selections
    function buildParticipantsJsonSchema() {
        const schema = {};

        for (const [code, info] of Object.entries(selectedParticipantFields)) {
            const fieldName = info.bidsFieldName || code;

            // Get description from original data
            schema[fieldName] = {
                Description: info.description || `Extracted from survey field: ${code}`
            };

            // Add standard properties for known BIDS fields
            if (fieldName === 'age') {
                schema[fieldName].Unit = 'years';
            } else if (fieldName === 'sex') {
                schema[fieldName].Levels = {
                    'M': 'Male',
                    'F': 'Female',
                    'O': 'Other'
                };
            } else if (fieldName === 'handedness') {
                schema[fieldName].Levels = {
                    'R': 'Right',
                    'L': 'Left',
                    'A': 'Ambidextrous'
                };
            }

            // Store source info for data conversion
            if (code !== fieldName) {
                schema[fieldName]._sourceField = code;
            }
        }

        return schema;
    }

    // Setup save/download button
    function setupParticipantsSaveButton() {
        const saveBtn = document.getElementById('saveParticipantsJsonBtn');
        const downloadBtn = document.getElementById('downloadParticipantsJsonBtn');
        const statusDiv = document.getElementById('participantsSaveStatus');

        if (saveBtn) {
            saveBtn.onclick = async () => {
                const schema = buildParticipantsJsonSchema();
                if (Object.keys(schema).length === 0) {
                    alert('No fields selected');
                    return;
                }

                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

                try {
                    // First get existing schema to merge
                    const existingRes = await fetch('/api/projects/participants');
                    const existingData = await existingRes.json();
                    const existingSchema = existingData.success ? (existingData.schema || {}) : {};

                    // Merge new fields into existing schema
                    const mergedSchema = { ...existingSchema, ...schema };

                    // Ensure participant_id is present
                    if (!mergedSchema.participant_id) {
                        mergedSchema.participant_id = { Description: 'Unique participant identifier' };
                    }

                    // Save merged schema
                    const response = await fetch('/api/projects/participants', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ schema: mergedSchema })
                    });
                    const result = await response.json();

                    if (result.success) {
                        statusDiv.innerHTML = `<span class="text-success"><i class="fas fa-check-circle me-1"></i>Saved ${Object.keys(schema).length} fields to participants.json!</span>`;
                    } else {
                        statusDiv.innerHTML = `<span class="text-danger"><i class="fas fa-exclamation-circle me-1"></i>${result.error}</span>`;
                    }
                } catch (e) {
                    statusDiv.innerHTML = `<span class="text-danger"><i class="fas fa-exclamation-circle me-1"></i>${e.message}</span>`;
                } finally {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>Save to participants.json';
                }
            };
        }

        if (downloadBtn) {
            downloadBtn.onclick = () => {
                const schema = buildParticipantsJsonSchema();
                if (Object.keys(schema).length === 0) {
                    alert('No fields selected');
                    return;
                }

                // Ensure participant_id is present
                if (!schema.participant_id) {
                    schema.participant_id = { Description: 'Unique participant identifier' };
                }

                const blob = new Blob([JSON.stringify(schema, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'participants.json';
                a.click();
                URL.revokeObjectURL(url);
            };
        }
    }

    convertBtn.addEventListener('click', async function() {
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');
        convertError.textContent = '';
        convertInfo.textContent = '';
        resetConversionUI();

        // Hide template results and participant metadata section
        if (templateResultsContainer) {
            templateResultsContainer.classList.add('d-none');
            document.getElementById('templateResultSingle')?.classList.add('d-none');
            document.getElementById('templateResultGroups')?.classList.add('d-none');
            document.getElementById('templateResultQuestions')?.classList.add('d-none');
            document.getElementById('participantMetadataSection')?.classList.add('d-none');
        }

        const file = convertExcelFile.files && convertExcelFile.files[0];
        if (!file) {
            return;
        }

        const filename = file.name.toLowerCase();
        const isLssFile = filename.endsWith('.lss');
        const isLimeSurveyFile = filename.endsWith('.lss') || filename.endsWith('.lsa');

        // DATA CONVERSION MODE — session is required
        const sessionVal = getSurveySessionValue();

        if (!sessionVal) {
            convertError.textContent = 'Please enter a session ID (e.g., 1, 2, 3).';
            convertError.classList.remove('d-none');
            (convertSessionCustom || convertSessionSelect)?.focus();
            return;
        }

        // DATA CONVERSION MODE

        // Prevent .lss files in data mode (they don't contain response data)
        if (isLssFile) {
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i><strong>.lss files contain structure only</strong> (no response data). Use <a href="/template-editor" class="alert-link">Template Editor</a> for template generation, or upload a <strong>.lsa</strong> file (archive with responses).';
            convertError.classList.remove('d-none');
            return;
        }

        // Validate ID map before sending
        const idMap = convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
        if (idMap) {
            if (idMap.size === 0) {
                convertError.classList.remove('d-none');
                convertError.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i>ID map file is empty`;
                return;
            }
        }

        // Validate ID column selection for non-PRISM data
        const idColumnVal = document.getElementById('convertIdColumn')?.value;
        if (!window._isPrismData && (!idColumnVal || idColumnVal === 'auto' || idColumnVal === '')) {
            convertError.classList.remove('d-none');
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Please select a participant ID column before converting.';
            const idSelect = document.getElementById('convertIdColumn');
            if (idSelect) {
                idSelect.classList.add('border-danger');
                idSelect.focus();
            }
            return;
        }

        const formData = new FormData();
        formData.append('excel', file);
        console.log(`[CLIENT DEBUG] Excel file: ${file.name}, size: ${file.size}`);

        if (idMap) {
            console.log(`[CLIENT DEBUG] ID map file before append: ${idMap.name}, size: ${idMap.size}, type: ${idMap.type}`);
            formData.append('id_map', idMap);
            console.log(`[CLIENT DEBUG] ID map appended to FormData`);
            appendLog(`Using ID map file: ${idMap.name} (${idMap.size} bytes)`, 'step');
        }

        // Library path is now resolved automatically (project first, then global)
        formData.append('dataset_name', convertDatasetName.value.trim());

        // Show log container
        conversionLogContainer.classList.remove('d-none');
        conversionLogBody.classList.remove('d-none');
        const icon = toggleLogBtn.querySelector('i');
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');

        appendLog(`Starting conversion of: ${file.name}`, 'info');
        appendLog(`Using library: Project library first, then global`, 'step');

        // Always save to project's rawdata folder when a project is loaded
        formData.append('save_to_project', 'true');
        appendLog('Output will be saved to project rawdata folder', 'step');

        // Add ID column if selected
        if (idColumnVal && idColumnVal !== 'auto' && idColumnVal !== '') {
            formData.append('id_column', idColumnVal);
            appendLog(`Using ID column: ${idColumnVal}`, 'step');
        }

        formData.append('session', sessionVal);
        appendLog(`Forcing session ID: ${sessionVal}`, 'step');

        formData.append('language', convertLanguage ? convertLanguage.value : 'auto');
        formData.append('validate', 'true');  // Request validation

        convertBtn.disabled = true;
        appendLog('Uploading file and starting conversion...', 'info');

        fetch('/api/survey-convert-validate', {
            method: 'POST',
            body: formData,
        })
        .then(async response => {
            const contentType = response.headers.get('content-type') || '';
            let data = null;
            
            if (contentType.includes('application/json')) {
                data = await response.json();
                // Process logs even if response is not ok
                if (data.log && Array.isArray(data.log)) {
                    data.log.forEach(entry => {
                        appendLog(entry.message, entry.type || entry.level || 'info');
                    });
                }
                
                if (!response.ok) {
                    if (data.error === 'id_column_required') {
                        const idSelect = document.getElementById('convertIdColumn');
                        if (idSelect) {
                            idSelect.classList.add('border-danger');
                            idSelect.focus();
                        }
                        throw new Error('Please select the participant ID column.');
                    }
                    if (data.error === 'unmatched_groups') {
                        displayUnmatchedGroupsError(data);
                        return null;
                    }
                    throw new Error(data.error || 'Conversion failed');
                }
                return data;
            } else {
                // Fallback: direct ZIP download (old API)
                if (!response.ok) {
                    throw new Error('Conversion failed');
                }
                const blob = await response.blob();
                return { blob, validation: null };
            }
        })
        .then(data => {
            if (!data) return;  // Handled by resolution UI (e.g. unmatched groups)

            // Logs already processed above for JSON responses

            // Display conversion summary (template matches, tool columns, unmatched) before validation
            if (data.conversion_summary) {
                displayConversionSummary(data.conversion_summary);
            }

            // Register conversion in project.json Sessions/TaskDefinitions
            const regSessionVal = getSurveySessionValue();
            const regTasks = (data.conversion_summary && data.conversion_summary.tasks_included) || [];
            if (regSessionVal && regTasks.length) {
                const srcFile = file ? file.name : '';
                const srcExt = srcFile.toLowerCase().split('.').pop();
                const convType = (srcExt === 'lsa') ? 'survey-lsa' : 'survey-xlsx';
                registerSessionInProject(regSessionVal, regTasks, 'survey', srcFile, convType);
            }

            if (data.validation) {
                const v = data.validation;
                const errorCount = (v.errors || []).length;
                const warningCount = (v.warnings || []).length;

                if (errorCount === 0 && warningCount === 0) {
                    appendLog('✓ Validation passed - dataset is valid!', 'success');
                } else if (errorCount === 0) {
                    appendLog(`⚠ Validation passed with ${warningCount} warning(s)`, 'warning');
                } else {
                    appendLog(`✗ Validation failed with ${errorCount} error(s)`, 'error');
                }

                displayValidationResults(data.validation);
            }

            if (data.zip_base64) {
                // Decode base64 ZIP
                const byteCharacters = atob(data.zip_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                currentZipBlob = new Blob([byteArray], { type: 'application/zip' });
                appendLog('✓ Data saved to project rawdata folder', 'success');
            } else if (data.blob) {
                currentZipBlob = data.blob;
                appendLog('✓ Data saved to project rawdata folder', 'success');
            }

            // Final completion message
            appendLog('═══════════════════════════════════════════════', 'info');
            appendLog('✓ CONVERSION COMPLETED SUCCESSFULLY', 'success');
            appendLog('═══════════════════════════════════════════════', 'info');

            convertInfo.textContent = 'Conversion complete. See results below.';
            convertInfo.classList.remove('d-none');
        })
        .catch(err => {
            appendLog(`Error: ${err.message}`, 'error');
            convertError.textContent = err.message;
            convertError.classList.remove('d-none');
        })
        .finally(() => {
            updateConvertBtn();
        });
    });

    // Additional Variables button handler
    const createParticipantMappingBtn = document.getElementById('createParticipantMappingBtn');
    if (createParticipantMappingBtn) {
        createParticipantMappingBtn.addEventListener('click', function() {
            // Check if project is loaded using template variable
            const currentProjectPath = "{{ current_project.path or '' }}";
            if (!currentProjectPath) {
                alert('Please load a project first to add additional variables. Projects are managed in the Projects page.');
                return;
            }

            // Reset the modal to initial state
            document.getElementById('mappingColumnsContainer').classList.remove('d-none');
            document.getElementById('mappingSuccess').classList.add('d-none');
            document.getElementById('mappingError').classList.add('d-none');
            document.getElementById('saveMappingBtn').classList.remove('d-none');
            document.getElementById('cancelMappingBtn').classList.remove('d-none');
            document.getElementById('closeMappingBtn').classList.add('d-none');

            // Show the modal and prepare the mapping interface
            const modal = new bootstrap.Modal(document.getElementById('participantMappingModal'));
            
            // Get preview candidates from either survey preview or participants preview
            let mappingCandidates = [];

            if (window.lastPreviewData && window.lastPreviewData.participants_tsv) {
                const tsv = window.lastPreviewData.participants_tsv;
                mappingCandidates = tsv.unused_columns || [];
            } else if (window.lastParticipantsPreviewData && Array.isArray(window.lastParticipantsPreviewData.columns)) {
                const p = window.lastParticipantsPreviewData;
                const idCol = p.id_column;
                const schema = p.neurobagel_schema || {};
                const participantColumns = Array.isArray(p.source_columns) && p.source_columns.length > 0
                    ? p.source_columns
                    : p.columns;
                const excludedQuestionnaireCols = new Set(
                    Array.isArray(p.questionnaire_like_columns) ? p.questionnaire_like_columns : []
                );
                const previewRows = Array.isArray(p.preview_rows) ? p.preview_rows : [];

                function inferReason(colName, values) {
                    const lower = String(colName || '').toLowerCase();
                    const cleaned = (values || [])
                        .map(v => String(v ?? '').trim())
                        .filter(v => v.length > 0);

                    if (['date', 'time', 'timestamp', 'datetime'].some(t => lower.includes(t))) {
                        return 'Inferred as date/time from column name';
                    }

                    const dateLikeRegex = /^(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})(\s+\d{1,2}:\d{2}(:\d{2})?)?$/;
                    const dateLikeCount = cleaned.filter(v => dateLikeRegex.test(v) || !Number.isNaN(Date.parse(v))).length;
                    if (cleaned.length > 0 && (dateLikeCount / cleaned.length) >= 0.6) {
                        return 'Inferred as date/time from values';
                    }

                    const uniqueCount = new Set(cleaned).size;
                    const numericValues = cleaned.map(v => Number(v)).filter(v => !Number.isNaN(v));
                    const numericRatio = cleaned.length ? (numericValues.length / cleaned.length) : 0;

                    if (numericRatio > 0.8 && uniqueCount > 10) {
                        return 'Inferred as continuous (mostly numeric with many unique values)';
                    }
                    if (uniqueCount <= 10) {
                        return 'Inferred as categorical (few unique values)';
                    }
                    return 'Inferred as text/string (default)';
                }

                mappingCandidates = participantColumns
                    .filter(col => col !== idCol && !excludedQuestionnaireCols.has(col))
                    .map(col => ({
                        field_code: col,
                        description: schema[col]?.Description || '',
                        infer_reason: inferReason(
                            col,
                            previewRows
                                .map(row => row ? row[col] : null)
                                .filter(v => v !== null && v !== undefined && String(v).trim() !== '')
                        )
                    }));
            }

            if (mappingCandidates.length > 0) {
                renderParticipantMappingForm(mappingCandidates);
            } else {
                document.getElementById('saveMappingBtn').disabled = true;
                document.getElementById('mappingColumnsContainer').innerHTML = 
                    '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>No preview data available. Please run a preview first.</div>';
            }
            
            modal.show();
        });
    }

    // Helper function to render the additional variables form
    function renderParticipantMappingForm(unusedCols) {
        const container = document.getElementById('mappingColumnsContainer');
        
        if (!unusedCols || unusedCols.length === 0) {
            container.innerHTML = '<div class="alert alert-info"><i class="fas fa-info-circle me-2"></i>No additional variables available to add.</div>';
            document.getElementById('saveMappingBtn').disabled = true;
            return;
        }

        let html = `
            <div class="mb-3">
                <h6>Select columns to include in participants.tsv (on next Extract & Convert):</h6>
                <div class="form-check-list" style="max-height: 300px; overflow-y: auto;">
        `;

        unusedCols.forEach((item, idx) => {
            const fieldCode = typeof item === 'object' ? item.field_code : item;
            const description = typeof item === 'object' ? (item.description || '') : '';
            const inferReason = typeof item === 'object' ? (item.infer_reason || '') : '';
            const inferIcon = inferReason
                ? `<i class="fas fa-circle-info text-muted ms-1" title="${String(inferReason).replace(/"/g, '&quot;')}"></i>`
                : '';
            
            html += `
                <div class="form-check mb-2">
                    <input class="form-check-input col-selector" type="checkbox" id="col_${idx}" value="${fieldCode}" data-description="${description}">
                    <label class="form-check-label" for="col_${idx}">
                        <strong>${fieldCode}</strong>${inferIcon}
                        ${description ? `<br><small class="text-muted">→ ${description}</small>` : ''}
                    </label>
                </div>
            `;
        });

        html += `
                </div>
            </div>
            <div class="alert alert-info small">
                <i class="fas fa-lightbulb me-2"></i>
                <strong>Tip:</strong> Columns with descriptive text are likely demographic fields that should be included.
            </div>
        `;

        container.innerHTML = html;

        // Enable save button when selections are made
        const checkboxes = document.querySelectorAll('.col-selector');
        const updateSaveBtn = () => {
            const hasSelection = Array.from(checkboxes).some(cb => cb.checked);
            document.getElementById('saveMappingBtn').disabled = !hasSelection;
        };

        checkboxes.forEach(cb => {
            cb.addEventListener('change', updateSaveBtn);
        });
    }

    // Save Selection button handler
    const saveMappingBtn = document.getElementById('saveMappingBtn');
    if (saveMappingBtn) {
        saveMappingBtn.addEventListener('click', async function() {
            const selected = Array.from(document.querySelectorAll('.col-selector:checked'));
            
            if (selected.length === 0) {
                alert('Please select at least one column');
                return;
            }

            // Build explicit participants_mapping.json-compatible object.
            // Important: keep selected variable names as-is (e.g., session, completion_date)
            // so they appear exactly in participants.tsv after conversion.
            const mapping = {
                version: '1.0',
                description: 'Additional variables mapping created from PRISM web UI',
                mappings: {}
            };
            selected.forEach(checkbox => {
                const fieldCode = String(checkbox.value || '').trim();
                if (!fieldCode) return;

                const description = String(checkbox.getAttribute('data-description') || '').trim();
                mapping.mappings[fieldCode] = {
                    source_column: fieldCode,
                    standard_variable: fieldCode,
                    type: 'string'
                };
                if (description) {
                    mapping.mappings[fieldCode].description = description;
                }
            });

            // Get the library path from the form (will use project library by preference in backend)
            const libraryPath = document.getElementById('convertLibraryPath')?.value || '';

            try {
                // Send mapping to backend to save
                const response = await fetch('/api/save-participant-mapping', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        mapping: mapping,
                        library_path: libraryPath
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || 'Failed to save additional variables selection');
                }

                showMappingSuccess(result.file_path);
            } catch (err) {
                showMappingError(err.message);
            }
        });
    }

    function showMappingSuccess(filePath) {
        document.getElementById('mappingColumnsContainer').classList.add('d-none');
        document.getElementById('mappingSuccess').classList.remove('d-none');
        document.getElementById('mappingError').classList.add('d-none');
        document.getElementById('mappingFilePath').innerHTML = `
            <strong>File created:</strong> <code>${filePath}</code><br>
            <span class="text-muted">Run <strong>2. Extract &amp; Convert</strong> to apply these variables to participants.tsv.</span>
        `;
        
        // Hide the Save and Cancel buttons, show the Close button
        document.getElementById('saveMappingBtn').classList.add('d-none');
        document.getElementById('cancelMappingBtn').classList.add('d-none');
        document.getElementById('closeMappingBtn').classList.remove('d-none');
    }

    function showMappingError(message) {
        document.getElementById('mappingError').classList.remove('d-none');
        document.getElementById('mappingErrorText').textContent = message;
        document.getElementById('mappingSuccess').classList.add('d-none');
    }

    // Preview button (dry-run) handler
    previewBtn.addEventListener('click', async function() {
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');
        convertError.textContent = '';
        convertInfo.textContent = '';
        resetConversionUI();

        const file = convertExcelFile.files && convertExcelFile.files[0];
        if (!file) {
            return;
        }

        // Validate ID map before sending
        const idMap = convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
        if (idMap) {
            // Just check that a file is selected; don't read it (avoids stream issues)
            console.log(`[CLIENT DEBUG] ID map file selected: ${idMap.name} (size: ${idMap.size} bytes, type: ${idMap.type})`);
            if (idMap.size === 0) {
                convertError.classList.remove('d-none');
                convertError.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i>ID map file is empty`;
                return;
            }
        }

        // Validate ID column selection for non-PRISM data
        const previewIdCol = document.getElementById('convertIdColumn')?.value;
        if (!window._isPrismData && (!previewIdCol || previewIdCol === 'auto' || previewIdCol === '')) {
            convertError.classList.remove('d-none');
            convertError.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Please select a participant ID column before previewing.';
            const idSelect = document.getElementById('convertIdColumn');
            if (idSelect) {
                idSelect.classList.add('border-danger');
                idSelect.focus();
            }
            return;
        }

        const formData = new FormData();
        formData.append('excel', file);

        if (idMap) {
            console.log(`[CLIENT DEBUG] About to append id_map to FormData: ${idMap.name} (size: ${idMap.size} bytes)`);
            formData.append('id_map', idMap);
            console.log(`[CLIENT DEBUG] Successfully appended id_map to FormData`);
        }

        // Add ID column if selected
        if (previewIdCol && previewIdCol !== 'auto' && previewIdCol !== '') {
            formData.append('id_column', previewIdCol);
        }

        const sessionVal = getSurveySessionValue();
        if (sessionVal) {
            formData.append('session', sessionVal);
        }

        formData.append('language', convertLanguage ? convertLanguage.value : 'auto');

        // Default: run validation in preview
        formData.append('validate', 'true');

        // Show log container
        conversionLogContainer.classList.remove('d-none');
        conversionLogBody.classList.remove('d-none');
        const icon = toggleLogBtn.querySelector('i');
        icon.classList.remove('fa-chevron-right');
        icon.classList.add('fa-chevron-down');

        appendLog('🔍 PREVIEW MODE (Dry-Run)', 'info');
        appendLog('═══════════════════════════════════════', 'info');
        appendLog(`Analyzing file: ${file.name}`, 'step');
        if (idMap) {
            appendLog(`With ID map: ${idMap.name}`, 'step');
        }
        appendLog('No files will be created.', 'info');
        appendLog('', 'info');

        console.log(`[CLIENT DEBUG] FormData ready, sending to /api/survey-convert-preview`);
        console.log(`[CLIENT DEBUG] FormData contains:`, {
            excel: file.name,
            excel_size: file.size,
            id_map: idMap ? idMap.name : null,
            id_map_size: idMap ? idMap.size : null
        });

        previewBtn.disabled = true;
        convertBtn.disabled = true;

        fetch('/api/survey-convert-preview', {
            method: 'POST',
            body: formData,
        })
        .then(async response => {
            const data = await response.json();
            
            // DEBUG: Log the FULL response to understand structure
            console.log('[SURVEY-PREVIEW FULL RESPONSE]', data);
            console.log('[SURVEY-PREVIEW RESPONSE]', {
                status: response.ok,
                detected_sessions: data.detected_sessions,
                session_column: data.session_column,
                has_preview: !!data.preview,
                all_keys: Object.keys(data)
            });

            if (!response.ok) {
                if (data.error === 'id_column_required') {
                    const idSelect = document.getElementById('convertIdColumn');
                    if (idSelect) {
                        idSelect.classList.add('border-danger');
                        idSelect.focus();
                    }
                    throw new Error('Please select the participant ID column.');
                }
                if (data.error === 'unmatched_groups') {
                    displayUnmatchedGroupsError(data);
                    return null;
                }
                throw new Error(data.error || 'Preview failed');
            }

            const sessionsLoaded = populateSurveySessionPickerFromDetected(data.detected_sessions);
            if (sessionsLoaded) {
                appendLog(`✓ Sessions auto-detected: ${data.detected_sessions.join(', ')}`, 'success');
            } else if (data.session_column) {
                appendLog(`⚠ Session column '${data.session_column}' found but no sessions detected. Enter session manually.`, 'warning');
            }

            const preview = data.preview;

            if (!preview) {
                appendLog('⚠ No preview data received', 'warning');
                return;
            }

            // Display summary
            appendLog('📊 SUMMARY', 'info');
            appendLog(`   Total participants: ${preview.summary.total_participants}`, 'info');
            appendLog(`   Unique participants: ${preview.summary.unique_participants}`, 'info');
            appendLog(`   Tasks detected: ${preview.summary.tasks.join(', ')}`, 'info');
            appendLog(`   Total files to create: ${preview.summary.total_files}`, 'info');
            appendLog('', 'info');

            // Display conversion summary (template matches, tool columns, unmatched) before validation
            if (data.conversion_summary) {
                displayConversionSummary(data.conversion_summary);
            }

            // Show validation results if backend ran validation during preview
            if (data.validation) {
                const v = data.validation;
                const errorCount = (v.errors || []).length;
                const warningCount = (v.warnings || []).length;
                const summaryErrors = v.summary && Number.isFinite(v.summary.total_errors)
                    ? v.summary.total_errors
                    : errorCount;
                const summaryWarnings = v.summary && Number.isFinite(v.summary.total_warnings)
                    ? v.summary.total_warnings
                    : warningCount;

                if (summaryErrors === 0 && summaryWarnings === 0) {
                    appendLog('✓ Validation (preview) passed - dataset is valid!', 'success');
                } else if (summaryErrors === 0) {
                    appendLog(`⚠ Validation (preview) passed with ${summaryWarnings} warning(s)`, 'warning');
                } else {
                    appendLog(`✗ Validation (preview) failed with ${summaryErrors} error(s)`, 'error');
                }

                if (summaryErrors > 0) {
                    let printed = 0;
                    const maxToShow = 20;

                    if (v.formatted && Array.isArray(v.formatted.errors)) {
                        for (const group of v.formatted.errors) {
                            for (const fileIssue of (group.files || [])) {
                                if (printed >= maxToShow) break;
                                const msg = (fileIssue && fileIssue.message) ? fileIssue.message : (group.message || 'Validation error');
                                appendLog(`  - ${msg}`, 'error');
                                printed++;
                            }
                            if (printed >= maxToShow) break;
                        }
                    }

                    if (printed === 0 && Array.isArray(v.errors)) {
                        for (const err of v.errors) {
                            if (printed >= maxToShow) break;
                            if (typeof err === 'string') {
                                appendLog(`  - ${err}`, 'error');
                                printed++;
                            }
                        }
                    }

                    if (summaryErrors > printed) {
                        appendLog(`  ... and ${summaryErrors - printed} more errors (see details below)`, 'error');
                    }
                }

                if (summaryWarnings > 0) {
                    appendLog(`⚠ ${summaryWarnings} warning(s) found`, 'warning');
                }

                displayValidationResults(data.validation);
                appendLog('', 'info');
            }

            // Display data issues
            if (preview.data_issues && preview.data_issues.length > 0) {
                appendLog(`⚠️  DATA ISSUES FOUND (${preview.data_issues.length})`, 'warning');
                appendLog('   Fix these issues BEFORE conversion:', 'warning');
                appendLog('', 'warning');
                
                preview.data_issues.slice(0, 10).forEach(issue => {
                    const severity = issue.severity.toUpperCase();
                    appendLog(`   [${severity}] ${issue.type}`, 'warning');
                    appendLog(`   → ${issue.message}`, 'warning');
                    
                    if (issue.type === 'duplicate_ids' && issue.details) {
                        const dups = Object.keys(issue.details).slice(0, 5);
                        appendLog(`   → Duplicates: ${dups.join(', ')}`, 'warning');
                    } else if (issue.type === 'unexpected_values') {
                        appendLog(`   → Column: ${issue.column} (task: ${issue.task}, item: ${issue.item})`, 'warning');
                        if (issue.unexpected) {
                            appendLog(`   → Unexpected values: ${issue.unexpected.slice(0, 5).join(', ')}`, 'warning');
                        }
                    } else if (issue.type === 'out_of_range') {
                        appendLog(`   → Column: ${issue.column} (task: ${issue.task}, item: ${issue.item})`, 'warning');
                        appendLog(`   → Expected range: ${issue.range}`, 'warning');
                        appendLog(`   → Out of range count: ${issue.out_of_range_count}`, 'warning');
                    }
                    appendLog('', 'warning');
                });
                
                if (preview.data_issues.length > 10) {
                    appendLog(`   ... and ${preview.data_issues.length - 10} more issues`, 'warning');
                }
                appendLog('', 'info');
            } else {
                appendLog('✅ NO DATA ISSUES DETECTED', 'success');
                appendLog('', 'info');
            }

            // Display participants.tsv preview (only if participants are being created)
            if (preview.participants_tsv && Object.keys(preview.participants_tsv).length > 0) {
                const tsv = preview.participants_tsv;
                
                // Store preview data globally for the mapping button
                window.lastPreviewData = preview;
                
                // Enable the additional variables button if there are unused columns
                if (createParticipantMappingBtn) {
                    createParticipantMappingBtn.disabled = !(tsv.unused_columns && tsv.unused_columns.length > 0);
                }
                
                appendLog('📝 PARTICIPANTS.TSV PREVIEW', 'info');
                appendLog('   This file will be created with the following structure:', 'info');
                appendLog('', 'info');
                
                // Columns
                appendLog(`   Columns (${tsv.columns.length} total):`, 'info');
                tsv.columns.forEach(col => {
                    appendLog(`     • ${col}`, 'info');
                });
                
                // Mappings
                if (Object.keys(tsv.mappings).length > 0) {
                    appendLog('', 'info');
                    appendLog('   Column Mappings:', 'info');
                    Object.entries(tsv.mappings).forEach(([outputCol, mappingInfo]) => {
                        const hasMapping = mappingInfo.has_value_mapping;
                        const indicator = hasMapping ? '🔄' : '✓';
                        appendLog(`     ${indicator} ${outputCol} ← ${mappingInfo.source_column}`, 'info');
                        if (hasMapping && Object.keys(mappingInfo.value_mapping).length > 0) {
                            appendLog(`        (has value transformation mapping)`, 'info');
                        }
                    });
                }
                
                // Sample data
                if (tsv.sample_rows.length > 0) {
                    appendLog('', 'info');
                    const sampleCount = Math.min(5, tsv.sample_rows.length);
                    appendLog(`   Sample Data (showing first ${sampleCount} of ${tsv.total_rows} participants):`, 'info');
                    appendLog(`   ${'-'.repeat(100)}`, 'info');
                    
                    // Header
                    const header = tsv.columns.map(col => col.padEnd(20)).join(' | ');
                    appendLog(`   ${header}`, 'info');
                    appendLog(`   ${'-'.repeat(100)}`, 'info');
                    
                    // Rows
                    tsv.sample_rows.slice(0, 5).forEach(rowData => {
                        const row = tsv.columns.map(col => String(rowData[col] || 'n/a').padEnd(20)).join(' | ');
                        appendLog(`   ${row}`, 'info');
                    });
                    
                    if (tsv.sample_rows.length > 5) {
                        appendLog(`   ... and ${tsv.sample_rows.length - 5} more rows shown above (total ${tsv.total_rows} participants)`, 'info');
                    }
                    appendLog(`   ${'-'.repeat(100)}`, 'info');
                }
                
                // Notes
                if (tsv.notes.length > 0) {
                    appendLog('', 'info');
                    appendLog('   📌 Notes:', 'info');
                    tsv.notes.forEach(note => {
                        appendLog(`     • ${note}`, 'info');
                    });
                }
                
                // Unused columns
                if (tsv.unused_columns && tsv.unused_columns.length > 0) {
                    appendLog('', 'info');
                    appendLog(`   ⚠️  UNUSED COLUMNS (${tsv.unused_columns.length} available for participants.tsv):`, 'warning');
                    appendLog(`      These columns are not being imported as survey data and could be included`, 'warning');
                    appendLog(`      in participants.tsv if you create/update participants_mapping.json:`, 'warning');
                    tsv.unused_columns.slice(0, 10).forEach(item => {
                        // Handle both old format (string) and new format (dict with description)
                        if (typeof item === 'object') {
                            const fieldCode = item.field_code || '';
                            const description = item.description || '';
                            appendLog(`      • ${fieldCode}`, 'warning');
                            if (description) {
                                appendLog(`        ↳ ${description}`, 'warning');
                            }
                        } else {
                            appendLog(`      • ${item}`, 'warning');
                        }
                    });
                    if (tsv.unused_columns.length > 10) {
                        appendLog(`      ... and ${tsv.unused_columns.length - 10} more columns`, 'warning');
                    }
                    
                    // Add hint to open additional variables selector
                    appendLog('', 'info');
                    appendLog(`   💡 TIP: Click "Add Additional Variables (Optional)", save the mapping, then run "2. Extract & Convert" to apply it.`, 'info');
                }
                
                appendLog('', 'info');
            }

            // Display participant preview
            appendLog('👥 PARTICIPANT PREVIEW (first 10)', 'info');
            preview.participants.slice(0, 10).forEach(p => {
                const completeness = p.completeness_percent;
                const status = completeness > 80 ? '✓' : (completeness > 50 ? '⚠' : '✗');
                appendLog(`   ${status} ${p.participant_id} (${p.session_id})`, 'info');
                appendLog(`      Raw ID: ${p.raw_id}`, 'info');
                appendLog(`      Completeness: ${completeness}% (${p.total_items - p.missing_values}/${p.total_items} items)`, 'info');
            });
            
            if (preview.participants.length > 10) {
                appendLog(`   ... and ${preview.participants.length - 10} more participants`, 'info');
            }
            appendLog('', 'info');

            // Display column mapping preview
            appendLog('📋 COLUMN MAPPING (first 15)', 'info');
            const cols = Object.entries(preview.column_mapping).slice(0, 15);
            cols.forEach(([col, info]) => {
                const run_info = info.run ? ` (run ${info.run})` : '';
                const status = info.has_unexpected_values ? '⚠' : '✓';
                appendLog(`   ${status} ${col}`, 'info');
                appendLog(`      → Task: ${info.task}${run_info}, Item: ${info.base_item}`, 'info');
                appendLog(`      → Missing: ${info.missing_percent}% (${info.missing_count} values)`, 'info');
                if (info.has_unexpected_values) {
                    appendLog(`      ⚠ Has unexpected values!`, 'warning');
                }
            });
            
            if (Object.keys(preview.column_mapping).length > 15) {
                appendLog(`   ... and ${Object.keys(preview.column_mapping).length - 15} more columns`, 'info');
            }
            appendLog('', 'info');

            // Display file structure
            appendLog('📁 FILES TO CREATE', 'info');
            const fileTypes = {};
            preview.files_to_create.forEach(f => {
                fileTypes[f.type] = (fileTypes[f.type] || 0) + 1;
            });
            
            appendLog(`   Metadata files: ${fileTypes.metadata || 0}`, 'info');
            appendLog(`   Sidecar files: ${fileTypes.sidecar || 0}`, 'info');
            appendLog(`   Data files: ${fileTypes.data || 0}`, 'info');
            appendLog('', 'info');
            
            appendLog('   Sample files:', 'info');
            const shownByType = {metadata: 0, sidecar: 0, data: 0};
            preview.files_to_create.forEach(f => {
                if (shownByType[f.type] < 3) {
                    appendLog(`   - ${f.path}`, 'info');
                    appendLog(`     ${f.description}`, 'info');
                    shownByType[f.type]++;
                }
            });

            appendLog('', 'info');
            appendLog('═══════════════════════════════════════', 'info');
            
            // Count errors and warnings from validation results and data issues
            let previewErrorCount = 0;
            let previewWarningCount = 0;
            
            if (data.validation) {
                // Check for validation.summary
                if (data.validation.summary) {
                    previewErrorCount = data.validation.summary.total_errors || 0;
                    previewWarningCount = data.validation.summary.total_warnings || 0;
                }
                // Check for validation.errors array
                else if (data.validation.errors && Array.isArray(data.validation.errors)) {
                    previewErrorCount = data.validation.errors.length;
                }
                // Check for validation.warnings array 
                if (data.validation.warnings && Array.isArray(data.validation.warnings)) {
                    previewWarningCount = (previewWarningCount || 0) + data.validation.warnings.length;
                }
                // Check if validation itself is an error (single error object/string)
                if (data.validation.error) {
                    previewErrorCount++;
                }
            }
            
            // Add data_issues count (these are warnings)
            const dataIssueCount = preview.data_issues ? preview.data_issues.length : 0;
            if (dataIssueCount > 0) {
                previewWarningCount += dataIssueCount;
            }
            
            console.log(`Counts - Errors: ${previewErrorCount}, Warnings: ${previewWarningCount}`);
            
            if (previewErrorCount > 0) {
                appendLog('⚠ PREVIEW COMPLETED WITH VALIDATION ERRORS', 'warning');
                appendLog(`   🔴 ${previewErrorCount} error(s) - FIX REQUIRED before converting`, 'error');
                if (previewWarningCount > 0) {
                    appendLog(`   🟡 ${previewWarningCount} warning(s)`, 'warning');
                }
                if (dataIssueCount > 0) {
                    appendLog(`   ⚠️  ${dataIssueCount} data issue(s)`, 'warning');
                }
                convertInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Preview completed, but validation found errors. Fix these issues before converting.';
            } else if (previewWarningCount > 0 || dataIssueCount > 0) {
                appendLog('✓ PREVIEW COMPLETED (with warnings)', 'warning');
                if (previewWarningCount > 0) {
                    appendLog(`   🟡 ${previewWarningCount} warning(s) - review recommended`, 'warning');
                }
                if (dataIssueCount > 0) {
                    appendLog(`   ⚠️  ${dataIssueCount} data issue(s)`, 'warning');
                }
                convertInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Preview completed with warnings. Review above before converting.';
            } else {
                appendLog('✓ PREVIEW COMPLETED SUCCESSFULLY', 'success');
                convertInfo.innerHTML = '<i class="fas fa-info-circle me-2"></i>Preview complete. Review the log above, then click <strong>Convert</strong> to proceed.';
            }
            appendLog('═══════════════════════════════════════', 'info');

            convertInfo.classList.remove('d-none');
        })
        .catch(err => {
            appendLog(`Error: ${err.message}`, 'error');
            convertError.textContent = err.message;
            convertError.classList.remove('d-none');
        })
        .finally(() => {
            previewBtn.disabled = false;
            convertBtn.disabled = false;
        });
    });

    // ===== INITIALIZE BIOMETRICS MODULE =====
    if (biometricsDataFile) {
        initBiometrics({
            biometricsDataFile,
            clearBiometricsDataFileBtn,
            biometricsPreviewBtn,
            biometricsConvertBtn,
            biometricsError,
            biometricsInfo,
            biometricsLogContainer,
            biometricsLog,
            biometricsLogBody,
            toggleBiometricsLogBtn,
            biometricsValidationResultsContainer,
            biometricsValidationResultsCard,
            biometricsValidationResultsHeader,
            biometricsValidationBadge,
            biometricsValidationSummary,
            biometricsValidationDetails,
            biometricsDownloadSection,
            biometricsDownloadWarningSection,
            biometricsDownloadZipBtn,
            biometricsDownloadZipWarningBtn,
            biometricsDetectedContainer,
            biometricsDetectedList,
            biometricsConfirmBtn,
            biometricsSelectAll,
            biometricsSessionSelect,
            biometricsSessionCustom,
            // Shared helper functions available in converter scope
            appendLog,
            displayValidationResults,
            downloadBase64Zip,
            registerSessionInProject,
            getBiometricsSessionValue
        });
    }

    // ===== INITIALIZE PHYSIO MODULE =====
    if (physioRawFile) {
        initPhysio({
            // Single mode
            physioRawFile,
            physioTask,
            physioSamplingRate,
            physioConvertBtn,
            physioError,
            physioInfo,
            // Batch mode
            physioBatchFiles,
            clearPhysioBatchFilesBtn,
            physioBatchFolder,
            clearPhysioBatchFolderBtn,
            physioBatchSamplingRate,
            physioBatchDryRun,
            physioBatchConvertBtn,
            physioBatchError,
            physioBatchInfo,
            physioBatchProgress,
            physioBatchLogContainer,
            physioBatchLog,
            physioBatchLogClearBtn,
            autoDetectPhysioBtn,
            autoDetectHint,
            physioBatchFolderPath,
            // Shared functions
            appendLog
        });
    }

    // --- Eyetracking Single Convert ---
    function updateEyetrackingSingleBtn() {

    function updateEyetrackingSingleBtn() {
        const hasFile = eyetrackingSingleFile && eyetrackingSingleFile.files && eyetrackingSingleFile.files.length === 1;
        const hasSubject = eyetrackingSubject && eyetrackingSubject.value.trim().length > 0;
        if (eyetrackingSingleConvertBtn) eyetrackingSingleConvertBtn.disabled = !(hasFile && hasSubject);
    }

    if (eyetrackingSingleFile) {
        eyetrackingSingleFile.addEventListener('change', updateEyetrackingSingleBtn);
    }
    if (eyetrackingSubject) {
        eyetrackingSubject.addEventListener('input', updateEyetrackingSingleBtn);
    }
    updateEyetrackingSingleBtn();

    if (eyetrackingSingleConvertBtn) {
        eyetrackingSingleConvertBtn.addEventListener('click', async function() {
            eyetrackingSingleError.classList.add('d-none');
            eyetrackingSingleInfo.classList.add('d-none');
            eyetrackingSingleConvertBtn.disabled = true;

            const file = eyetrackingSingleFile.files[0];
            const subject = eyetrackingSubject.value.trim();
            const session = eyetrackingSession ? eyetrackingSession.value.trim() : '';
            const task = eyetrackingTask ? eyetrackingTask.value.trim() : 'gaze';

            const formData = new FormData();
            formData.append('edf', file);
            formData.append('subject', subject);
            formData.append('task', task);
            if (session) formData.append('session', session);

            eyetrackingSingleInfo.textContent = 'Converting... this may take a moment.';
            eyetrackingSingleInfo.classList.remove('d-none');

            try {
                const response = await fetch('/api/eyetracking-convert', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data && data.error ? data.error : 'Conversion failed');
                }

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'eyetracking_prism.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
                eyetrackingSingleInfo.textContent = 'Done. Your ZIP download should start automatically.';
            } catch (err) {
                eyetrackingSingleError.textContent = err.message;
                eyetrackingSingleError.classList.remove('d-none');
                eyetrackingSingleInfo.classList.add('d-none');
            } finally {
                updateEyetrackingSingleBtn();
            }
        });
    }

    // --- Eyetracking Batch Convert ---
    function updateEyetrackingBatchBtn() {
        const hasFiles = eyetrackingBatchFiles && eyetrackingBatchFiles.files && eyetrackingBatchFiles.files.length > 0;
        clearEyetrackingBatchFilesBtn?.classList.toggle('d-none', !hasFiles);
        if (eyetrackingBatchConvertBtn) eyetrackingBatchConvertBtn.disabled = !hasFiles;
    }

    if (eyetrackingBatchFiles) {
        eyetrackingBatchFiles.addEventListener('change', updateEyetrackingBatchBtn);
        updateEyetrackingBatchBtn();
    }

    clearEyetrackingBatchFilesBtn?.addEventListener('click', function() {
        if (eyetrackingBatchFiles) {
            eyetrackingBatchFiles.value = '';
            eyetrackingBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
        }
        eyetrackingBatchError.classList.add('d-none');
        eyetrackingBatchError.textContent = '';
        eyetrackingBatchInfo.classList.add('d-none');
        eyetrackingBatchInfo.textContent = '';
    });

    if (eyetrackingBatchLogClearBtn) {
        eyetrackingBatchLogClearBtn.addEventListener('click', () => {
            if (eyetrackingBatchLog) eyetrackingBatchLog.textContent = '';
        });
    }

    // Handle dry-run checkbox state change for eyetracking
    const eyetrackingBatchDryRunCheckbox = document.getElementById('eyetrackingBatchDryRun');
    if (eyetrackingBatchDryRunCheckbox) {
        eyetrackingBatchDryRunCheckbox.addEventListener('change', function() {
            if (eyetrackingBatchConvertBtn) {
                if (this.checked) {
                    eyetrackingBatchConvertBtn.innerHTML = '<i class="fas fa-flask me-2"></i>Preview (Dry-Run)';
                } else {
                    eyetrackingBatchConvertBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Convert All & Download';
                }
            }
        });
    }

    if (eyetrackingBatchConvertBtn) {
        eyetrackingBatchConvertBtn.addEventListener('click', async function() {
            eyetrackingBatchError.classList.add('d-none');
            eyetrackingBatchInfo.classList.add('d-none');
            eyetrackingBatchProgress.classList.remove('d-none');
            eyetrackingBatchLogContainer.classList.remove('d-none');
            eyetrackingBatchLog.textContent = '';
            eyetrackingBatchConvertBtn.disabled = true;

            const files = Array.from(eyetrackingBatchFiles.files);
            const isDryRun = document.getElementById('eyetrackingBatchDryRun')?.checked || false;

            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            formData.append('modality', 'eyetracking');
            formData.append('dry_run', isDryRun ? 'true' : 'false');
            formData.append('save_to_project', 'true');
            formData.append('dest_root', 'rawdata');

            try {
                const response = await fetch('/api/batch-convert', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data && data.error ? data.error : 'Batch conversion failed');
                }

                const result = await response.json();
                
                // Show log with colors based on level, not ANSI codes
                if (result.logs && Array.isArray(result.logs)) {
                    const logLines = result.logs.map(log => {
                        // Determine color class from level
                        let colorClass = 'ansi-reset';
                        if (log.level === 'error') colorClass = 'ansi-red';
                        else if (log.level === 'warning') colorClass = 'ansi-yellow';
                        else if (log.level === 'success') colorClass = 'ansi-green';
                        else if (log.level === 'info') colorClass = 'ansi-blue';
                        else if (log.level === 'preview') colorClass = 'ansi-cyan';
                        
                        // Escape HTML and wrap with color
                        const escaped = log.message.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                        return `<span class="${colorClass}">${escaped}</span>`;
                    });
                    eyetrackingBatchLog.innerHTML = logLines.join('<br>');
                    eyetrackingBatchLog.scrollTop = eyetrackingBatchLog.scrollHeight;
                } else if (result.log) {
                    eyetrackingBatchLog.textContent = result.log;
                }

                if (isDryRun && result.dry_run) {
                    // Dry-run preview mode
                    let infoMsg = `🧪 DRY-RUN PREVIEW\n\n`;
                    infoMsg += `✓ Would convert: ${result.converted || 0} files\n`;
                    if (result.errors) infoMsg += `✗ Errors: ${result.errors}\n`;
                    if (result.new_files) infoMsg += `📁 New files: ${result.new_files}\n`;
                    if (result.existing_files) infoMsg += `⚠️  Existing files: ${result.existing_files}\n`;
                    eyetrackingBatchInfo.textContent = infoMsg;
                } else {
                    // Download the ZIP
                    if (result.zip) {
                        downloadBase64Zip(result.zip, `Eyetracking_prism.zip`);
                    }
                    let statusMsg = `✓ Converted ${result.converted || 0} files. ${result.errors || 0} errors.`;
                    if (result.project_saved) {
                        statusMsg += `\n📁 Files also saved to project.`;
                    }
                    if (result.warnings && result.warnings.length > 0) {
                        statusMsg += `\n⚠️  Warnings:\n${result.warnings.join('\n')}`;
                    }
                    eyetrackingBatchInfo.textContent = statusMsg;
                }
                eyetrackingBatchInfo.classList.remove('d-none');
            } catch (err) {
                eyetrackingBatchError.textContent = err.message;
                eyetrackingBatchError.classList.remove('d-none');
            } finally {
                eyetrackingBatchProgress.classList.add('d-none');
                updateEyetrackingBatchBtn();
            }
        });
    }

    // --- Organize Batch ---
    function updateOrganizeBtn() {
        const hasFiles = organizeFiles && organizeFiles.files && organizeFiles.files.length > 0;
        if (organizeBtn) organizeBtn.disabled = !hasFiles;
    }

    if (organizeFiles) {
        organizeFiles.addEventListener('change', updateOrganizeBtn);
        updateOrganizeBtn();
    }

    if (organizeLogClearBtn) {
        organizeLogClearBtn.addEventListener('click', () => {
            if (organizeLog) organizeLog.textContent = '';
        });
    }

    if (organizeBtn) {
        organizeBtn.addEventListener('click', async function() {
            organizeError.classList.add('d-none');
            organizeInfo.classList.add('d-none');
            organizeProgress.classList.remove('d-none');
            organizeLogContainer.classList.remove('d-none');
            organizeLog.textContent = '';
            organizeBtn.disabled = true;

            const files = Array.from(organizeFiles.files);
            const datasetName = organizeDatasetName ? organizeDatasetName.value.trim() : 'Organized Dataset';
            const modality = organizeModality ? organizeModality.value : 'anat';

            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            formData.append('dataset_name', datasetName);
            formData.append('modality', modality);

            try {
                const response = await fetch('/api/batch-convert', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data && data.error ? data.error : 'Organization failed');
                }

                const result = await response.json();
                
                // Show log with colors based on level
                if (result.logs && Array.isArray(result.logs)) {
                    const logLines = result.logs.map(log => {
                        let colorClass = 'ansi-reset';
                        if (log.level === 'error') colorClass = 'ansi-red';
                        else if (log.level === 'warning') colorClass = 'ansi-yellow';
                        else if (log.level === 'success') colorClass = 'ansi-green';
                        else if (log.level === 'info') colorClass = 'ansi-blue';
                        else if (log.level === 'preview') colorClass = 'ansi-cyan';
                        
                        const escaped = log.message.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                        return `<span class="${colorClass}">${escaped}</span>`;
                    });
                    organizeLog.innerHTML = logLines.join('<br>');
                    organizeLog.scrollTop = organizeLog.scrollHeight;
                } else if (result.log) {
                    organizeLog.textContent = result.log;
                }

                // Download the ZIP
                if (result.zip) {
                    downloadBase64Zip(result.zip, `${datasetName}_prism.zip`);
                }

                organizeInfo.textContent = `Organized ${result.converted || 0} files. ${result.errors || 0} errors.`;
                organizeInfo.classList.remove('d-none');
            } catch (err) {
                organizeError.textContent = err.message;
                organizeError.classList.remove('d-none');
            } finally {
                organizeProgress.classList.add('d-none');
                updateOrganizeBtn();
            }
        });
    }

    // --- Physio Renamer Logic ---
    const renamerExampleContainer = document.getElementById('renamerExampleContainer');
    const renamerOriginalExample = document.getElementById('renamerOriginalExample');
    const renamerNewExample = document.getElementById('renamerNewExample');
    const renamerModality = document.getElementById('renamerModality');
    const renamerExampleHint = document.getElementById('renamerExampleHint');
    let currentExampleFile = null;

    const modalityHints = {
        'physio': 'sub-001_task-rest_physio.edf',
        'biometrics': 'sub-001_biometrics-height_biometrics.tsv',
        'events': 'sub-001_task-rest_events.tsv',
        'survey': 'sub-001_survey-phq9_survey.tsv'
    };

    const renamerRecordingContainer = document.getElementById('renamerRecordingContainer');
    const renamerRecording = document.getElementById('renamerRecording');

    function updateRecordingVisibility() {
        if (renamerModality && renamerRecordingContainer) {
            const showRecording = renamerModality.value === 'physio';
            renamerRecordingContainer.style.display = showRecording ? 'block' : 'none';
        }
    }

    if (renamerModality) {
        renamerModality.addEventListener('change', () => {
            const mod = renamerModality.value;
            let hint = modalityHints[mod] || 'sub-001_task-rest_physio.edf';
            
            // Update hint based on recording selection for physio
            if (mod === 'physio' && renamerRecording && renamerRecording.value) {
                hint = `sub-001_task-rest_recording-${renamerRecording.value}_physio.edf`;
            }
            
            if (renamerExampleHint) renamerExampleHint.innerHTML = `Example: <code>${hint}</code>`;
            if (renamerNewExample) renamerNewExample.placeholder = `e.g. ${hint}`;
            
            updateRecordingVisibility();
            inferPattern();
        });
    }

    if (renamerRecording) {
        renamerRecording.addEventListener('change', () => {
            const mod = renamerModality ? renamerModality.value : 'physio';
            let hint = modalityHints[mod] || 'sub-001_task-rest_physio.edf';
            
            if (renamerRecording.value) {
                hint = `sub-001_task-rest_recording-${renamerRecording.value}_physio.edf`;
            }
            
            if (renamerExampleHint) renamerExampleHint.innerHTML = `Example: <code>${hint}</code>`;
            if (renamerNewExample) renamerNewExample.placeholder = `e.g. ${hint}`;
            inferPattern();
        });
    }

    // Initialize visibility
    updateRecordingVisibility();

    function updateRenamerBtn() {
        const hasFiles = renamerFiles && renamerFiles.files && renamerFiles.files.length > 0;
        const hasNewName = renamerNewExample && renamerNewExample.value.trim().length > 0;
        if (renamerDownloadBtn) renamerDownloadBtn.disabled = !hasFiles || !hasNewName;
    }

    function pickExampleFile() {
        if (!renamerFiles || !renamerFiles.files || renamerFiles.files.length === 0) return;
        const files = Array.from(renamerFiles.files);
        currentExampleFile = files[Math.floor(Math.random() * files.length)];
        if (renamerOriginalExample) renamerOriginalExample.textContent = currentExampleFile.name;
        if (renamerExampleContainer) renamerExampleContainer.classList.remove('d-none');
        if (renamerNewExample) {
            renamerNewExample.value = '';
            renamerNewExample.focus();
        }
        updateRenamerBtn();
        if (renamerPreview) renamerPreview.classList.add('d-none');
    }

    if (renamerFiles) {
        renamerFiles.addEventListener('change', () => {
            pickExampleFile();
            updateRenamerBtn();
        });
    }

    if (renamerResetBtn) {
        renamerResetBtn.addEventListener('click', pickExampleFile);
    }

    function inferPattern() {
        if (!currentExampleFile || !renamerNewExample) return;
        const oldName = currentExampleFile.name;
        const newName = renamerNewExample.value.trim();
        if (!newName) {
            if (renamerPreview) renamerPreview.classList.add('d-none');
            return;
        }

        // Find all digit sequences in oldName
        const digitRegex = /\d+/g;
        const matches = [];
        let match;
        while ((match = digitRegex.exec(oldName)) !== null) {
            matches.push({ value: match[0], index: match.index });
        }

        // Create regex pattern from oldName by replacing digit sequences with (\d+)
        // and escaping other characters
        let finalPattern = "";
        let lastIndex = 0;
        matches.forEach(m => {
            finalPattern += oldName.substring(lastIndex, m.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            finalPattern += '(\\d+)';
            lastIndex = m.index + m.value.length;
        });
        finalPattern += oldName.substring(lastIndex).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        // Now create the replacement string
        let replacement = newName;
        
        if (matches.length > 0) {
            // Sort matches by length descending to avoid partial matches (e.g. matching '1' inside '014')
            const uniqueValues = [...new Set(matches.map(m => m.value))].sort((a, b) => b.length - a.length);
            
            // Create a map from value to its first group index
            const valueToGroup = {};
            matches.forEach((m, i) => {
                if (!(m.value in valueToGroup)) {
                    valueToGroup[m.value] = i + 1;
                }
            });

            const combinedRegex = new RegExp(uniqueValues.map(v => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
            replacement = replacement.replace(combinedRegex, (matched) => {
                return `\\${valueToGroup[matched]}`;
            });
        }

        if (renamerPattern) renamerPattern.value = finalPattern;
        if (renamerReplacement) renamerReplacement.value = replacement;
        
        // Run dry run automatically
        runRenamer(true);
    }

    if (renamerNewExample) {
        renamerNewExample.addEventListener('input', () => {
            inferPattern();
            updateRenamerBtn();
        });
    }

    const renamerOrganize = document.getElementById('renamerOrganize');
    if (renamerOrganize) {
        renamerOrganize.addEventListener('change', () => {
            runRenamer(true);
        });
    }

    function filterRenamerTable(showOnlyUnmatched) {
        if (!renamerPreviewBody) return;
        const rows = renamerPreviewBody.querySelectorAll('tr');
        rows.forEach(row => {
            const isMatch = row.getAttribute('data-match') === 'true';
            if (showOnlyUnmatched) {
                row.classList.toggle('d-none', isMatch);
            } else {
                row.classList.remove('d-none');
            }
        });
        
        if (renamerFilterAll) renamerFilterAll.classList.toggle('active', !showOnlyUnmatched);
        if (renamerFilterUnmatched) renamerFilterUnmatched.classList.toggle('active', showOnlyUnmatched);
    }

    if (renamerFilterAll) {
        renamerFilterAll.addEventListener('click', () => filterRenamerTable(false));
    }
    if (renamerFilterUnmatched) {
        renamerFilterUnmatched.addEventListener('click', () => filterRenamerTable(true));
    }

    async function runRenamer(isDryRun) {
        if (!renamerPattern || !renamerReplacement || !renamerPattern.value) return;
        
        renamerError.classList.add('d-none');
        renamerInfo.classList.add('d-none');
        
        const formData = new FormData();
        formData.append('pattern', renamerPattern.value);
        formData.append('replacement', renamerReplacement.value);
        formData.append('dry_run', isDryRun);
        
        const renamerOrganize = document.getElementById('renamerOrganize');
        if (renamerOrganize) {
            formData.append('organize', renamerOrganize.checked);
        }

        if (renamerModality) {
            formData.append('modality', renamerModality.value);
        }
        
        const files = Array.from(renamerFiles.files);
        if (files.length === 0 && !isDryRun) return;
        
        // For dry run, we only send filenames to be faster
        if (isDryRun) {
            files.forEach(f => formData.append('filenames', f.name));
        } else {
            files.forEach(f => formData.append('files', f));
        }
        
        try {
            const response = await fetch('/api/physio-rename', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                throw new Error(data && data.error ? data.error : 'Renaming failed');
            }
            
            const result = await response.json();
            
            if (isDryRun) {
                renamerPreviewBody.innerHTML = '';
                let matchCount = 0;
                const unmatchedFiles = [];
                const selectedModality = renamerModality ? renamerModality.value : 'physio';

                result.results.forEach(res => {
                    const isMatch = res.old !== res.new;
                    
                    // Basic BIDS validation for the new name
                    let isValidBids = true;
                    let bidsError = '';
                    
                    if (isMatch) {
                        if (!res.new.startsWith('sub-')) {
                            isValidBids = false;
                            bidsError = 'Missing sub- prefix';
                        } else if (!res.new.includes('_')) {
                            isValidBids = false;
                            bidsError = 'Missing entities/suffix';
                        } else {
                            // Check suffix
                            const stem = res.new.split('.')[0];
                            const suffix = stem.split('_').pop();
                            const expectedSuffixes = {
                                'physio': 'physio',
                                'biometrics': 'biometrics',
                                'events': 'events',
                                'survey': 'survey'
                            };
                            if (expectedSuffixes[selectedModality] && suffix !== expectedSuffixes[selectedModality]) {
                                isValidBids = false;
                                bidsError = `Expected _${expectedSuffixes[selectedModality]} suffix`;
                            }
                        }
                    }

                    if (isMatch && isValidBids) {
                        matchCount++;
                    } else if (!isMatch) {
                        unmatchedFiles.push(res.old);
                    }
                    
                    const tr = document.createElement('tr');
                    tr.setAttribute('data-match', isMatch && isValidBids);
                    
                    let displayNew = res.new;
                    if (res.path && res.path !== res.new) {
                        displayNew = `<span class="text-muted">${res.path.substring(0, res.path.lastIndexOf('/') + 1)}</span>${res.new}`;
                    }

                    tr.innerHTML = `
                        <td class="font-monospace small">${res.old}</td>
                        <td><i class="fas fa-arrow-right text-muted"></i></td>
                        <td class="font-monospace small ${isMatch ? (isValidBids ? 'text-success' : 'text-danger') : 'text-muted'}">
                            ${displayNew}
                            ${!isValidBids && isMatch ? `<br><small class="text-danger"><i class="fas fa-times-circle me-1"></i>${bidsError}</small>` : ''}
                        </td>
                        <td class="text-center">
                            ${(isMatch && isValidBids) ? '<i class="fas fa-check-circle text-success"></i>' : 
                              (!isMatch ? '<i class="fas fa-exclamation-triangle text-warning" title="No match found - file will not be renamed"></i>' : 
                              '<i class="fas fa-times-circle text-danger" title="Invalid BIDS/PRISM format"></i>')}
                        </td>
                    `;
                    renamerPreviewBody.appendChild(tr);
                });
                renamerPreview.classList.remove('d-none');

                if (matchCount < result.results.length && result.results.length > 0) {
                    const unmatchedCount = result.results.length - matchCount;
                    renamerError.innerHTML = `
                        <div class="d-flex align-items-center">
                            <i class="fas fa-exclamation-triangle me-3 fa-2x"></i>
                            <div>
                                <strong>Warning: ${unmatchedCount} files are either unmatched or invalid.</strong><br>
                                Only files with a green checkmark will be renamed correctly. Check the "New PRISM Filename" column for errors.
                                <div class="mt-2">
                                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="document.getElementById('renamerFilterUnmatched').click()">
                                        <i class="fas fa-search me-1"></i>Show Incompatible Files
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    renamerError.classList.remove('d-none');
                }
                
                // Reset filter to "All" on new dry run
                filterRenamerTable(false);
            } else {
                if (result.zip) {
                    downloadBase64Zip(result.zip, 'renamed_files.zip');
                    renamerInfo.textContent = `Successfully renamed ${result.results.length} files. ZIP download started.`;
                    renamerInfo.classList.remove('d-none');
                }
            }
        } catch (err) {
            if (!isDryRun) {
                renamerError.textContent = err.message;
                renamerError.classList.remove('d-none');
            }
        }
    }

    if (renamerDownloadBtn) {
        renamerDownloadBtn.addEventListener('click', () => runRenamer(false));
    }

    // Toggle chevron icon for global renamer
    const globalRenamerCollapse = document.getElementById('globalRenamerCollapse');
    if (globalRenamerCollapse) {
        globalRenamerCollapse.addEventListener('show.bs.collapse', function () {
            const icon = document.querySelector('[data-bs-target="#globalRenamerCollapse"] i.fa-chevron-down');
            if (icon) icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
        });
        globalRenamerCollapse.addEventListener('hide.bs.collapse', function () {
            const icon = document.querySelector('[data-bs-target="#globalRenamerCollapse"] i.fa-chevron-up');
            if (icon) icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
        });
    }

    // --- Auto-fill library paths from current project ---
    // Store available library paths for quick switching
    const availableConvertPaths = {
        global: null,
        project: null
    };

    // Update source badge display
    function updateConvertLibrarySourceBadge(source) {
        const badge = document.getElementById('convertLibrarySourceBadge');
        const text = document.getElementById('convertLibrarySourceText');
        if (!badge || !text) return;

        if (source) {
            badge.style.display = 'inline-block';
            if (source === 'global') {
                badge.className = 'badge bg-info ms-2';
                text.textContent = 'Global Library';
            } else if (source === 'project') {
                badge.className = 'badge bg-success ms-2';
                text.textContent = 'Project Library';
            } else {
                badge.className = 'badge bg-secondary ms-2';
                text.textContent = 'Custom Path';
            }
        } else {
            badge.style.display = 'none';
        }
    }

    // Determine current source based on path
    function detectConvertLibrarySource() {
        if (!convertLibraryPathInput) return null;
        const currentPath = convertLibraryPathInput.value.trim();
        if (!currentPath) return null;

        // Normalize paths for comparison
        const normalize = p => p.replace(/\\/g, '/').replace(/\/$/, '').toLowerCase();
        const normalizedCurrent = normalize(currentPath);

        if (availableConvertPaths.project && normalize(availableConvertPaths.project) === normalizedCurrent) {
            return 'project';
        }
        if (availableConvertPaths.global && normalize(availableConvertPaths.global) === normalizedCurrent) {
            return 'global';
        }
        return 'custom';
    }

    async function initializeLibraryPathsFromProject() {
        const globalBtn = document.getElementById('convertUseGlobalLibraryBtn');
        const projectBtn = document.getElementById('convertUseProjectLibraryBtn');

        try {
            const response = await fetch('/api/projects/library-path');
            const data = await response.json();

            // Store available paths
            availableConvertPaths.global = data.global_library_path || null;
            availableConvertPaths.project = data.project_library_path || null;

            // Enable/disable quick switch buttons based on availability
            if (globalBtn) {
                if (availableConvertPaths.global) {
                    globalBtn.disabled = false;
                    globalBtn.title = availableConvertPaths.global;
                } else {
                    globalBtn.disabled = true;
                    globalBtn.title = 'No global library configured';
                }
            }

            if (projectBtn) {
                if (availableConvertPaths.project) {
                    projectBtn.disabled = false;
                    projectBtn.title = availableConvertPaths.project;
                } else {
                    projectBtn.disabled = true;
                    projectBtn.title = data.project_path ? 'Project has no library folder' : 'No project selected';
                }
            }

            // Auto-fill with best available path (prefer global for templates)
            if (convertLibraryPathInput && !convertLibraryPathInput.value) {
                let selectedPath = null;
                let selectedSource = null;

                if (availableConvertPaths.global) {
                    selectedPath = availableConvertPaths.global;
                    selectedSource = 'global';
                } else if (availableConvertPaths.project) {
                    selectedPath = availableConvertPaths.project;
                    selectedSource = 'project';
                } else if (data.library_path) {
                    selectedPath = data.library_path;
                    selectedSource = 'custom';
                }

                if (selectedPath) {
                    convertLibraryPathInput.value = selectedPath;
                    updateConvertLibrarySourceBadge(selectedSource);
                    // Trigger language detection
                    refreshConvertLanguages();
                }
            } else {
                // Path already set, detect source
                updateConvertLibrarySourceBadge(detectConvertLibrarySource());
            }

            // Biometrics library path is auto-resolved on the backend

            console.log('Library paths initialized:', {
                global: availableConvertPaths.global,
                project: availableConvertPaths.project
            });
        } catch (err) {
            console.warn('Could not load project library path:', err);
        }

        // Set up click handlers for quick switch buttons
        if (globalBtn) {
            globalBtn.addEventListener('click', function() {
                if (availableConvertPaths.global && convertLibraryPathInput) {
                    convertLibraryPathInput.value = availableConvertPaths.global;
                    updateConvertLibrarySourceBadge('global');
                    refreshConvertLanguages();
                }
            });
        }

        if (projectBtn) {
            projectBtn.addEventListener('click', function() {
                if (availableConvertPaths.project && convertLibraryPathInput) {
                    convertLibraryPathInput.value = availableConvertPaths.project;
                    updateConvertLibrarySourceBadge('project');
                    refreshConvertLanguages();
                }
            });
        }

        // Update source badge when path changes manually
        if (convertLibraryPathInput) {
            convertLibraryPathInput.addEventListener('input', function() {
                updateConvertLibrarySourceBadge(detectConvertLibrarySource());
            });
        }
    }

    // Initial populate
    refreshConvertLanguages();

    // Auto-fill from project (async, doesn't block)
    initializeLibraryPathsFromProject();

    // Listen for library settings changes from other tabs/pages
    window.addEventListener('prism-library-settings-changed', function(event) {
        console.log('Library settings changed, refreshing paths...');
        // Re-initialize library paths to pick up new global/project settings
        initializeLibraryPathsFromProject();
    });
});
