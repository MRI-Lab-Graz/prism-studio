/**
 * Survey Convert Module (Landgig Integration)
 * Handles Excel/LimeSurvey data conversion to PRISM survey format
 * Includes: column detection, ID mapping, preview, participants mapping, validation
 */

import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { createSessionRegistrar } from '../../shared/session-register.js';

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
        downloadSection,
        downloadWarningSection,
        downloadZipBtn,
        downloadZipWarningBtn,
        conversionSummaryContainer,
        conversionSummaryBody,
        toggleSummaryBtn,
        // Shared functions
        downloadBase64Zip,
        populateSessionPickers
    } = elements;

    const convertAdvancedToggle = document.getElementById('convertAdvancedToggle');
    let templateWorkflowGate = null;

    // ---- Survey Version Plan Wizard state ----
    const surveyVersionWizard = document.getElementById('surveyVersionWizard');
    const versionTaskCards = document.getElementById('versionTaskCards');
    const confirmVersionPlanBtn = document.getElementById('confirmVersionPlanBtn');
    const versionPlanSavedMsg = document.getElementById('versionPlanSavedMsg');
    const versionWizardBadge = document.getElementById('versionWizardBadge');

    let pendingMultivariantTasks = null; // set when template check returns multi-variant info
    let versionPlanConfirmed = false;

    function hideVersionWizard() {
        if (surveyVersionWizard) surveyVersionWizard.classList.add('d-none');
        pendingMultivariantTasks = null;
        versionPlanConfirmed = false;
    }

    function _buildVersionOptionHtml(versions, selected, variantDescMap) {
        return versions.map(v =>
            `<option value="${v}"${v === selected ? ' selected' : ''}>${v}${variantDescMap[v] ? ' — ' + variantDescMap[v] : ''}</option>`
        ).join('');
    }

    function _buildOverrideRow(key, ver, versions, kind, variantDescMap) {
        const placeholder = kind === 'session' ? 'e.g. ses-02' : 'e.g. run-02';
        const opts = _buildVersionOptionHtml(versions, ver, variantDescMap);
        return `<div class="d-flex align-items-center gap-2 mb-1 override-row">
            <input type="text" class="form-control form-control-sm override-key" placeholder="${placeholder}" value="${key}" style="max-width:130px">
            <select class="form-select form-select-sm override-version" style="max-width:230px">${opts}</select>
            <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 remove-override" title="Remove">
                <i class="fas fa-times"></i>
            </button>
        </div>`;
    }

    function _buildOverrideRows(mapping, versions, kind, variantDescMap) {
        return Object.entries(mapping).map(([k, v]) => _buildOverrideRow(k, v, versions, kind, variantDescMap)).join('');
    }

    function _attachRemoveListeners(container) {
        if (!container) return;
        container.querySelectorAll('.remove-override').forEach(btn => {
            btn.onclick = () => btn.closest('.override-row').remove();
        });
    }

    function buildVersionWizard(multivariantTasks) {
        if (!surveyVersionWizard || !versionTaskCards) return;
        const tasks = Object.entries(multivariantTasks || {});
        if (tasks.length === 0) { hideVersionWizard(); return; }

        pendingMultivariantTasks = multivariantTasks;
        versionPlanConfirmed = false;
        versionTaskCards.innerHTML = '';

        tasks.forEach(([taskName, info]) => {
            const versions = info.versions || [];
            const currentPlan = info.current_plan || {};
            const existingDefault = currentPlan.default_version || info.default_version || versions[0];
            const bySession = currentPlan.by_session || {};
            const byRun = currentPlan.by_run || {};

            const variantDescMap = {};
            (info.variant_definitions || []).forEach(vd => {
                variantDescMap[vd.VariantID] = (vd.Description && vd.Description.en) || '';
            });

            const alreadyHasOverrides = Object.keys(bySession).length > 0 || Object.keys(byRun).length > 0;
            const versionOpts = _buildVersionOptionHtml(versions, existingDefault, variantDescMap);
            const card = document.createElement('div');
            card.className = 'border rounded p-3 mb-3 bg-light bg-opacity-50';
            card.dataset.task = taskName;

            card.innerHTML = `
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <strong class="text-primary"><i class="fas fa-poll me-1"></i>${taskName}</strong>
                    <span class="badge bg-secondary">${versions.length} versions</span>
                </div>
                <div class="row g-2 mb-2">
                    <div class="col-md-7">
                        <label class="form-label mb-1 small fw-semibold">
                            Which version did you use?
                            <span class="text-muted fw-normal">(default for all sessions &amp; runs)</span>
                        </label>
                        <select class="form-select form-select-sm" data-role="default-version">${versionOpts}</select>
                    </div>
                </div>
                <div class="form-check form-switch mb-2">
                    <input class="form-check-input" type="checkbox" id="override-toggle-${taskName}" ${alreadyHasOverrides ? 'checked' : ''}>
                    <label class="form-check-label small" for="override-toggle-${taskName}">
                        Different version in some sessions or runs
                    </label>
                </div>
                <div class="version-overrides ${alreadyHasOverrides ? '' : 'd-none'} ps-3 border-start border-2 border-primary-subtle mt-2">
                    <div class="mb-2">
                        <div class="d-flex align-items-center mb-1">
                            <span class="small fw-semibold me-2 text-muted">Session overrides</span>
                            <button class="btn btn-outline-secondary btn-sm py-0 px-2 add-session-override" type="button">
                                <i class="fas fa-plus me-1"></i>Add
                            </button>
                        </div>
                        <div class="session-overrides-list">
                            ${_buildOverrideRows(bySession, versions, 'session', variantDescMap)}
                        </div>
                    </div>
                    <div>
                        <div class="d-flex align-items-center mb-1">
                            <span class="small fw-semibold me-2 text-muted">Run overrides</span>
                            <button class="btn btn-outline-secondary btn-sm py-0 px-2 add-run-override" type="button">
                                <i class="fas fa-plus me-1"></i>Add
                            </button>
                        </div>
                        <div class="run-overrides-list">
                            ${_buildOverrideRows(byRun, versions, 'run', variantDescMap)}
                        </div>
                    </div>
                </div>`;

            const toggle = card.querySelector(`#override-toggle-${taskName}`);
            const overrideSection = card.querySelector('.version-overrides');
            toggle.addEventListener('change', () => overrideSection.classList.toggle('d-none', !toggle.checked));

            card.querySelector('.add-session-override').addEventListener('click', () => {
                const list = card.querySelector('.session-overrides-list');
                list.insertAdjacentHTML('beforeend', _buildOverrideRow('', versions[0], versions, 'session', variantDescMap));
                _attachRemoveListeners(list);
            });
            card.querySelector('.add-run-override').addEventListener('click', () => {
                const list = card.querySelector('.run-overrides-list');
                list.insertAdjacentHTML('beforeend', _buildOverrideRow('', versions[0], versions, 'run', variantDescMap));
                _attachRemoveListeners(list);
            });
            _attachRemoveListeners(card.querySelector('.session-overrides-list'));
            _attachRemoveListeners(card.querySelector('.run-overrides-list'));
            versionTaskCards.appendChild(card);
        });

        if (versionWizardBadge) {
            versionWizardBadge.textContent = 'Action required';
            versionWizardBadge.className = 'badge bg-warning text-dark ms-auto';
        }
        if (versionPlanSavedMsg) versionPlanSavedMsg.classList.add('d-none');
        surveyVersionWizard.classList.remove('d-none');
    }

    function collectVersionPlanFromWizard() {
        const mapping = {};
        if (!versionTaskCards) return mapping;
        versionTaskCards.querySelectorAll('[data-task]').forEach(card => {
            const task = card.dataset.task;
            const defaultVersion = card.querySelector('[data-role="default-version"]')?.value || '';
            const toggle = card.querySelector('input[type="checkbox"]');
            const hasOverrides = toggle && toggle.checked;
            const bySession = {}, byRun = {};
            if (hasOverrides) {
                card.querySelector('.session-overrides-list')?.querySelectorAll('.override-row').forEach(row => {
                    const k = row.querySelector('.override-key')?.value.trim();
                    const v = row.querySelector('.override-version')?.value;
                    if (k && v) bySession[k] = v;
                });
                card.querySelector('.run-overrides-list')?.querySelectorAll('.override-row').forEach(row => {
                    const k = row.querySelector('.override-key')?.value.trim();
                    const v = row.querySelector('.override-version')?.value;
                    if (k && v) byRun[k] = v;
                });
            }
            mapping[task] = { default_version: defaultVersion, by_session: bySession, by_run: byRun, by_session_run: {} };
        });
        return mapping;
    }

    if (confirmVersionPlanBtn) {
        confirmVersionPlanBtn.addEventListener('click', async () => {
            const mapping = collectVersionPlanFromWizard();
            if (Object.keys(mapping).length === 0) return;
            confirmVersionPlanBtn.disabled = true;
            try {
                const resp = await fetch('/api/projects/survey-plan/from-import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ survey_version_mapping: mapping }),
                });
                const result = await resp.json();
                if (result.success) {
                    versionPlanConfirmed = true;
                    if (versionWizardBadge) {
                        versionWizardBadge.textContent = 'Saved ✓';
                        versionWizardBadge.className = 'badge bg-success ms-auto';
                    }
                    if (versionPlanSavedMsg) versionPlanSavedMsg.classList.remove('d-none');
                    appendLog('Survey version plan saved to project.json.', 'success');
                    updateConvertBtn();
                } else {
                    appendLog(`Failed to save version plan: ${result.error || 'Unknown error'}`, 'error');
                }
            } catch (e) {
                appendLog(`Version plan save error: ${e.message}`, 'error');
            } finally {
                confirmVersionPlanBtn.disabled = false;
            }
        });
    }

    function setTemplateEditorErrorCtaVisible(visible) {
        if (!templateEditorErrorCta) return;
        templateEditorErrorCta.classList.toggle('d-none', !visible);
    }

    function isAdvancedOptionsEnabled() {
        return Boolean(convertAdvancedToggle && convertAdvancedToggle.checked);
    }

    function applyAdvancedOptionsState() {
        const enabled = isAdvancedOptionsEnabled();

        if (convertDatasetName) {
            convertDatasetName.disabled = !enabled;
            if (!enabled) convertDatasetName.value = '';
        }

        if (convertLanguage) {
            convertLanguage.disabled = !enabled;
            if (!enabled) convertLanguage.value = 'auto';
        }

        if (convertIdMapFile) {
            convertIdMapFile.disabled = !enabled;
            if (!enabled) {
                convertIdMapFile.value = '';
                clearIdMapFileBtn?.classList.add('d-none');
            }
        }

        if (clearIdMapFileBtn) {
            clearIdMapFileBtn.disabled = !enabled;
        }
    }

    if (convertAdvancedToggle) {
        convertAdvancedToggle.addEventListener('change', applyAdvancedOptionsState);
    }

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
        });

        clearIdMapFileBtn?.addEventListener('click', () => {
            convertIdMapFile.value = '';
            updateIdMapClearButtonState();
           convertError?.classList.add('d-none');
            convertError.textContent = '';
        });

        updateIdMapClearButtonState();
    }

    applyAdvancedOptionsState();

    // Library path browser
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
            updateConvertBtn();
        });
    }
    if (convertSessionCustom) {
        convertSessionCustom.addEventListener('input', function() {
            if (this.value && convertSessionSelect) convertSessionSelect.value = '';
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
    }

    async function detectFileColumns(file) {
        const filename = file.name.toLowerCase();
        const idColumnSelect = document.getElementById('convertIdColumn');
        const idColumnStatus = document.getElementById('idColumnStatus');
        const idColumnHelp = document.getElementById('idColumnHelp');
        if (!idColumnSelect) return;

        resetDetectedColumnsState();

        if (filename.endsWith('.lss')) {
            if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-muted">(structure only)</span>';
            if (idColumnHelp) idColumnHelp.innerHTML = '<i class="fas fa-info-circle me-1"></i>.lss files have no response data';
            return;
        }

        if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-info"><i class="fas fa-spinner fa-spin me-1"></i>Loading...</span>';

        if (filename.endsWith('.lsa') || filename.endsWith('.xlsx') || filename.endsWith('.csv') || filename.endsWith('.tsv')) {
            try {
                const formData = new FormData();
                formData.append('file', file);
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
                    } else {
                        if (idColumnStatus) idColumnStatus.innerHTML = '<span class="text-warning">No columns found</span>';
                    }
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
        const hasFile = convertExcelFile.files && convertExcelFile.files.length === 1;
        const blockedByTemplateGate = Boolean(templateWorkflowGate && templateWorkflowGate.blocked);
        const blockedByVersionPlan = Boolean(pendingMultivariantTasks && !versionPlanConfirmed);
        const hasProjectLoaded = resolveCurrentProjectPath() !== '';

        convertBtn.disabled = !hasFile || blockedByTemplateGate || blockedByVersionPlan;
        if (checkProjectTemplatesBtn) {
            checkProjectTemplatesBtn.disabled = !hasProjectLoaded;
            if (!hasProjectLoaded) {
                checkProjectTemplatesBtn.title = 'Load a project first to check local templates.';
            } else {
                checkProjectTemplatesBtn.removeAttribute('title');
            }
        }
        
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
            if (blockedByTemplateGate) {
                convertBtn.title = 'Complete required project template fields first, then run Preview again.';
            } else if (blockedByVersionPlan) {
                convertBtn.title = 'Confirm the survey version plan above before converting.';
            } else {
                convertBtn.removeAttribute('title');
            }
        }

        clearConvertExcelFileBtn?.classList.toggle('d-none', !hasFile);
    }

    convertExcelFile.addEventListener('change', async function() {
        const file = this.files?.[0];
        templateWorkflowGate = null;
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
        setTemplateEditorErrorCtaVisible(false);
        resetConversionUI();

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

        if (sourcedataFileSelect) {
            sourcedataFileSelect.value = '';
        }

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
        convertExcelFile.value = '';
        convertExcelFile.dispatchEvent(new Event('change', { bubbles: true }));
        resetSurveyImportFormState();
    });

    const idColSelect = document.getElementById('convertIdColumn');
    if (idColSelect) {
        idColSelect.addEventListener('change', function() {
            this.classList.remove('border-danger');
            convertError.classList.add('d-none');
            updateConvertBtn();
        });
    }

    if (convertSeparator) {
        convertSeparator.addEventListener('change', async function() {
            const currentFile = convertExcelFile.files && convertExcelFile.files[0];
            if (currentFile && isDelimitedSurveyFilename(currentFile.name.toLowerCase())) {
                await detectFileColumns(currentFile);
            }
        });
    }

    handleModeSwitch();
    updateConvertBtn();

    if (checkProjectTemplatesBtn) {
        checkProjectTemplatesBtn.addEventListener('click', async function() {
            convertError.classList.add('d-none');
            convertError.textContent = '';

            conversionLogContainer.classList.remove('d-none');
            conversionLogBody.classList.remove('d-none');
            const icon = toggleLogBtn.querySelector('i');
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');

            const selectedFile = convertExcelFile.files && convertExcelFile.files[0];
            const selectedIdColumn = (convertIdColumn && convertIdColumn.value && convertIdColumn.value !== 'auto')
                ? convertIdColumn.value
                : '';

            if (selectedFile) {
                appendLog(`Checking official templates against input: ${selectedFile.name}`, 'info');
            }
            appendLog('Checking local project survey templates...', 'info');
            checkProjectTemplatesBtn.disabled = true;

            try {
                const formData = new FormData();
                if (selectedFile) {
                    formData.append('excel', selectedFile);
                }
                if (selectedIdColumn) {
                    formData.append('id_column', selectedIdColumn);
                }
                formData.append('separator', getSelectedSeparator(selectedFile ? selectedFile.name.toLowerCase() : ''));

                const response = await fetch('/api/survey-check-project-templates', {
                    method: 'POST',
                    body: formData,
                });
                const data = await response.json();

                if (!response.ok) {
                    if (data.error === 'id_column_required') {
                        if (convertIdColumn) {
                            convertIdColumn.classList.add('border-danger');
                            convertIdColumn.focus();
                        }
                        throw new Error('Please select a participant ID column, then run template check again.');
                    }
                    throw new Error(data.error || 'Template check could not be completed');
                }

                const templateCount = Number.isFinite(data.template_count) ? data.template_count : 0;
                const tasks = Array.isArray(data.tasks) ? data.tasks : [];
                const localTemplates = Array.isArray(data.local_templates) ? data.local_templates : [];
                const templateWarnings = Array.isArray(data.warnings) ? data.warnings : [];
                const matching = (data && typeof data.matching === 'object' && data.matching)
                    ? data.matching
                    : null;

                if (matching && matching.input_file) {
                    const officialCount = Number.isFinite(matching.official_template_count)
                        ? matching.official_template_count
                        : 0;
                    appendLog(`Official templates available: ${officialCount}`, 'info');

                    const matchedTasks = Array.isArray(matching.matched_tasks) ? matching.matched_tasks : [];
                    if (matchedTasks.length > 0) {
                        appendLog(`Official templates matched from input: ${matchedTasks.join(', ')}`, 'success');
                    } else {
                        appendLog('No official template matches were detected from the selected input file.', 'warning');
                    }

                    const copiedTasks = Array.isArray(matching.copied_tasks) ? matching.copied_tasks : [];
                    if (copiedTasks.length > 0) {
                        appendLog(`Copied to project library: ${copiedTasks.join(', ')}`, 'info');
                    }

                    const existingTasks = Array.isArray(matching.existing_tasks) ? matching.existing_tasks : [];
                    if (existingTasks.length > 0) {
                        appendLog(`Already present in project library: ${existingTasks.join(', ')}`, 'info');
                    }

                    const missingOfficial = Array.isArray(matching.missing_official_tasks)
                        ? matching.missing_official_tasks
                        : [];
                    if (missingOfficial.length > 0) {
                        appendLog(`Not found in official library by task name: ${missingOfficial.join(', ')}`, 'warning');
                    }

                    if (matching.match_error) {
                        appendLog(`Template matching note: ${matching.match_error}`, 'warning');
                    }
                }

                appendLog(`Local templates found (${templateCount}): ${localTemplates.length ? localTemplates.join(', ') : '(none)'}`, 'info');
                if (tasks.length) {
                    appendLog(`Tasks covered: ${tasks.join(', ')}`, 'info');
                }
                if (templateWarnings.length) {
                    appendLog(`Template quality warnings: ${templateWarnings.length}`, 'warning');
                    templateWarnings.slice(0, 30).forEach(warn => {
                        const fileName = (warn.file || '').split('/').pop() || 'template';
                        appendLog(`  - ${fileName}: ${warn.message}`, 'warning');
                    });
                    if (templateWarnings.length > 30) {
                        appendLog(`  ... and ${templateWarnings.length - 30} more warning(s)`, 'warning');
                    }
                }

                if (data.ok) {
                    templateWorkflowGate = null;
                    setTemplateEditorErrorCtaVisible(false);
                    appendLog('Project template check passed.', 'success');
                    convertInfo.innerHTML = '<i class="fas fa-check-circle me-2"></i>Project templates look good. Continue with Preview (Dry-Run).';
                    convertInfo.classList.remove('d-none');
                } else {                    templateWorkflowGate = data.workflow_gate || {
                        blocked: true,
                        message: data.message || 'Project templates require completion before import.'
                    };
                    setTemplateEditorErrorCtaVisible(true);

                    appendLog('Template check found templates that still need project-level fields.', 'warning');
                    appendLog(`  ${templateWorkflowGate.message}`, 'warning');
                    if (Array.isArray(templateWorkflowGate.next_steps)) {
                        templateWorkflowGate.next_steps.forEach(step => appendLog(`  - ${step}`, 'warning'));
                    }

                    const issues = Array.isArray(data.issues) ? data.issues : [];
                    issues.slice(0, 30).forEach(issue => {
                        const fileName = (issue.file || '').split('/').pop() || 'template';
                        appendLog(`  - ${fileName}: ${issue.message}`, 'warning');
                    });
                    if (issues.length > 30) {
                        appendLog(`  ... and ${issues.length - 30} more item(s)`, 'warning');
                    }

                    convertInfo.innerHTML = '<i class="fas fa-clipboard-check me-2"></i>Some copied survey templates still need project-level metadata. Complete them in Template Editor, then run Preview again.';
                    convertInfo.classList.remove('d-none');
                }

                // Show version plan wizard for any detected multi-variant questionnaires
                const mvTasks = (data && typeof data.multivariant_tasks === 'object' && data.multivariant_tasks)
                    ? data.multivariant_tasks : {};
                if (Object.keys(mvTasks).length > 0) {
                    buildVersionWizard(mvTasks);
                    appendLog(`Multi-version questionnaire(s) detected: ${Object.keys(mvTasks).join(', ')}. Please confirm the version plan below.`, 'warning');
                } else {
                    hideVersionWizard();
                }
            } catch (err) {
                appendLog(`Template check error: ${err.message}`, 'error');
                convertError.textContent = err.message;
                convertError.classList.remove('d-none');
                setTemplateEditorErrorCtaVisible(true);
            } finally {
                updateConvertBtn();
            }
        });
    }

    // Sourcedata quick-select
    if (sourcedataQuickSelect && sourcedataFileSelect) {
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
            .catch(() => {});

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
                convertExcelFile.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (err) {
                console.error('Failed to load sourcedata file:', err);
                convertError.textContent = `Failed to load ${filename} from sourcedata.`;
convertError.classList.remove('d-none');
            }
        });
    }

    let currentZipBlob = null;

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
        const line = document.createElement('span');
        line.style.color = color;
        line.textContent = `[${timestamp}] ${String(message)}`;
        targetLog.appendChild(line);
        targetLog.appendChild(document.createTextNode('\n'));
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

        const toolCols = summary.tool_columns;
        if (toolCols && toolCols.length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-wrench me-1"></i>Tool-Specific Columns <span class="badge bg-secondary">${toolCols.length}</span></h6>`;
            html += `<div class="mb-3"><details><summary class="text-muted small" style="cursor:pointer;">LimeSurvey system columns (click to expand)</summary>`;
            html += `<div class="mt-1"><code>${toolCols.join('</code>, <code>')}</code></div></details></div>`;
        }

        const unknownCols = summary.unknown_columns;
        if (unknownCols && unknownCols.length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-question-circle me-1 text-warning"></i>Unmatched Columns <span class="badge bg-warning text-dark">${unknownCols.length}</span></h6>`;
            html += `<div class="mb-1"><code>${unknownCols.join('</code>, <code>')}</code></div>`;
            html += `<small class="text-muted">These columns were not assigned to any template.</small>`;
        }

        if (html) {
            conversionSummaryBody.innerHTML = html;
            conversionSummaryContainer.classList.remove('d-none');

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
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
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
            if (m.overlap_count !==undefined) details.push(`${m.overlap_count}/${m.template_items} items match`);
            if (m.levels_match === true) details.push('levels verified');
            const matchDiv = document.createElement('div');
            matchDiv.id = 'templateSingleMatch';
            matchDiv.className = 'alert alert-info py-2 mt-2 mb-0';
            const srcLabel = m.source === 'project' ? 'project template' : 'library template';
            const srcIcon = m.source === 'project' ? 'fa-folder' : 'fa-globe';
            const leadIcon = document.createElement('i');
            leadIcon.className = `fas ${icon} me-1`;
            matchDiv.appendChild(leadIcon);

            const confidenceBadge = document.createElement('span');
            confidenceBadge.className = `badge ${badgeClass} me-2`;
            confidenceBadge.textContent = m.confidence || 'unknown';
            matchDiv.appendChild(confidenceBadge);

            matchDiv.appendChild(document.createTextNode(`Matches ${srcLabel}: `));
            const strong = document.createElement('strong');
            strong.textContent = m.template_key || '';
            matchDiv.appendChild(strong);
            matchDiv.appendChild(document.createTextNode(' '));

            const sourceBadge = document.createElement('span');
            sourceBadge.className = 'badge bg-light text-dark border ms-1';
            const sourceBadgeIcon = document.createElement('i');
            sourceBadgeIcon.className = `fas ${srcIcon} me-1`;
            sourceBadge.appendChild(sourceBadgeIcon);
            sourceBadge.appendChild(document.createTextNode(m.source === 'project' ? 'project' : 'library'));
            matchDiv.appendChild(sourceBadge);

            const detailText = details.join(', ');
            if (detailText) {
                matchDiv.appendChild(document.createTextNode(` (${detailText})`));
            }
            if (actionLabel) {
                matchDiv.appendChild(document.createTextNode(' — '));
                const em = document.createElement('em');
                em.textContent = actionLabel;
                matchDiv.appendChild(em);
            }
            container.querySelector('.alert')?.after(matchDiv);
        } else if (m === null) {
            const matchDiv = document.createElement('div');
            matchDiv.id = 'templateSingleMatch';
            matchDiv.className = 'alert alert-light py-2 mt-2 mb-0 border';
            const iconEl = document.createElement('i');
            iconEl.className = 'fas fa-plus-circle me-1';
            matchDiv.appendChild(iconEl);
            matchDiv.appendChild(document.createTextNode('No matching library template found — this will be a new template.'));
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
                    const safeName = escapeHtml(name || '');
                    const safeTemplateKey = escapeHtml(m.template_key || '');
                    const safeDetailStr = escapeHtml(detailStr);
                    const safeSourceLabel = escapeHtml(sourceLabel);
                    const safeConfidence = escapeHtml(m.confidence || 'unknown');
                    // Don't show "Use library version" for participants matches - there's no participants template in the library
                    const useLibBtn = (m.suggested_action === 'use_library' && !m.is_participants)
                        ? `<button class="btn btn-sm btn-outline-primary use-library-btn mt-1" data-name="${safeName}" data-template-key="${safeTemplateKey}" data-is-participants="${m.is_participants || false}"><i class="fas fa-book me-1"></i>Use ${safeSourceLabel} version</button>`
                        : '';
                    matchHtml = `
                        <div class="mt-1 pt-1 border-top">
                            <span class="badge ${badgeClass}" title="${safeDetailStr}">
                                <i class="fas ${icon} me-1"></i>${safeConfidence} match: ${safeTemplateKey}
                            </span>
                            <span class="badge bg-light text-dark border ms-1" title="Matched from ${safeSourceLabel}">
                                <i class="fas ${sourceIcon} me-1"></i>${safeSourceLabel}
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

                const safeName = escapeHtml(name || '');
                const safeQuestionCount = escapeHtml(String(info.question_count ?? ''));
                card.innerHTML = `
                    <div class="card h-100">
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${safeName}</strong>
                                    <small class="d-block text-muted">${safeQuestionCount} questions</small>
                                </div>
                                <button class="btn btn-sm btn-outline-success download-template-btn" data-name="${safeName}">
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
                            const matchDiv = btn.closest('.border-top');
                            if (matchDiv) {
                                matchDiv.replaceChildren();
                                const badge = document.createElement('span');
                                badge.className = 'badge bg-success';
                                const badgeIcon = document.createElement('i');
                                badgeIcon.className = 'fas fa-check-circle me-1';
                                badge.appendChild(badgeIcon);
                                badge.appendChild(document.createTextNode(`Using library: ${templateKey || ''}`));
                                matchDiv.appendChild(badge);

                                const filenameEl = document.createElement('small');
                                filenameEl.className = 'd-block text-muted mt-1';
                                filenameEl.textContent = result.filename || '';
                                matchDiv.appendChild(filenameEl);
                            }
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
                const heading = document.createElement('h6');
                heading.className = 'text-muted';
                heading.textContent = groupName;
                groupDiv.appendChild(heading);
                listEl.appendChild(groupDiv);

                for (const q of groupInfo.questions || []) {
                    const qData = data.questions[q.code];
                    if (!qData) continue;

                    const card = document.createElement('div');
                    card.className = 'col-md-3';

                    const cardInner = document.createElement('div');
                    cardInner.className = 'card h-100';
                    const cardBody = document.createElement('div');
                    cardBody.className = 'card-body py-2';
                    const row = document.createElement('div');
                    row.className = 'd-flex justify-content-between align-items-center';

                    const textWrap = document.createElement('div');
                    const strong = document.createElement('strong');
                    strong.textContent = q.code || '';
                    textWrap.appendChild(strong);
                    const small = document.createElement('small');
                    small.className = 'd-block text-muted';
                    small.textContent = `${q.type || ''} (${String(q.item_count ?? '')} items)`;
                    textWrap.appendChild(small);

                    const button = document.createElement('button');
                    button.className = 'btn btn-sm btn-outline-success download-q-btn';
                    button.dataset.code = q.code || '';
                    const buttonIcon = document.createElement('i');
                    buttonIcon.className = 'fas fa-download';
                    button.appendChild(buttonIcon);

                    row.appendChild(textWrap);
                    row.appendChild(button);
                    cardBody.appendChild(row);
                    cardInner.appendChild(cardBody);
                    card.appendChild(cardInner);
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
            const safeCode = escapeHtml(field.code || '');
            const safeDescription = escapeHtml(field.description || '');
            const safeType = escapeHtml(field.type || 'text');
            const safeGroup = field.group ? escapeHtml(field.group) : '';
            const safeSuggestedMapping = suggestedMapping ? escapeHtml(suggestedMapping) : '';
            html += `
                <label class="list-group-item list-group-item-action py-2 d-flex align-items-center">
                    <input type="checkbox" class="form-check-input me-2 participant-field-checkbox"
                           data-code="${safeCode}" data-description="${safeDescription}"
                           data-type="${safeType}">
                    <div class="flex-grow-1">
                        <code class="me-2">${safeCode}</code>
                        <small class="text-muted">${safeDescription || safeType || ''}</small>
                        ${safeGroup ? `<span class="badge bg-light text-dark ms-2">${safeGroup}</span>` : ''}
                    </div>
                    ${suggestedMapping ? `
                        <select class="form-select form-select-sm bids-mapping-select" style="width: 140px;" data-code="${safeCode}">
                            <option value="">Map to...</option>
                            <option value="${safeSuggestedMapping}" selected>${safeSuggestedMapping}</option>
                            <option value="participant_id">participant_id</option>
                            <option value="age">age</option>
                            <option value="sex">sex</option>
                            <option value="handedness">handedness</option>
                            <option value="custom">Custom name</option>
                        </select>
                    ` : `
                        <select class="form-select form-select-sm bids-mapping-select" style="width: 140px;" data-code="${safeCode}">
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
            schema[fieldName]._sourceField = code;
        }

        return schema;
    }

    function mergeSurveyParticipantsSchema(existingSchema, selectedSchema) {
        const safeExisting = (existingSchema && typeof existingSchema === 'object') ? { ...existingSchema } : {};
        const safeSelected = (selectedSchema && typeof selectedSchema === 'object') ? selectedSchema : {};

        const selectedSourceFields = new Set(
            Object.values(safeSelected)
                .map(v => (v && typeof v === 'object') ? String(v._sourceField || '').trim() : '')
                .filter(v => v.length > 0)
        );

        const selectedTargetFields = new Set(Object.keys(safeSelected));

        // Start from existing schema and remove stale survey-derived fields that are no longer selected.
        const merged = { ...safeExisting };
        Object.entries(merged).forEach(([fieldName, fieldSpec]) => {
            if (!fieldSpec || typeof fieldSpec !== 'object') return;
            const sourceField = String(fieldSpec._sourceField || '').trim();
            if (!sourceField) return;
            const stillSelectedBySource = selectedSourceFields.has(sourceField);
            const stillSelectedByTarget = selectedTargetFields.has(fieldName);
            if (!stillSelectedBySource && !stillSelectedByTarget) {
                delete merged[fieldName];
            }
        });

        // Apply currently selected fields while preserving manually curated metadata
        // (e.g., Annotations/Levels edits) for fields that remain selected.
        Object.entries(safeSelected).forEach(([fieldName, selectedSpec]) => {
            const existingSpec = merged[fieldName];
            if (existingSpec && typeof existingSpec === 'object') {
                merged[fieldName] = {
                    ...existingSpec,
                    ...selectedSpec,
                };
            } else {
                merged[fieldName] = selectedSpec;
            }
        });

        if (!merged.participant_id) {
            merged.participant_id = { Description: 'Unique participant identifier' };
        }

        return merged;
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

                    // Merge selected fields into existing schema while removing stale
                    // survey-mapped fields that are no longer selected.
                    const mergedSchema = mergeSurveyParticipantsSchema(existingSchema, schema);

                    // Save merged schema
                    const response = await fetch('/api/projects/participants', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ schema: mergedSchema })
                    });
                    const result = await response.json();

                    if (result.success) {
                        statusDiv.replaceChildren();
                        const text = document.createElement('span');
                        text.className = 'text-success';
                        const icon = document.createElement('i');
                        icon.className = 'fas fa-check-circle me-1';
                        text.appendChild(icon);
                        text.appendChild(document.createTextNode(`Saved ${Object.keys(schema).length} fields to participants.json!`));
                        statusDiv.appendChild(text);
                    } else {
                        statusDiv.replaceChildren();
                        const text = document.createElement('span');
                        text.className = 'text-danger';
                        const icon = document.createElement('i');
                        icon.className = 'fas fa-exclamation-circle me-1';
                        text.appendChild(icon);
                        text.appendChild(document.createTextNode(result.error || 'Failed to save participants schema'));
                        statusDiv.appendChild(text);
                    }
                } catch (e) {
                    statusDiv.replaceChildren();
                    const text = document.createElement('span');
                    text.className = 'text-danger';
                    const icon = document.createElement('i');
                    icon.className = 'fas fa-exclamation-circle me-1';
                    text.appendChild(icon);
                    text.appendChild(document.createTextNode(e.message || 'Error'));
                    statusDiv.appendChild(text);
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

    // ===== MAIN CONVERT HANDLER =====

    let currentTemplateData = null;

    convertBtn.addEventListener('click', async function() {
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');
        convertError.textContent = '';
        setTemplateEditorErrorCtaVisible(false);
        convertInfo.textContent = '';
        resetConversionUI();
        templateWorkflowGate = null;

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
        const idMap = isAdvancedOptionsEnabled() && convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
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
        if (isAdvancedOptionsEnabled() && convertDatasetName && convertDatasetName.value.trim()) {
            formData.append('survey', convertDatasetName.value.trim());
        }

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
        appendLog('Output will be saved to project folder', 'step');

        // Add ID column if selected
        if (idColumnVal && idColumnVal !== 'auto' && idColumnVal !== '') {
            formData.append('id_column', idColumnVal);
            appendLog(`Using ID column: ${idColumnVal}`, 'step');
        }

        formData.append('session', sessionVal);
        appendLog(`Forcing session ID: ${sessionVal}`, 'step');

        formData.append('language', (isAdvancedOptionsEnabled() && convertLanguage) ? convertLanguage.value : 'auto');
        formData.append('separator', getSelectedSeparator(filename));
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
                    if (data.error === 'project_template_completion_required') {
                        templateWorkflowGate = data.workflow_gate || {
                            blocked: true,
                            message: data.message || 'Project templates must be completed before import can continue.'
                        };
                        setTemplateEditorErrorCtaVisible(true);

                        appendLog('Template metadata updates are required before import.', 'warning');
                        appendLog(`   ${templateWorkflowGate.message}`, 'warning');
                        if (Array.isArray(templateWorkflowGate.next_steps)) {
                            templateWorkflowGate.next_steps.forEach(step => appendLog(`   • ${step}`, 'warning'));
                        }
                        if (Array.isArray(data.template_issues) && data.template_issues.length) {
                            data.template_issues.slice(0, 20).forEach(issue => {
                                const name = (issue.file || '').split('/').pop() || 'template';
                                appendLog(`   - ${name}: ${issue.message}`, 'warning');
                            });
                            if (data.template_issues.length > 20) {
                                appendLog(`   ... and ${data.template_issues.length - 20} more template item(s)`, 'warning');
                            }
                        }

                        convertInfo.innerHTML = '<i class="fas fa-clipboard-check me-2"></i>Some copied survey templates still need project-level metadata. Complete them in Template Editor, then run Preview again.';
                        convertInfo.classList.remove('d-none');
                        return null;
                    }
                    templateWorkflowGate = null;
                    setTemplateEditorErrorCtaVisible(false);
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
                setTemplateEditorErrorCtaVisible(errorCount > 0);

                if (errorCount === 0 && warningCount === 0) {
                    appendLog('✓ Validation passed - dataset is valid!', 'success');
                } else if (errorCount === 0) {
                    appendLog(`⚠ Validation passed with ${warningCount} warning(s)`, 'warning');
                } else {
                    appendLog(`Validation found ${errorCount} error(s)`, 'error');
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
                appendLog('✓ Data saved to project folder', 'success');
            } else if (data.blob) {
                currentZipBlob = data.blob;
                appendLog('✓ Data saved to project folder', 'success');
            }

            // Final completion message
            appendLog('═══════════════════════════════════════════════', 'info');
            appendLog('✓ Conversion completed successfully', 'success');
            appendLog('═══════════════════════════════════════════════', 'info');

            convertInfo.textContent = 'Conversion complete. See results below.';
            convertInfo.classList.remove('d-none');
        })
        .catch(err => {
            appendLog(`Error: ${err.message}`, 'error');
            convertError.textContent = err.message;
            convertError.classList.remove('d-none');
            setTemplateEditorErrorCtaVisible(Boolean(templateWorkflowGate && templateWorkflowGate.blocked));
        })
        .finally(() => {
            updateConvertBtn();
        });
    });

    // ===== PREVIEW HANDLER (DRY-RUN) =====

    previewBtn.addEventListener('click', async function() {
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');
        convertError.textContent = '';
        setTemplateEditorErrorCtaVisible(false);
        convertInfo.textContent = '';
        resetConversionUI();

        const file = convertExcelFile.files && convertExcelFile.files[0];
        if (!file) {
            return;
        }

        // Validate ID map before sending
        const idMap = isAdvancedOptionsEnabled() && convertIdMapFile && convertIdMapFile.files && convertIdMapFile.files[0];
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

        formData.append('language', (isAdvancedOptionsEnabled() && convertLanguage) ? convertLanguage.value : 'auto');
        formData.append('separator', getSelectedSeparator(file.name.toLowerCase()));
        if (isAdvancedOptionsEnabled() && convertDatasetName && convertDatasetName.value.trim()) {
            formData.append('survey', convertDatasetName.value.trim());
        }

        // Default: run validation in preview
        formData.append('validate', 'true');
        templateWorkflowGate = null;

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
        previewBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Running…';
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
                templateWorkflowGate = null;
                setTemplateEditorErrorCtaVisible(false);
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
            const totalFilesToCreate =
                preview.summary.total_files ??
                preview.summary.files_created ??
                (Array.isArray(preview.files_to_create) ? preview.files_to_create.length : 'n/a');
            appendLog(`   Total files to create: ${totalFilesToCreate}`, 'info');
            appendLog('', 'info');

            // Display conversion summary (template matches, tool columns, unmatched) before validation
            if (data.conversion_summary) {
                displayConversionSummary(data.conversion_summary);
            }

            if (data.workflow_gate && data.workflow_gate.blocked) {
                templateWorkflowGate = data.workflow_gate;
                setTemplateEditorErrorCtaVisible(true);
                appendLog('Template metadata updates are required before import.', 'warning');
                appendLog(`   ${data.workflow_gate.message}`, 'warning');
                if (Array.isArray(data.workflow_gate.next_steps)) {
                    data.workflow_gate.next_steps.forEach(step => appendLog(`   • ${step}`, 'warning'));
                }
            } else {
                templateWorkflowGate = null;
                setTemplateEditorErrorCtaVisible(false);
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
                appendLog(`Data issues found (${preview.data_issues.length})`, 'warning');
                appendLog('   Fix these issues before conversion:', 'warning');
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
                appendLog('✓ No data issues detected', 'success');
                appendLog('', 'info');
            }

            if (typeof window.setParticipantsAdditionalVariablesEnabled === 'function') {
                window.setParticipantsAdditionalVariablesEnabled(false);
            }

            // Display participants.tsv preview
            if (preview.participants_tsv && Object.keys(preview.participants_tsv).length > 0) {
                const tsv = preview.participants_tsv;
                window.lastPreviewData = preview;
                const hasAdditionalVariableCandidates = Boolean(tsv.unused_columns && tsv.unused_columns.length > 0);
                if (typeof window.setParticipantsAdditionalVariablesEnabled === 'function') {
                    window.setParticipantsAdditionalVariablesEnabled(hasAdditionalVariableCandidates);
                }
                
                appendLog('📝 PARTICIPANTS.TSV PREVIEW', 'info');
                appendLog('   This file will be created with the following structure:', 'info');
                appendLog('', 'info');
                
                appendLog(`   Columns (${tsv.columns.length} total):`, 'info');
                tsv.columns.forEach(col => {
                    appendLog(`     • ${col}`, 'info');
                });
                
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
                
                if (tsv.sample_rows.length > 0) {
                    appendLog('', 'info');
                    const sampleCount = Math.min(5, tsv.sample_rows.length);
                    appendLog(`   Sample Data (showing first ${sampleCount} of ${tsv.total_rows} participants):`, 'info');
                    appendLog(`   ${'-'.repeat(100)}`, 'info');
                    const header = tsv.columns.map(col => col.padEnd(20)).join(' | ');
                    appendLog(`   ${header}`, 'info');
                    appendLog(`   ${'-'.repeat(100)}`, 'info');
                    tsv.sample_rows.slice(0, 5).forEach(rowData => {
                        const row = tsv.columns.map(col => String(rowData[col] || 'n/a').padEnd(20)).join(' | ');
                        appendLog(`   ${row}`, 'info');
                    });
                    if (tsv.sample_rows.length > 5) {
                        appendLog(`   ... and ${tsv.sample_rows.length - 5} more rows shown above (total ${tsv.total_rows} participants)`, 'info');
                    }
                    appendLog(`   ${'-'.repeat(100)}`, 'info');
                }
                
                if (tsv.notes.length > 0) {
                    appendLog('', 'info');
                    appendLog('   📌 Notes:', 'info');
                    tsv.notes.forEach(note => {
                        appendLog(`     • ${note}`, 'info');
                    });
                }
                
                if (tsv.unused_columns && tsv.unused_columns.length > 0) {
                    appendLog('', 'info');
                    appendLog(`   Unused columns (${tsv.unused_columns.length} available for participants.tsv):`, 'warning');
                    appendLog(`      These columns are not being imported as survey data and could be included`, 'warning');
                    appendLog(`      in participants.tsv if you create/update participants_mapping.json:`, 'warning');
                    tsv.unused_columns.slice(0, 10).forEach(item => {
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
            
            let previewErrorCount = 0;
            let previewWarningCount = 0;
            
            if (data.validation) {
                if (data.validation.summary) {
                    previewErrorCount = data.validation.summary.total_errors || 0;
                    previewWarningCount = data.validation.summary.total_warnings || 0;
                } else if (data.validation.errors && Array.isArray(data.validation.errors)) {
                    previewErrorCount = data.validation.errors.length;
                }
                if (data.validation.warnings && Array.isArray(data.validation.warnings)) {
                    previewWarningCount = (previewWarningCount || 0) + data.validation.warnings.length;
                }
                if (data.validation.error) {
                    previewErrorCount++;
                }
            }
            
            const dataIssueCount = preview.data_issues ? preview.data_issues.length : 0;
            if (dataIssueCount > 0) {
                previewWarningCount += dataIssueCount;
            }
            
            console.log(`Counts - Errors: ${previewErrorCount}, Warnings: ${previewWarningCount}`);
            
            if (templateWorkflowGate && templateWorkflowGate.blocked) {
                appendLog('Preview paused: update copied template metadata first.', 'warning');
                appendLog(`   ${templateWorkflowGate.issue_count || previewErrorCount || 1} template item(s) need edits before import`, 'warning');
                convertInfo.innerHTML = '<i class="fas fa-clipboard-check me-2"></i>Some copied survey templates still need project-level metadata. Complete them in Template Editor, then run Preview again.';
                setTemplateEditorErrorCtaVisible(true);
            } else if (previewErrorCount > 0) {
                appendLog('Preview complete: validation issues found.', 'warning');
                appendLog(`   ${previewErrorCount} error(s) must be fixed before converting`, 'error');
                if (previewWarningCount > 0) {
                    appendLog(`   ${previewWarningCount} warning(s)`, 'warning');
                }
                if (dataIssueCount > 0) {
                    appendLog(`   ${dataIssueCount} data issue(s)`, 'warning');
                }
                convertInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Preview completed, but validation found errors. Fix these issues before converting.';
                setTemplateEditorErrorCtaVisible(true);
            } else if (previewWarningCount > 0 || dataIssueCount > 0) {
                appendLog('✓ Preview completed (with warnings)', 'warning');
                if (previewWarningCount > 0) {
                    appendLog(`   ${previewWarningCount} warning(s) - review recommended`, 'warning');
                }
                if (dataIssueCount > 0) {
                    appendLog(`   ${dataIssueCount} data issue(s)`, 'warning');
                }
                convertInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Preview completed with warnings. Review above before converting.';
                setTemplateEditorErrorCtaVisible(false);
            } else {
                appendLog('✓ Preview completed successfully', 'success');
                convertInfo.innerHTML = '<i class="fas fa-info-circle me-2"></i>Preview complete. Review the log above, then click <strong>Convert</strong> to proceed.';
                setTemplateEditorErrorCtaVisible(false);
            }
            appendLog('═══════════════════════════════════════', 'info');

            // Show version plan wizard for multi-variant questionnaires detected during preview
            const mvTasks = (data && typeof data.multivariant_tasks === 'object' && data.multivariant_tasks)
                ? data.multivariant_tasks : {};
            if (Object.keys(mvTasks).length > 0) {
                buildVersionWizard(mvTasks);
                appendLog(`Multi-version questionnaire(s) detected: ${Object.keys(mvTasks).join(', ')}. Please confirm the version plan below.`, 'warning');
            } else {
                hideVersionWizard();
            }

            convertInfo.classList.remove('d-none');
        })
        .catch(err => {
            appendLog(`Error: ${err.message}`, 'error');
            convertError.textContent = err.message;
            convertError.classList.remove('d-none');
            setTemplateEditorErrorCtaVisible(Boolean(templateWorkflowGate && templateWorkflowGate.blocked));
        })
        .finally(() => {
            previewBtn.innerHTML = '<i class="fas fa-eye me-2"></i>Preview (Dry-Run)';
            updateConvertBtn();
        });
    });
}
