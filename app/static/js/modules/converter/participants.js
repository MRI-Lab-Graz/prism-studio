import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { escapeHtml } from '../../shared/dom.js';

export function initParticipants() {
    const participantsPanel = document.getElementById('participants-panel');
    if (!participantsPanel) return;
    const neurobagelWidgetUrl = participantsPanel.dataset.neurobagelWidgetUrl || '/static/neurobagel_widget.html';
    const jsonEditorUrl = participantsPanel.dataset.jsonEditorUrl || '/json-editor';
    // Track whether preview has been completed
    let participantsPreviewCompleted = false;
    let participantsExcelSheetCount = null;
    let participantsShowSheetSelector = null;
    let participantsSheetMetadataPending = false;
    
    function updateParticipantsSelectedFileName() {
        const fileInput = document.getElementById('participantsDataFile');
        const fileNameField = document.getElementById('participantsSelectedFileName');
        if (!fileNameField) return;
    
        const selected = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0].name : '';
        fileNameField.value = selected || 'No file selected';
    }
    
    function resetParticipantsPanelState() {
        participantsPreviewCompleted = false;
        participantsExcelSheetCount = null;
        participantsShowSheetSelector = null;
        participantsSheetMetadataPending = false;
    
        const previewResults = document.getElementById('participantsPreviewResults');
        const schemaPreview = document.getElementById('neurobagelSchemaPreview');
        const conversionProgress = document.getElementById('participantsConversionProgress');
        const conversionLog = document.getElementById('participantsConversionLog');
        const errorDiv = document.getElementById('participantsError');
        const infoDiv = document.getElementById('participantsInfo');
        const successDiv = document.getElementById('participantsSuccess');
        const availabilityInfo = document.getElementById('participantsPreviewAvailabilityInfo');
        const warningDiv = document.getElementById('participantsExistingFilesWarning');
        const workflowSummary = document.getElementById('participantsWorkflowSummary');
        const forceOverwrite = document.getElementById('participantsForceOverwrite');
        const convertBtn = document.getElementById('participantsConvertBtn');
        const convertHint = document.getElementById('convertBtnHint');
        const saveAnnotBtn = document.getElementById('saveNeurobagelBtn');
        const previewTableHead = document.querySelector('#participantsPreviewTable thead');
        const previewTableBody = document.querySelector('#participantsPreviewTable tbody');
        const previewCount = document.getElementById('participantsPreviewCount');
        const schemaJsonCode = document.getElementById('schemaJsonCode');
        const sheetInput = document.getElementById('participantsSheet');
        const separator = document.getElementById('participantsSeparator');
        const idGroup = document.getElementById('participantsIdColumnGroup');
    
        if (previewResults) previewResults.classList.add('d-none');
        if (schemaPreview) schemaPreview.classList.add('d-none');
        if (conversionProgress) conversionProgress.classList.add('d-none');
        if (conversionLog) conversionLog.innerHTML = '';
        if (errorDiv) {
            errorDiv.classList.add('d-none');
            errorDiv.textContent = '';
        }
        if (infoDiv) {
            infoDiv.classList.add('d-none');
            infoDiv.innerHTML = '';
        }
        if (successDiv) {
            successDiv.classList.add('d-none');
            successDiv.innerHTML = '';
        }
        if (availabilityInfo) availabilityInfo.classList.add('d-none');
        if (warningDiv) warningDiv.classList.add('d-none');
        if (workflowSummary) workflowSummary.classList.add('d-none');
        if (forceOverwrite) forceOverwrite.checked = false;
    
        if (convertBtn) {
            convertBtn.disabled = true;
            convertBtn.classList.remove('btn-success');
            convertBtn.classList.add('btn-outline-secondary');
        }
        if (convertHint) convertHint.textContent = 'Run step 1 first';
        if (saveAnnotBtn) saveAnnotBtn.disabled = true;
    
        if (previewTableHead) previewTableHead.innerHTML = '';
        if (previewTableBody) previewTableBody.innerHTML = '';
        if (previewCount) previewCount.textContent = '0 participants';
        if (schemaJsonCode) schemaJsonCode.textContent = '';
    
        if (sheetInput) sheetInput.value = '';
        if (separator) separator.value = 'auto';
        setParticipantsIdColumnOptions([], 'auto', true);
        setParticipantsIdSelectionRequired(false);
        if (idGroup) idGroup.classList.add('d-none');
    
        window.lastParticipantsPreviewData = null;
        window.neurobagelSchema = null;
        window.existingParticipantsData = null;
        window.participantsTsvData = null;
        window.pendingAdditionalParticipantColumns = [];
        window.currentAdditionalParticipantColumns = [];
        window.excludedParticipantColumns = [];
        setParticipantsAdditionalVariablesEnabled(false);
    
        const widgetContainer = document.getElementById('neurobagelWidgetContainer');
        if (widgetContainer) widgetContainer.innerHTML = '';
    }
    
    async function parseParticipantsJsonResponse(response) {
        const rawText = await response.text();
    
        try {
            return JSON.parse(rawText);
        } catch (strictErr) {
            // Some backends may emit non-standard JSON tokens like NaN/Infinity.
            // Normalize them to null so the preview flow can continue.
            const normalized = rawText
                .replace(/\bNaN\b/g, 'null')
                .replace(/\b-Infinity\b/g, 'null')
                .replace(/\bInfinity\b/g, 'null');
    
            try {
                return JSON.parse(normalized);
            } catch (lenientErr) {
                throw strictErr;
            }
        }
    }
    
    function isExcelParticipantsFile(file) {
        if (!file || !file.name) return false;
        return file.name.toLowerCase().endsWith('.xlsx');
    }
    
    function isDelimitedParticipantsFile(file) {
        if (!file || !file.name) return false;
        const name = file.name.toLowerCase();
        return name.endsWith('.csv') || name.endsWith('.tsv');
    }

    function isSupportedParticipantsImportFile(file) {
        if (!file || !file.name) return false;
        const name = file.name.toLowerCase();
        return (
            name.endsWith('.xlsx')
            || name.endsWith('.csv')
            || name.endsWith('.tsv')
            || name.endsWith('.lsa')
        );
    }
    
    function updateParticipantsSheetMetadata(metadata = null) {
        const sheetInput = document.getElementById('participantsSheet');
        const parsedCount = metadata && metadata.non_empty_sheet_count !== undefined && metadata.non_empty_sheet_count !== null
            ? Number(metadata.non_empty_sheet_count)
            : metadata && metadata.sheet_count !== undefined && metadata.sheet_count !== null
                ? Number(metadata.sheet_count)
            : Number.NaN;
        const hasExplicitShowValue = metadata && typeof metadata.show_sheet_selector === 'boolean';
    
        participantsExcelSheetCount = Number.isFinite(parsedCount) ? parsedCount : null;
        participantsShowSheetSelector = hasExplicitShowValue ? Boolean(metadata.show_sheet_selector) : null;
        participantsSheetMetadataPending = false;
    
        if (sheetInput && participantsShowSheetSelector === false) {
            sheetInput.value = '';
        }
    
        updateParticipantsInputVisibility();
    }
    
    function updateParticipantsInputVisibility() {
        const fileInput = document.getElementById('participantsDataFile');
        const sheetGroup = document.getElementById('participantsSheetGroup');
        const idGroup = document.getElementById('participantsIdColumnGroup');
        const separatorGroup = document.getElementById('participantsSeparatorGroup');
        const separatorSelect = document.getElementById('participantsSeparator');
    
        const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
        const isExcel = isExcelParticipantsFile(file);
        const isDelimited = isDelimitedParticipantsFile(file);
        const showSheetGroup = isExcel
            && !participantsSheetMetadataPending
            && (
                participantsShowSheetSelector !== null
                    ? participantsShowSheetSelector
                    : (participantsExcelSheetCount === null || participantsExcelSheetCount > 1)
            );
    
        if (sheetGroup) {
            sheetGroup.classList.toggle('d-none', !showSheetGroup);
        }
    
        if (separatorGroup) {
            separatorGroup.classList.toggle('d-none', !isDelimited);
        }
        if (!isDelimited && separatorSelect) {
            separatorSelect.value = 'auto';
        }
    
        if (!file && idGroup) {
            idGroup.classList.add('d-none');
        }
    }
    
    function setParticipantsIdSelectionRequired(isRequired) {
        const idLabel = document.getElementById('participantsIdColumnLabel');
        const idHint = document.getElementById('participantsIdColumnHint');

        if (idLabel) {
            idLabel.innerHTML = isRequired
                ? 'ID Column <span class="text-danger">*</span>'
                : 'ID Column';
        }

        if (idHint) {
            idHint.textContent = isRequired
                ? 'Select the source ID column. It will be renamed to participant_id.'
                : 'Detected source ID column. It will be renamed to participant_id in output.';
        }
    }

    function setParticipantsIdColumnOptions(columns, selectedValue = 'auto', allowAutoOption = true) {
        const idSelect = document.getElementById('participantsIdColumn');
        if (!idSelect) return;
    
        idSelect.innerHTML = '';
    
        if (allowAutoOption) {
            const autoOpt = document.createElement('option');
            autoOpt.value = 'auto';
            autoOpt.textContent = 'Auto-detect';
            idSelect.appendChild(autoOpt);
        } else {
            const placeholderOpt = document.createElement('option');
            placeholderOpt.value = '';
            placeholderOpt.textContent = 'Select ID column...';
            placeholderOpt.disabled = true;
            placeholderOpt.selected = true;
            idSelect.appendChild(placeholderOpt);
        }
    
        if (Array.isArray(columns)) {
            columns.forEach((col) => {
                const colName = String(col || '').trim();
                if (!colName) return;
                const opt = document.createElement('option');
                opt.value = colName;
                opt.textContent = colName;
                idSelect.appendChild(opt);
            });
        }
    
        const normalized = String(selectedValue || '').trim();
        if (normalized && [...idSelect.options].some((opt) => opt.value === normalized)) {
            idSelect.value = normalized;
        } else if (allowAutoOption && [...idSelect.options].some((opt) => opt.value === 'auto')) {
            idSelect.value = 'auto';
        } else if (!allowAutoOption && [...idSelect.options].some((opt) => opt.value === '')) {
            idSelect.value = '';
        } else if (idSelect.options.length > 0) {
            idSelect.value = idSelect.options[0].value;
        } else {
            idSelect.value = '';
        }
    }
    
    async function autoDetectParticipantsIdColumn() {
        const fileInput = document.getElementById('participantsDataFile');
        const idGroup = document.getElementById('participantsIdColumnGroup');
        const idSelect = document.getElementById('participantsIdColumn');
        const idHint = document.getElementById('participantsIdColumnHint');
        const sheetInput = document.getElementById('participantsSheet');
    
        const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
        if (!file) {
            participantsExcelSheetCount = null;
            participantsShowSheetSelector = null;
            participantsSheetMetadataPending = false;
            setParticipantsIdColumnOptions([], 'auto', true);
            setParticipantsIdSelectionRequired(false);
            updateParticipantsInputVisibility();
            if (idGroup) idGroup.classList.add('d-none');
            return;
        }

        if (!isSupportedParticipantsImportFile(file)) {
            participantsExcelSheetCount = null;
            participantsShowSheetSelector = null;
            participantsSheetMetadataPending = false;
            updateParticipantsInputVisibility();
            setParticipantsIdColumnOptions([], '', false);
            setParticipantsIdSelectionRequired(true);
            if (idHint) {
                idHint.textContent = 'Unsupported file format. Use .xlsx, .csv, .tsv, or .lsa.';
            }
            if (idGroup) idGroup.classList.remove('d-none');
            return;
        }
    
        try {
            const formData = new FormData();
            formData.append('file', file);
            if (isExcelParticipantsFile(file) && sheetInput && sheetInput.value) {
                formData.append('sheet', sheetInput.value);
            }
            const separator = document.getElementById('participantsSeparator')?.value || 'auto';
            formData.append('separator', separator);
    
            const response = await fetch('/api/participants-detect-id', {
                method: 'POST',
                body: formData
            });
            const data = await parseParticipantsJsonResponse(response);
    
            if (!response.ok) {
                throw new Error(data.error || 'ID detection failed');
            }
    
            updateParticipantsSheetMetadata(data);

            const idSelectionRequired = Boolean(data.id_selection_required);
            const selectedId = String(data.source_id_column || data.id_column || data.suggested_id_column || '').trim();

            setParticipantsIdSelectionRequired(idSelectionRequired);
            setParticipantsIdColumnOptions(
                data.columns || [],
                selectedId,
                false
            );

            if (idSelectionRequired) {
                if (idHint) idHint.textContent = 'Select the source ID column manually. It will be renamed to participant_id.';
            } else {
                if (idSelect && selectedId) idSelect.value = selectedId;
                if (idHint) idHint.textContent = 'Confirm or change the detected source ID column. It will be renamed to participant_id in output.';
            }
            if (idGroup) idGroup.classList.remove('d-none');
        } catch (error) {
            participantsExcelSheetCount = null;
            participantsShowSheetSelector = null;
            participantsSheetMetadataPending = false;
            updateParticipantsInputVisibility();
            console.warn('Participants ID auto-detection failed:', error);
            setParticipantsIdColumnOptions([], '', false);
            setParticipantsIdSelectionRequired(true);
            if (idHint) idHint.textContent = 'Automatic detection unavailable. Select the source ID column manually.';
            if (idGroup) idGroup.classList.remove('d-none');
        }
    }
    
    // Enable/disable buttons based on file selection and preview state
    function updateParticipantsButtonState() {
        const fileInput = document.getElementById('participantsDataFile');
        const hasFile = fileInput && fileInput.files.length > 0;
        const file = hasFile ? fileInput.files[0] : null;
        
        const previewBtn = document.getElementById('participantsPreviewBtn');
        const convertBtn = document.getElementById('participantsConvertBtn');
        const saveAnnotBtn = document.getElementById('saveNeurobagelBtn');
        
        if (hasFile) {
            participantsExcelSheetCount = null;
            participantsShowSheetSelector = null;
            participantsSheetMetadataPending = isExcelParticipantsFile(file);
            if (previewBtn) previewBtn.disabled = false;
            // Convert is only enabled if preview has been completed
            if (convertBtn) convertBtn.disabled = !participantsPreviewCompleted;
            if (saveAnnotBtn) saveAnnotBtn.disabled = !participantsPreviewCompleted;
            const warningDiv = document.getElementById('participantsExistingFilesWarning');
            if (warningDiv) warningDiv.classList.add('d-none');
            updateParticipantsInputVisibility();
            autoDetectParticipantsIdColumn();
        } else {
            participantsExcelSheetCount = null;
            participantsShowSheetSelector = null;
            participantsSheetMetadataPending = false;
            if (previewBtn) previewBtn.disabled = true;
            if (convertBtn) convertBtn.disabled = true;
            if (saveAnnotBtn) saveAnnotBtn.disabled = true;
            participantsPreviewCompleted = false;
            updateParticipantsInputVisibility();
        }
    
        updateParticipantsSelectedFileName();
    }
    
    // Attach event listener
    const fileInput = document.getElementById('participantsDataFile');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            resetParticipantsPanelState();
            updateParticipantsButtonState();
        });
    }
    
    const participantsChooseFileBtn = document.getElementById('participantsChooseFileBtn');
    if (participantsChooseFileBtn && fileInput) {
        participantsChooseFileBtn.addEventListener('click', function() {
            fileInput.click();
        });
    }
    
    const participantsClearFileBtn = document.getElementById('participantsClearFileBtn');
    if (participantsClearFileBtn && fileInput) {
        participantsClearFileBtn.addEventListener('click', function() {
            fileInput.value = '';
            resetParticipantsPanelState();
            updateParticipantsButtonState();
        });
    }
    
    const sheetInput = document.getElementById('participantsSheet');
    if (sheetInput) {
        sheetInput.addEventListener('change', function() {
            const fileEl = document.getElementById('participantsDataFile');
            const file = fileEl && fileEl.files && fileEl.files[0] ? fileEl.files[0] : null;
            if (isExcelParticipantsFile(file)) {
                autoDetectParticipantsIdColumn();
            }
        });
    }
    
    const participantsSeparator = document.getElementById('participantsSeparator');
    if (participantsSeparator) {
        participantsSeparator.addEventListener('change', function() {
            const fileEl = document.getElementById('participantsDataFile');
            const file = fileEl && fileEl.files && fileEl.files[0] ? fileEl.files[0] : null;
            if (isDelimitedParticipantsFile(file)) {
                autoDetectParticipantsIdColumn();
            }
        });
    }
    
    // Run immediately
    updateParticipantsInputVisibility();
    updateParticipantsButtonState();
    setParticipantsAdditionalVariablesEnabled(false);
    
    // Check for existing participant files
    async function checkExistingParticipantFiles() {
        try {
            const response = await fetch('/api/participants-check');
            const data = await response.json();
            
            const warningDiv = document.getElementById('participantsExistingFilesWarning');
            const messageSpan = document.getElementById('participantsExistingFilesMessage');
            
            if (data.exists) {
                const files = Object.values(data.files).filter(f => f !== null);
                messageSpan.textContent = `Found existing files: ${files.map(f => f.split('/').pop()).join(', ')}`;
                warningDiv.classList.remove('d-none');
            } else {
                warningDiv.classList.add('d-none');
            }
            return data;
        } catch (error) {
            console.error('Error checking existing files:', error);
            return { exists: false, files: {} };
        }
    }

    function normalizeParticipantAdditionalColumn(value) {
        return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '');
    }

    function ensureExcludedParticipantColumnsState() {
        if (!Array.isArray(window.excludedParticipantColumns)) {
            window.excludedParticipantColumns = [];
        }
        return window.excludedParticipantColumns;
    }

    function collectExcludedParticipantAdditionalColumns(previewColumns = []) {
        const excluded = new Set(
            (Array.isArray(previewColumns) ? previewColumns : [])
                .map(normalizeParticipantAdditionalColumn)
                .filter(Boolean)
        );

        const liveColumns = [
            ...(Array.isArray(window.currentAdditionalParticipantColumns) ? window.currentAdditionalParticipantColumns : []),
            ...(Array.isArray(window.pendingAdditionalParticipantColumns) ? window.pendingAdditionalParticipantColumns : []),
        ];

        liveColumns.forEach((columnName) => {
            const normalized = normalizeParticipantAdditionalColumn(columnName);
            if (normalized) {
                excluded.add(normalized);
            }
        });

        return excluded;
    }

    function setParticipantsAdditionalVariablesEnabled(hasAdditionalVariables) {
        const createParticipantMappingBtn = document.getElementById('createParticipantMappingBtn');
        if (!createParticipantMappingBtn) {
            return;
        }
        createParticipantMappingBtn.disabled = !Boolean(hasAdditionalVariables);
    }

    window.setParticipantsAdditionalVariablesEnabled = setParticipantsAdditionalVariablesEnabled;

    function refreshParticipantsPreviewAfterAdditionalVariableChange() {
        const previewBtn = document.getElementById('participantsPreviewBtn');
        const participantsFileInput = document.getElementById('participantsDataFile');
        if (!previewBtn || previewBtn.disabled) {
            return false;
        }
        if (!participantsFileInput || !participantsFileInput.files || !participantsFileInput.files[0]) {
            return false;
        }
        if (!window.lastParticipantsPreviewData) {
            return false;
        }

        window.setTimeout(() => {
            try {
                previewBtn.click();
            } catch (error) {
                console.warn('Could not refresh participants preview after additional variable change:', error);
            }
        }, 0);

        return true;
    }

    window.refreshParticipantsPreviewAfterAdditionalVariableChange = refreshParticipantsPreviewAfterAdditionalVariableChange;

    const createParticipantMappingBtn = document.getElementById('createParticipantMappingBtn');
    if (createParticipantMappingBtn) {
        createParticipantMappingBtn.addEventListener('click', function() {
            const currentProjectPath = resolveCurrentProjectPath();
            if (!currentProjectPath) {
                alert('Please load a project first to add additional variables. Projects are managed in the Projects page.');
                return;
            }

            document.getElementById('mappingColumnsContainer').classList.remove('d-none');
            document.getElementById('mappingSuccess').classList.add('d-none');
            document.getElementById('mappingError').classList.add('d-none');
            document.getElementById('saveMappingBtn').classList.remove('d-none');
            document.getElementById('cancelMappingBtn').classList.remove('d-none');
            document.getElementById('closeMappingBtn').classList.add('d-none');

            const modal = new bootstrap.Modal(document.getElementById('participantMappingModal'));
            let mappingCandidates = [];

            if (window.lastParticipantsPreviewData && Array.isArray(window.lastParticipantsPreviewData.columns)) {
                const p = window.lastParticipantsPreviewData;
                const idCol = p.source_id_column || p.id_column;
                const idColNormalized = normalizeParticipantAdditionalColumn(idCol);
                const schema = p.neurobagel_schema || {};
                const defaultPreviewCols = Array.isArray(p.columns) ? p.columns : [];
                const excludedColumns = collectExcludedParticipantAdditionalColumns(defaultPreviewCols);
                const participantColumns = Array.isArray(p.source_columns) && p.source_columns.length > 0
                    ? p.source_columns
                    : p.columns;
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

                const questionnaireColSet = new Set(Array.isArray(p.questionnaire_like_columns) ? p.questionnaire_like_columns : []);
                mappingCandidates = participantColumns
                    .filter(col => {
                        const normalized = normalizeParticipantAdditionalColumn(col);
                        return normalized !== idColNormalized
                            && !questionnaireColSet.has(col)
                            && normalized
                            && !excludedColumns.has(normalized);
                    })
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
            } else if (window.lastPreviewData && window.lastPreviewData.participants_tsv) {
                const tsv = window.lastPreviewData.participants_tsv;
                mappingCandidates = tsv.unused_columns || [];
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
            const safeFieldCode = escapeHtml(fieldCode || '');
            const safeDescription = escapeHtml(description || '');
            const safeInferReason = escapeHtml(String(inferReason || ''));
            const inferIcon = inferReason
                ? `<i class="fas fa-circle-info text-muted ms-1" title="${safeInferReason}"></i>`
                : '';

            html += `
                <div class="form-check mb-2">
                    <input class="form-check-input col-selector" type="checkbox" id="col_${idx}" value="${safeFieldCode}" data-description="${safeDescription}">
                    <label class="form-check-label" for="col_${idx}">
                        <strong>${safeFieldCode}</strong>${inferIcon}
                        ${safeDescription ? `<br><small class="text-muted">→ ${safeDescription}</small>` : ''}
                    </label>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;

        container.innerHTML = html;

        const checkboxes = document.querySelectorAll('.col-selector');
        const updateSaveBtn = () => {
            const hasSelection = Array.from(checkboxes).some(cb => cb.checked);
            document.getElementById('saveMappingBtn').disabled = !hasSelection;
        };

        checkboxes.forEach(cb => {
            cb.addEventListener('change', updateSaveBtn);
        });
    }

    const saveMappingBtn = document.getElementById('saveMappingBtn');
    if (saveMappingBtn) {
        saveMappingBtn.addEventListener('click', async function() {
            const selected = Array.from(document.querySelectorAll('.col-selector:checked'));

            if (selected.length === 0) {
                alert('Please select at least one column');
                return;
            }

            const mapping = {
                version: '1.0',
                description: 'Additional variables mapping created from PRISM web UI',
                mappings: {}
            };
            const selectedColumnsForNeurobagel = [];
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

                selectedColumnsForNeurobagel.push({
                    name: fieldCode,
                    description: description,
                });
            });

            const libraryPath = document.getElementById('convertLibraryPath')?.value || '';

            try {
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

                exposeAdditionalVariablesToNeurobagel(selectedColumnsForNeurobagel);
                showMappingSuccess();
            } catch (err) {
                showMappingError(err.message);
            }
        });
    }

    function exposeAdditionalVariablesToNeurobagel(selectedColumns) {
        if (!Array.isArray(selectedColumns) || selectedColumns.length === 0) {
            return;
        }

        const pendingNames = new Set(
            Array.isArray(window.pendingAdditionalParticipantColumns)
                ? window.pendingAdditionalParticipantColumns.map(v => String(v || '').trim()).filter(Boolean)
                : []
        );

        if (!window.currentAdditionalParticipantColumns || !Array.isArray(window.currentAdditionalParticipantColumns)) {
            window.currentAdditionalParticipantColumns = [];
        }
        if (!window.currentAdditionalParticipantDescriptions || typeof window.currentAdditionalParticipantDescriptions !== 'object') {
            window.currentAdditionalParticipantDescriptions = {};
        }

        selectedColumns.forEach(({ name }) => {
            const cleanedName = String(name || '').trim();
            if (cleanedName) {
                pendingNames.add(cleanedName);
                if (!window.currentAdditionalParticipantColumns.includes(cleanedName)) {
                    window.currentAdditionalParticipantColumns.push(cleanedName);
                }
            }
        });

        const excludedColumns = ensureExcludedParticipantColumnsState();
        window.excludedParticipantColumns = excludedColumns.filter((columnName) => {
            const normalizedColumn = normalizeParticipantAdditionalColumn(columnName);
            return !selectedColumns.some(({ name }) => normalizeParticipantAdditionalColumn(name) === normalizedColumn);
        });

        selectedColumns.forEach(({ name, description }) => {
            const cleanedName = String(name || '').trim();
            if (!cleanedName) return;
            window.currentAdditionalParticipantDescriptions[cleanedName] = String(description || '').trim();
        });

        window.pendingAdditionalParticipantColumns = Array.from(pendingNames);

        const participantsTsvData = (window.participantsTsvData && typeof window.participantsTsvData === 'object')
            ? window.participantsTsvData
            : {};

        selectedColumns.forEach(({ name }) => {
            const cleanedName = String(name || '').trim();
            if (cleanedName && !Object.prototype.hasOwnProperty.call(participantsTsvData, cleanedName)) {
                participantsTsvData[cleanedName] = [];
            }
        });
        window.participantsTsvData = participantsTsvData;

        if (!window.existingParticipantsData || typeof window.existingParticipantsData !== 'object') {
            window.existingParticipantsData = {};
        }
        selectedColumns.forEach(({ name, description }) => {
            const cleanedName = String(name || '').trim();
            if (!cleanedName) return;

            const existingDef = window.existingParticipantsData[cleanedName];
            if (!existingDef || typeof existingDef !== 'object') {
                window.existingParticipantsData[cleanedName] = {
                    Description: description || ''
                };
            } else if (!existingDef.Description && description) {
                existingDef.Description = description;
            }
        });

        if (typeof window.renderNeurobagelWidget === 'function') {
            window.renderNeurobagelWidget().catch((error) => {
                console.warn('Could not re-render NeuroBagel widget after adding variables:', error);
            });
        }
    }

    window.removeAdditionalParticipantVariable = async function(variableName) {
        const cleanedName = String(variableName || '').trim();
        if (!cleanedName) return;

        if (Array.isArray(window.pendingAdditionalParticipantColumns)) {
            window.pendingAdditionalParticipantColumns = window.pendingAdditionalParticipantColumns
                .map(v => String(v || '').trim())
                .filter(v => v && v !== cleanedName);
        }

        if (Array.isArray(window.currentAdditionalParticipantColumns)) {
            window.currentAdditionalParticipantColumns = window.currentAdditionalParticipantColumns
                .map(v => String(v || '').trim())
                .filter(v => v && v !== cleanedName);
        }

        if (window.currentAdditionalParticipantDescriptions && typeof window.currentAdditionalParticipantDescriptions === 'object') {
            delete window.currentAdditionalParticipantDescriptions[cleanedName];
        }

        const excludedColumns = ensureExcludedParticipantColumnsState()
            .map(v => String(v || '').trim())
            .filter(Boolean);
        if (!excludedColumns.includes(cleanedName)) {
            excludedColumns.push(cleanedName);
        }
        window.excludedParticipantColumns = excludedColumns;

        const mapping = {
            version: '1.0',
            description: 'Additional variables mapping created from PRISM web UI',
            mappings: {}
        };

        const allAdditional = Array.isArray(window.currentAdditionalParticipantColumns)
            ? window.currentAdditionalParticipantColumns
            : [];

        allAdditional.forEach((columnName) => {
            const normalized = String(columnName || '').trim();
            if (!normalized) return;
            const desc = window.currentAdditionalParticipantDescriptions
                ? String(window.currentAdditionalParticipantDescriptions[normalized] || '').trim()
                : '';

            mapping.mappings[normalized] = {
                source_column: normalized,
                standard_variable: normalized,
                type: 'string'
            };
            if (desc) {
                mapping.mappings[normalized].description = desc;
            }
        });

        const libraryPath = document.getElementById('convertLibraryPath')?.value || '';
        const response = await fetch('/api/save-participant-mapping', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                mapping,
                library_path: libraryPath
            })
        });

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.error || 'Failed to update additional variables mapping');
        }
    };

    function showMappingSuccess() {
        document.getElementById('mappingColumnsContainer').classList.add('d-none');
        document.getElementById('mappingSuccess').classList.remove('d-none');
        document.getElementById('mappingError').classList.add('d-none');

        document.getElementById('saveMappingBtn').classList.add('d-none');
        document.getElementById('cancelMappingBtn').classList.add('d-none');
        document.getElementById('closeMappingBtn').classList.remove('d-none');

        const mappingModalEl = document.getElementById('participantMappingModal');
        const mappingModal = mappingModalEl ? bootstrap.Modal.getInstance(mappingModalEl) : null;
        if (mappingModal) {
            setTimeout(() => {
                mappingModal.hide();

                refreshParticipantsPreviewAfterAdditionalVariableChange();
                // loadNeurobagelWidget() is intentionally not called here –
                // refreshParticipantsPreviewAfterAdditionalVariableChange() triggers a
                // full preview which ends with displayNeurobagelSchema() →
                // loadNeurobagelWidget().  Calling it twice here causes a race
                // condition that wipes in-session NeuroBagel enrichments before the
                // user's Map click is reflected in the sidebar.

                const neurobagelSection = document.getElementById('neurobagelSection');
                if (neurobagelSection) {
                    neurobagelSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 350);
        }
    }

    function showMappingError(message) {
        document.getElementById('mappingError').classList.remove('d-none');
        document.getElementById('mappingErrorText').textContent = message;
        document.getElementById('mappingSuccess').classList.add('d-none');
    }
    
    function renderParticipantsPreviewTable(previewData, schemaOverride = null) {
        if (!previewData) return;
    
        const table = document.getElementById('participantsPreviewTable');
        if (!table) return;
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        if (!thead || !tbody) return;
    
        const tsvColumns = Array.isArray(previewData.columns) ? previewData.columns : [];
        const tsvColumnSet = new Set(tsvColumns.map(c => String(c).toLowerCase()));
    
        // Only show columns explicitly added by the user in this session via the
        // "Additional Variables" modal. Avoid pulling in columns from a previously
        // saved participants.tsv (which get merged into window.participantsTsvData
        // when the widget opens and would falsely appear as CUSTOM).
        const userAdded = [
            ...(window.pendingAdditionalParticipantColumns || []),
            ...(window.currentAdditionalParticipantColumns || [])
        ];
        const seen = new Set();
        const extraColumns = userAdded
            .map(c => String(c || '').trim())
            .filter(c => c && !tsvColumnSet.has(c.toLowerCase()) && !seen.has(c.toLowerCase()) && seen.add(c.toLowerCase()));
    
        const columns = [...tsvColumns, ...extraColumns];
        const previewRows = Array.isArray(previewData.preview_rows) ? previewData.preview_rows : [];
        const idColumn = previewData.id_column;
        const schema = schemaOverride || previewData.neurobagel_schema || {};
    
        // Returns the HTML-escaped raw source value for display in the preview.
        function formatPreviewCell(colName, rawValue) {
            if (rawValue === null || rawValue === undefined) {
                return '';
            }
            const rawText = String(rawValue).trim();
            return rawText.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        }
    
        thead.innerHTML = '';
        tbody.innerHTML = '';
    
        const headerRow = document.createElement('tr');
        columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
    
            const nbField = schema?.[col];
            // Use live widget state as the authoritative source for NeuroBagel mapping
            // to avoid showing stale badges from a previously saved participants.json.
            // Only flag as NeuroBagel if the term/variable matches a known concept.
            const widgetColState = window.neurobagelWidgetState?.allColumns?.[col];
            const knownMappings = Object.values(window.neurobagelCommonMappings || {});
            const isKnownNBConcept = (colState) => {
                if (!colState) return false;
                const sv = String(colState.standardized_variable || '').trim().toLowerCase();
                const tu = String(colState.term_url || '').trim().toLowerCase();
                if (!sv && !tu) return false;
                return knownMappings.some(m => m && (
                    (sv && String(m.standardized_variable || '').trim().toLowerCase() === sv) ||
                    (tu && String(m.term_url || '').trim().toLowerCase() === tu)
                ));
            };
            const hasNeurobagelMapping = widgetColState
                ? isKnownNBConcept(widgetColState)
                : !!nbField?.Annotations?.IsAbout;
            const variableType = widgetColState?.data_type || nbField?.Annotations?.VariableType;
    
            if (col === idColumn) {
                th.innerHTML += ' <span class="badge bg-primary">ID</span>';
            }
            if (extraColumns.includes(col)) {
                th.innerHTML += ' <span class="badge bg-secondary" title="Custom column (not in source file)">CUSTOM</span>';
            }
            if (hasNeurobagelMapping) {
                th.innerHTML += ' <span class="badge bg-info">NB</span>';
            }
            if (variableType) {
                const normalizedType = String(variableType).toLowerCase();
                const typeLabel = normalizedType === 'continuous'
                    ? 'CONT'
                    : (normalizedType === 'categorical' ? 'CAT' : String(variableType).toUpperCase());
                const typeClass = normalizedType === 'continuous'
                    ? 'bg-success'
                    : (normalizedType === 'categorical' ? 'bg-warning text-dark' : 'bg-secondary');
                th.innerHTML += ` <span class="badge ${typeClass}">${typeLabel}</span>`;
            }
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
    
        previewRows.forEach(row => {
            const tr = document.createElement('tr');
            columns.forEach(col => {
                const td = document.createElement('td');
                const rawVal = row[col];
                const hasData = rawVal !== null && rawVal !== undefined && String(rawVal).trim() !== '';
                if (extraColumns.includes(col) && !hasData) {
                    // Custom column with no data in this preview row
                    td.innerHTML = '<span class="text-muted" style="font-size:.8em">—</span>';
                    td.title = 'Not present in source file for this row';
                } else {
                    td.innerHTML = formatPreviewCell(col, rawVal);
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    
        refreshParticipantsWorkflowSummary();
    }
    
    function countAvailableAdditionalParticipantColumns(previewData) {
        if (!previewData || typeof previewData !== 'object') {
            return 0;
        }
    
        const sourceColumns = Array.isArray(previewData.source_columns)
            ? previewData.source_columns.map(col => String(col || '').trim()).filter(Boolean)
            : [];
        const defaultPreviewCols = new Set(
            (Array.isArray(previewData.columns) ? previewData.columns : [])
                .map(col => String(col || '').trim())
                .filter(Boolean)
        );
        const questionnaireColSet = new Set(
            (Array.isArray(previewData.questionnaire_like_columns) ? previewData.questionnaire_like_columns : [])
                .map(col => String(col || '').trim())
                .filter(Boolean)
        );
        const idCol = String(previewData.source_id_column || previewData.id_column || '').trim();
    
        if (sourceColumns.length > 0) {
            const candidates = sourceColumns.filter(col => (
                col
                && col !== idCol
                && !defaultPreviewCols.has(col)
                && !questionnaireColSet.has(col)
            ));
            return new Set(candidates).size;
        }
    
        // Fallback for legacy payloads that do not expose source/questionnaire columns.
        const totalSourceColumns = Number(previewData.total_source_columns || 0);
        const extractedColumns = Number(previewData.extracted_columns || 0);
        return Math.max(0, totalSourceColumns - extractedColumns);
    }
    
    function refreshParticipantsWorkflowSummary() {
        const summary = document.getElementById('participantsWorkflowSummary');
        const columnsBadge = document.getElementById('participantsSummaryColumns');
        const mappedBadge = document.getElementById('participantsSummaryMapped');
        const recodesBadge = document.getElementById('participantsSummaryRecodes');
    
        if (!summary || !columnsBadge || !mappedBadge || !recodesBadge) {
            return;
        }
    
        const previewData = window.lastParticipantsPreviewData;
        const previewColumns = Array.isArray(previewData && previewData.columns)
            ? previewData.columns.map(col => String(col || '').trim()).filter(Boolean)
            : [];
    
        if (previewColumns.length === 0) {
            summary.classList.add('d-none');
            return;
        }
    
        const allColumns = window.neurobagelWidgetState?.allColumns || {};
        const knownMappings = Object.values(window.neurobagelCommonMappings || {});
    
        function normalizeColName(value) {
            return String(value || '').toLowerCase().replace(/_/g, '').trim();
        }
    
        function findColumnState(colName) {
            if (Object.prototype.hasOwnProperty.call(allColumns, colName)) {
                return allColumns[colName];
            }
            const target = normalizeColName(colName);
            const matchedKey = Object.keys(allColumns).find(key => normalizeColName(key) === target);
            return matchedKey ? allColumns[matchedKey] : null;
        }
    
        function isKnownNBConcept(colState) {
            if (!colState) return false;
            const sv = String(colState.standardized_variable || '').trim().toLowerCase();
            const tu = String(colState.term_url || '').trim().toLowerCase();
            if (!sv && !tu) return false;
            return knownMappings.some(m => m && (
                (sv && String(m.standardized_variable || '').trim().toLowerCase() === sv) ||
                (tu && String(m.term_url || '').trim().toLowerCase() === tu)
            ));
        }
    
        let mappedCount = 0;
        let recodeCount = 0;
    
        previewColumns.forEach(colName => {
            const colState = findColumnState(colName);
            if (!colState) return;
    
            if (isKnownNBConcept(colState)) {
                mappedCount += 1;
            }
    
            const rewriteMap = (colState && typeof colState.level_key_mappings === 'object')
                ? colState.level_key_mappings
                : null;
            if (!rewriteMap) return;
    
            Object.entries(rewriteMap).forEach(([sourceValue, targetValue]) => {
                const src = String(sourceValue || '').trim();
                const dst = String(targetValue || '').trim();
                if (src && dst && src !== dst) {
                    recodeCount += 1;
                }
            });
        });
    
        columnsBadge.textContent = `${previewColumns.length} column${previewColumns.length === 1 ? '' : 's'}`;
        mappedBadge.textContent = `${mappedCount} mapped`;
        recodesBadge.textContent = `${recodeCount} value recode${recodeCount === 1 ? '' : 's'}`;
        summary.classList.remove('d-none');
    }
    
    async function buildEffectivePreviewSchema(previewData) {
        const baseSchema = (previewData && previewData.neurobagel_schema && typeof previewData.neurobagel_schema === 'object')
            ? { ...previewData.neurobagel_schema }
            : {};
    
        try {
            const response = await fetch('/api/projects/participants');
            const payload = await response.json();
            if (response.ok && payload.success && payload.exists && payload.schema && typeof payload.schema === 'object') {
                const projectSchema = payload.schema;
                const merged = { ...baseSchema };
    
                Object.entries(projectSchema).forEach(([fieldName, fieldSchema]) => {
                    if (!fieldName || typeof fieldSchema !== 'object') return;
                    const current = (merged[fieldName] && typeof merged[fieldName] === 'object') ? merged[fieldName] : {};
                    merged[fieldName] = { ...current, ...fieldSchema };
                });
    
                return merged;
            }
        } catch (error) {
            console.warn('Could not load project participants schema for preview merge:', error);
        }
    
        return baseSchema;
    }
    
    // Preview button handler
    document.getElementById('participantsPreviewBtn')?.addEventListener('click', async function() {
        const previewResults = document.getElementById('participantsPreviewResults');
        const errorDiv = document.getElementById('participantsError');
        let previewStage = 'starting preview';
        
        errorDiv.classList.add('d-none');
        previewResults.classList.add('d-none');
        
        try {
            previewStage = 'syncing annotation editor';
            if (typeof window.syncNeurobagelActiveEditorToState === 'function') {
                window.syncNeurobagelActiveEditorToState();
            }
    
            previewStage = 'validating input file';
            const fileInput = document.getElementById('participantsDataFile');
            if (!fileInput.files[0]) {
                throw new Error('Please select a file');
            }
            
            const formData = new FormData();
            formData.append('mode', 'file');
            formData.append('file', fileInput.files[0]);
            
            const sheet = document.getElementById('participantsSheet').value;
            const idGroup = document.getElementById('participantsIdColumnGroup');
            const idColumn = document.getElementById('participantsIdColumn').value;
            const separator = document.getElementById('participantsSeparator')?.value || 'auto';
            const idSelectionRequired = Boolean(idGroup && !idGroup.classList.contains('d-none'));
            if (sheet) formData.append('sheet', sheet);
            if (idSelectionRequired && (!idColumn || idColumn === 'auto')) {
                throw new Error('Please select the ID column. It will be renamed to participant_id.');
            }
            if (idColumn && (idColumn !== 'auto' || idSelectionRequired)) {
                formData.append('id_column', idColumn);
            }
            formData.append('separator', separator);
    
            // Include any columns the user explicitly added via "Additional Variables"
            const allExtra = [
                ...(window.pendingAdditionalParticipantColumns || []),
                ...(window.currentAdditionalParticipantColumns || [])
            ].map(c => String(c || '').trim()).filter(Boolean);
            if (allExtra.length > 0) {
                formData.append('extra_columns', JSON.stringify([...new Set(allExtra)]));
            }
    
            const excludedColumns = Array.isArray(window.excludedParticipantColumns)
                ? window.excludedParticipantColumns.map(c => String(c || '').trim()).filter(Boolean)
                : [];
            if (excludedColumns.length > 0) {
                formData.append('excluded_columns', JSON.stringify([...new Set(excludedColumns)]));
            }
    
            previewStage = 'requesting participants preview';
            const response = await fetch('/api/participants-preview', {
                method: 'POST',
                body: formData
            });
            
            previewStage = 'parsing preview response';
            const data = await response.json();
            
            if (!response.ok) {
                if (response.status === 409 && data.error === 'id_column_required') {
                    const idGroup = document.getElementById('participantsIdColumnGroup');
                    const idHint = document.getElementById('participantsIdColumnHint');
                    const suggestedId = String(data.suggested_id_column || '').trim();
                    setParticipantsIdSelectionRequired(true);
                    setParticipantsIdColumnOptions(data.columns || [], suggestedId, false);
                    if (idHint) idHint.textContent = 'Select the source ID column manually. It will be renamed to participant_id.';
                    if (idGroup) idGroup.classList.remove('d-none');
                }
                let errorMessage = data.error || 'Preview failed';
                if (String(errorMessage).trim().toLowerCase() === 'the string did not match the expected pattern.') {
                    const stageLabel = data.error_stage ? ` (${data.error_stage})` : '';
                    errorMessage = `Preview failed due to invalid value patterns${stageLabel}. Please manually fix mixed timing formats in the source file (use one format per column, e.g. all HH:MM or all numeric minutes) and avoid ambiguous values like "4-6h" or "10 30".`;
                }
                if (data.error_stage || data.error_type) {
                    const meta = [data.error_stage, data.error_type].filter(Boolean).join(' | ');
                    if (meta) {
                        errorMessage += ` [${meta}]`;
                    }
                }
                throw new Error(errorMessage);
            }
    
            if (data.id_column) {
                const idSelect = document.getElementById('participantsIdColumn');
                const idGroup = document.getElementById('participantsIdColumnGroup');
                const idHint = document.getElementById('participantsIdColumnHint');
                const selectedSourceId = data.source_id_column || data.id_column || data.suggested_id_column;
                const idSelectionRequired = Boolean(data.id_selection_required);
                setParticipantsIdSelectionRequired(idSelectionRequired);
                setParticipantsIdColumnOptions(
                    data.source_columns || data.columns || [],
                    selectedSourceId || (idSelectionRequired ? '' : 'auto'),
                    !idSelectionRequired
                );
                if (idSelect && selectedSourceId) idSelect.value = selectedSourceId;
                if (idHint) {
                    idHint.textContent = idSelectionRequired
                        ? 'Select the source ID column manually. It will be renamed to participant_id.'
                        : 'ID column is already participant_id in source file.';
                }
                if (idGroup) idGroup.classList.toggle('d-none', !idSelectionRequired);
            }
    
            previewStage = 'building effective schema';
            const effectiveSchema = await buildEffectivePreviewSchema(data);
            data.neurobagel_schema = effectiveSchema;
    
            // Make participants preview available to shared mapping modal logic
            window.lastParticipantsPreviewData = data;
            // Keep NeuroBagel editor in sync with the latest preview schema/types
            if (effectiveSchema) {
                window.existingParticipantsData = effectiveSchema;
            }
            
            // Display preview
            const countBadge = document.getElementById('participantsPreviewCount');
            countBadge.textContent = `${data.participant_count} participants`;
    
            const availabilityInfo = document.getElementById('participantsPreviewAvailabilityInfo');
            const availabilityText = document.getElementById('participantsPreviewAvailabilityText');
            const hiddenColumns = countAvailableAdditionalParticipantColumns(data);
            setParticipantsAdditionalVariablesEnabled(hiddenColumns > 0);
    
            if (hiddenColumns > 0 && availabilityInfo && availabilityText) {
                availabilityText.textContent = `${hiddenColumns} additional variable(s) are available in the source file but not shown in this preview (survey/questionnaire columns are excluded). Use "Add Additional Variables" to select and include them.`;
                availabilityInfo.classList.remove('d-none');
            } else if (availabilityInfo) {
                availabilityInfo.classList.add('d-none');
            }
            
            const infoDiv = document.getElementById('participantsInfo');
            const formatWarnings = Array.isArray(data.format_warnings)
                ? data.format_warnings.filter(Boolean)
                : [];
            const problemColumns = Array.isArray(data.problem_columns)
                ? data.problem_columns
                    .filter(entry => entry && entry.column)
                    .map(entry => ({
                        column: String(entry.column),
                        examples: Array.isArray(entry.examples)
                            ? entry.examples.map(v => String(v)).filter(Boolean).slice(0, 2)
                            : []
                    }))
                : [];
            if (formatWarnings.length > 0) {
                const escapeHtml = (value) => String(value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;');
    
                const columnListHtml = problemColumns.length > 0
                    ? `
                        <div class="mt-2"><strong>Affected columns:</strong></div>
                        <ul class="mb-2 mt-1">
                            ${problemColumns.map(item => {
                                const examples = item.examples.length > 0
                                    ? ` (examples: ${item.examples.map(ex => `'${escapeHtml(ex)}'`).join(', ')})`
                                    : '';
                                return `<li><strong>${escapeHtml(item.column)}</strong>${examples}</li>`;
                            }).join('')}
                        </ul>
                    `
                    : '';
    
                infoDiv.innerHTML = `
                    <i class="fas fa-circle-info me-2"></i>
                    <strong>Data format warning:</strong>
                    ${columnListHtml}
                    <div class="mb-0">
                        Please fix the listed columns manually in the source file before import.
                        Use one consistent format per column (recommended: all HH:MM or all numeric minutes).
                    </div>
                `;
                infoDiv.classList.remove('d-none');
            } else {
                infoDiv.classList.add('d-none');
            }
            
            previewStage = 'rendering preview table';
            try {
                renderParticipantsPreviewTable(data, effectiveSchema || null);
            } catch (renderError) {
                console.error('Participants preview table rendering failed:', renderError);
                throw new Error(`Preview table rendering failed: ${renderError.message || renderError}`);
            }
    
            // Make preview columns immediately available to the NeuroBagel quick editor
            // so users can map uploaded TSV fields before conversion.
            const previewColumnValues = {};
            data.columns.forEach(col => {
                const values = [];
                data.preview_rows.forEach(row => {
                    const raw = row[col];
                    if (raw !== null && raw !== undefined && String(raw).trim() !== '') {
                        values.push(String(raw));
                    }
                });
                previewColumnValues[col] = [...new Set(values)].slice(0, 50);
            });
            window.participantsTsvData = previewColumnValues;
            if (Array.isArray(window.pendingAdditionalParticipantColumns) && window.pendingAdditionalParticipantColumns.length > 0) {
                window.pendingAdditionalParticipantColumns.forEach((columnName) => {
                    const cleanedName = String(columnName || '').trim();
                    if (cleanedName && !Object.prototype.hasOwnProperty.call(window.participantsTsvData, cleanedName)) {
                        window.participantsTsvData[cleanedName] = [];
                    }
                });
            }
            console.log('✅ Set window.participantsTsvData from preview:', Object.keys(window.participantsTsvData));
            
            previewResults.classList.remove('d-none');
            
            // Display NeuroBagel schema if available
            if (effectiveSchema) {
                previewStage = 'updating annotation widget';
                try {
                    displayNeurobagelSchema(effectiveSchema);
                } catch (widgetError) {
                    // Non-fatal: preview is ready even if optional annotation widget fails to initialize.
                    console.error('NeuroBagel widget update failed:', widgetError);
                    const infoDiv = document.getElementById('participantsInfo');
                    if (infoDiv) {
                        infoDiv.innerHTML = `<i class="fas fa-circle-info me-2"></i>Preview loaded, but annotation widget could not be updated (${String(widgetError.message || widgetError)}). You can still review and convert data.`;
                        infoDiv.classList.remove('d-none');
                    }
                }
            }
            
        } catch (error) {
            const rawMessage = String(error && error.message ? error.message : error || 'Preview failed');
            const normalized = rawMessage.trim().toLowerCase();
            const genericPatternMessage = normalized === 'the string did not match the expected pattern.';
    
            if (genericPatternMessage) {
                errorDiv.textContent = `Preview failed in UI stage "${previewStage}" due to an invalid value pattern. Please retry once, and if it persists, keep separator on Semicolon and use ID column "ID" manually.`;
            } else {
                errorDiv.textContent = `${rawMessage} [${previewStage}]`;
            }
            errorDiv.classList.remove('d-none');
    
            const availabilityInfo = document.getElementById('participantsPreviewAvailabilityInfo');
            if (availabilityInfo) availabilityInfo.classList.add('d-none');

            setParticipantsAdditionalVariablesEnabled(false);
    
            const workflowSummary = document.getElementById('participantsWorkflowSummary');
            if (workflowSummary) workflowSummary.classList.add('d-none');
        }
    });
    
    function displayNeurobagelSchema(schema) {
        const schemaPreview = document.getElementById('neurobagelSchemaPreview');
        const schemaJsonCode = document.getElementById('schemaJsonCode');
        
        // Store schema globally for use during conversion
        window.neurobagelSchema = schema;
        
        // Show JSON preview
        schemaJsonCode.textContent = JSON.stringify(schema, null, 2);
        schemaPreview.classList.remove('d-none');
        
        // Mark preview as complete and enable Convert button
        participantsPreviewCompleted = true;
        const convertBtn = document.getElementById('participantsConvertBtn');
        const convertHint = document.getElementById('convertBtnHint');
        if (convertBtn) {
            convertBtn.disabled = false;
            convertBtn.classList.remove('btn-outline-secondary');
            convertBtn.classList.add('btn-success');
            convertHint.textContent = 'Ready to create files in project';
        }
    
        const saveAnnotBtn = document.getElementById('saveNeurobagelBtn');
        if (saveAnnotBtn) {
            saveAnnotBtn.disabled = false;
        }
    
        refreshParticipantsWorkflowSummary();
    
        // Keep annotation view in sync with latest preview/schema as soon as step 1 completes.
        loadNeurobagelWidget();
    }
    
    function buildAnnotatedParticipantsSchemaFromWidgetState() {
        const widgetState = window.neurobagelWidgetState || {};
        const allColumns = widgetState.allColumns || {};
    
        const annotatedData = {};
    
        // Keep only columns present in current preview/local participants context.
        const tsvColumnMap = window.participantsTsvData || {};
        const tsvColumns = Object.keys(tsvColumnMap);
    
        function normalizeColName(value) {
            return String(value || '').toLowerCase().replace(/_/g, '').trim();
        }
    
        function normalizeSchemaToken(value) {
            return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '').trim();
        }
    
        function isParticipantIdMappedColumn(colData) {
            if (!colData || typeof colData !== 'object') return false;
    
            const standardizedVariable = normalizeSchemaToken(colData.standardized_variable);
            const termUrl = String(colData.term_url || '').trim().toLowerCase();
            const label = normalizeSchemaToken(colData.label);
    
            return standardizedVariable === 'participantid'
                || termUrl === 'nb:participantid'
                || label === 'participantid'
                || label === 'subjectid';
        }
    
        function resolveCanonicalLevelKeyForSave(colData, rawKey, rawLevelData) {
            // Preserve source keys as-is; keys must match TSV source values.
            return String(rawKey || '').trim();
        }
    
        for (const [colName, colData] of Object.entries(allColumns)) {
            const colNameNormalized = normalizeColName(colName);
            const matchedTsvColumn = tsvColumns.find(c => {
                const cNorm = normalizeColName(c);
                return cNorm === colNameNormalized || cNorm === String(colName || '').toLowerCase();
            });
    
            if (!matchedTsvColumn) {
                continue;
            }
    
            const normalizedType = String(colData.data_type || '').toLowerCase();
            const isCategorical = normalizedType === 'categorical';
    
            let retainedLevels = [];
            if (isCategorical) {
                const rawLevels = (colData.levels && typeof colData.levels === 'object')
                    ? Object.entries(colData.levels)
                    : [];
    
                const normalizedLevelMap = {};
                rawLevels.forEach(([levelKey, levelData]) => {
                    const sourceKey = String(levelKey || '').trim();
                    if (!sourceKey) return;
    
                    const key = resolveCanonicalLevelKeyForSave(colData, sourceKey, levelData) || sourceKey;
                    const nextLevel = {
                        label: (levelData && levelData.label) ? levelData.label : key,
                        description: (levelData && levelData.description) ? levelData.description : '',
                        uri: (levelData && levelData.uri) ? levelData.uri : null,
                    };
    
                    if (!normalizedLevelMap[key]) {
                        normalizedLevelMap[key] = nextLevel;
                        return;
                    }
    
                    if (!normalizedLevelMap[key].description && nextLevel.description) {
                        normalizedLevelMap[key].description = nextLevel.description;
                    }
                    if (!normalizedLevelMap[key].uri && nextLevel.uri) {
                        normalizedLevelMap[key].uri = nextLevel.uri;
                    }
                });
    
                retainedLevels = Object.entries(normalizedLevelMap);
            }
    
            const targetColumnName = isParticipantIdMappedColumn(colData)
                ? 'participant_id'
                : matchedTsvColumn;
    
            annotatedData[targetColumnName] = {
                Description: colData.description || colData.Description || ""
            };
    
            if (colData.unit) {
                annotatedData[targetColumnName].Unit = colData.unit;
            }
    
            if (isCategorical && retainedLevels.length > 0) {
                annotatedData[targetColumnName].Levels = {};
                for (const [levelKey, levelData] of retainedLevels) {
                    annotatedData[targetColumnName].Levels[levelKey] = levelData.label || levelKey;
                }
            }
    
            const knownNBMappings = Object.values(window.neurobagelCommonMappings || {});
            const isKnownNBTerm = (sv, tu) => knownNBMappings.some(m => m && (
                (sv && String(m.standardized_variable || '').trim().toLowerCase() === String(sv).trim().toLowerCase()) ||
                (tu && String(m.term_url || '').trim().toLowerCase() === String(tu).trim().toLowerCase())
            ));
            const hasNeurobagelMapping = isKnownNBTerm(colData.standardized_variable, colData.term_url);
            const hasManualType = !!colData.data_type;
            if (hasNeurobagelMapping || hasManualType) {
                const annotations = {};
                if (hasNeurobagelMapping) {
                    const termUrl = colData.term_url || (colData.standardized_variable ? `nb:${colData.standardized_variable}` : null);
                    const termLabel = colData.label || colData.standardized_variable || null;
                    if (termUrl || termLabel) {
                        annotations.IsAbout = {
                            "TermURL": termUrl,
                            "Label": termLabel
                        };
                    }
                }
    
                if (colData.data_type) {
                    const normalizedVarType = {
                        'categorical': 'Categorical',
                        'continuous': 'Continuous',
                        'text': 'Text',
                        'string': 'Text',
                        'identifier': 'Text',
                    };
                    annotations.VariableType = normalizedVarType[String(colData.data_type).toLowerCase()] ||
                        (colData.data_type.charAt(0).toUpperCase() + colData.data_type.slice(1));
                }
    
                if (colData.data_type === 'continuous' && colData.unit) {
                    annotatedData[targetColumnName].Units = colData.unit;
                    annotations.Format = {
                        "TermURL": "nb:FromFloat",
                        "Label": "Float"
                    };
                }
    
                if (isCategorical && retainedLevels.length > 0) {
                    const annotationLevels = {};
                    for (const [levelKey, levelData] of retainedLevels) {
                        if (levelData.uri) {
                            annotationLevels[levelKey] = {
                                "TermURL": levelData.uri,
                                "Label": levelData.label || levelKey
                            };
                        }
                    }
                    if (Object.keys(annotationLevels).length > 0) {
                        annotations.Levels = annotationLevels;
                    }
                }
    
                if (Object.keys(annotations).length > 0) {
                    annotatedData[targetColumnName].Annotations = annotations;
                }
            }
        }
    
        return annotatedData;
    }
    
    // Convert button handler
    document.getElementById('participantsConvertBtn')?.addEventListener('click', async function() {
        const errorDiv = document.getElementById('participantsError');
        const successDiv = document.getElementById('participantsSuccess');
        const progressDiv = document.getElementById('participantsConversionProgress');
        const logDiv = document.getElementById('participantsConversionLog');
        const warningDiv = document.getElementById('participantsExistingFilesWarning');
        
        errorDiv.classList.add('d-none');
        successDiv.classList.add('d-none');
        
        // Check existing files only when starting real conversion
        const existingCheck = await checkExistingParticipantFiles();
        if (existingCheck && existingCheck.exists) {
            const checkbox = document.getElementById('participantsForceOverwrite');
            if (!checkbox.checked) {
                errorDiv.textContent = 'Existing participants files detected. Confirm overwrite to continue conversion.';
                errorDiv.classList.remove('d-none');
                return;
            }
        }
        
        progressDiv.classList.remove('d-none');
        logDiv.innerHTML = '';
        
        try {
            const fileInput = document.getElementById('participantsDataFile');
            if (!fileInput.files[0]) {
                throw new Error('Please select a file');
            }
    
            if (typeof window.syncNeurobagelActiveEditorToState === 'function') {
                window.syncNeurobagelActiveEditorToState();
            }
    
            const liveAnnotatedSchema = buildAnnotatedParticipantsSchemaFromWidgetState();
            if (liveAnnotatedSchema && Object.keys(liveAnnotatedSchema).length > 0) {
                window.neurobagelSchema = liveAnnotatedSchema;
            }
            
            const formData = new FormData();
            formData.append('mode', 'file');
            formData.append('file', fileInput.files[0]);
            formData.append('force_overwrite', document.getElementById('participantsForceOverwrite')?.checked || false);
            
            const sheet = document.getElementById('participantsSheet').value;
            const idGroup = document.getElementById('participantsIdColumnGroup');
            const idColumn = document.getElementById('participantsIdColumn').value;
            const separator = document.getElementById('participantsSeparator')?.value || 'auto';
            const idSelectionRequired = Boolean(idGroup && !idGroup.classList.contains('d-none'));
            if (sheet) formData.append('sheet', sheet);
            if (idSelectionRequired && (!idColumn || idColumn === 'auto')) {
                throw new Error('Please select the ID column. It will be renamed to participant_id.');
            }
            if (idColumn && (idColumn !== 'auto' || idSelectionRequired)) {
                formData.append('id_column', idColumn);
            }
            formData.append('separator', separator);
    
            const excludedColumns = Array.isArray(window.excludedParticipantColumns)
                ? window.excludedParticipantColumns.map(c => String(c || '').trim()).filter(Boolean)
                : [];
            if (excludedColumns.length > 0) {
                formData.append('excluded_columns', JSON.stringify([...new Set(excludedColumns)]));
            }
            
            // Include the modified neurobagel_schema if available
            if (window.neurobagelSchema) {
                formData.append('neurobagel_schema', JSON.stringify(window.neurobagelSchema));
            }
    
            const response = await fetch('/api/participants-convert', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            // Display log
            if (data.log) {
                data.log.forEach(entry => {
                    const line = document.createElement('div');
                    line.textContent = `[${entry.level}] ${entry.message}`;
                    line.className = entry.level === 'ERROR' ? 'text-danger' : (entry.level === 'WARNING' ? 'text-warning' : 'text-success');
                    logDiv.appendChild(line);
                });
            }
            
            if (!response.ok) {
                throw new Error(data.error || 'Conversion failed');
            }
            
            const writtenFiles = Array.isArray(data.files_created) ? data.files_created : [];
            const outputDirectory = typeof data.output_directory === 'string' ? data.output_directory.trim() : '';
            const overwriteNote = data.overwrote_existing
                ? '<div class="mt-2 small text-muted">Existing participants files were overwritten.</div>'
                : '';
            const locationNote = outputDirectory
                ? `<div class="mt-1 small text-muted">Written to: <code>${escapeHtml(outputDirectory)}</code></div>`
                : '';

            // Show success
            successDiv.innerHTML = `
                <i class="fas fa-check-circle me-2"></i>
                <strong>Success!</strong> Wrote ${writtenFiles.length} file(s):
                <ul class="mb-0 mt-2">
                    ${writtenFiles.map(f => `<li><code>${escapeHtml(f.split('/').pop())}</code></li>`).join('')}
                </ul>
                ${overwriteNote}
                ${locationNote}
                <div class="mt-2 small text-muted">Refreshing preview…</div>
            `;
            successDiv.classList.remove('d-none');
    
            // Conversion created/updated participants files. Clear stale preview schema
            // so Annotate Participants loads from the saved project participants.json.
            window.lastParticipantsPreviewData = null;
    
            // Refresh local participants.tsv columns cache used by the annotation widget.
            const projectPath = resolveCurrentProjectPath();
            if (projectPath) {
                try {
                    const tsvResponse = await fetch(`/api/neurobagel/local-participants?project_path=${encodeURIComponent(projectPath)}`);
                    const tsvData = await tsvResponse.json();
                    if (tsvData.columns) {
                        window.participantsTsvData = tsvData.columns;
                    }
                } catch (error) {
                    console.warn('Could not refresh participants TSV columns after conversion:', error);
                }
            }
            
            // Hide warning
            warningDiv.classList.add('d-none');
    
            // Auto-refresh preview so users immediately see updated participant columns.
            const previewBtn = document.getElementById('participantsPreviewBtn');
            if (previewBtn && fileInput && fileInput.files && fileInput.files[0]) {
                setTimeout(() => {
                    try {
                        previewBtn.click();
                    } catch (e) {
                        console.warn('Could not auto-refresh participants preview:', e);
                    }
                }, 100);
            }
            
        } catch (error) {
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('d-none');
        } finally {
            progressDiv.classList.add('d-none');
        }
    });
    
    // ===== NEUROBAGEL ANNOTATION HANDLERS =====
    
    // Function to open participants.json editor
    function openParticipantsEditor() {
        const currentProjectPath = resolveCurrentProjectPath();
        if (!currentProjectPath) {
            const errorDiv = document.getElementById('participantsError');
            errorDiv.textContent = 'Please select a project first from the top of the page';
            errorDiv.classList.remove('d-none');
            return;
        }
        
        // Navigate to JSON editor with autoload flag and file type
        window.location.href = `${jsonEditorUrl}?autoload=participants&from=converter`;
    }
    
    document.getElementById('saveNeurobagelBtn')?.addEventListener('click', async function() {
        const saveBtn = this;
        const originalLabel = saveBtn.innerHTML;
        const errorDiv = document.getElementById('participantsError');
    
        if (errorDiv) {
            errorDiv.classList.add('d-none');
            errorDiv.textContent = '';
        }
    
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
    
        try {
            if (typeof window.syncNeurobagelActiveEditorToState === 'function') {
                window.syncNeurobagelActiveEditorToState();
            }
    
            const annotatedData = buildAnnotatedParticipantsSchemaFromWidgetState();
            if (!annotatedData || Object.keys(annotatedData).length === 0) {
                throw new Error('No participant annotation data available. Run Preview Data first.');
            }
        
            // Save to the project
            const response = await fetch('/api/projects/participants', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    schema: annotatedData,
                })
            });
            
            const result = await response.json();
            if (result.success) {
                const savedSchema = (result.schema && typeof result.schema === 'object')
                    ? result.schema
                    : annotatedData;
                const successDiv = document.getElementById('participantsSuccess');
                successDiv.innerHTML = '<i class="fas fa-check-circle me-2"></i><strong>Success!</strong> Participants schema saved to participants.json';
                successDiv.classList.remove('d-none');
    
                window.neurobagelSchema = savedSchema;
                window.existingParticipantsData = savedSchema;
    
                if (window.lastParticipantsPreviewData) {
                    window.lastParticipantsPreviewData.neurobagel_schema = savedSchema;
                    renderParticipantsPreviewTable(window.lastParticipantsPreviewData, savedSchema);
                }
    
                displayNeurobagelSchema(savedSchema);
                
                // Keep the editor open so user can continue annotating
                // document.getElementById('neurobagelSection').style.display = 'none';
                // document.getElementById('participantsHelp').style.display = 'block';
            } else {
                throw new Error(result.error || 'Failed to save participants schema');
            }
        } catch (error) {
            if (errorDiv) {
                errorDiv.textContent = `Error saving participants schema: ${error.message}`;
                errorDiv.classList.remove('d-none');
            }
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalLabel;
        }
    });
    
    window.loadNeurobagelWidget = async function() {
        const container = document.getElementById('neurobagelWidgetContainer');
        if (!container) return;
    
        const mergeParticipantColumnMaps = (baseMap, incomingMap) => {
            const merged = (baseMap && typeof baseMap === 'object') ? { ...baseMap } : {};
            if (!incomingMap || typeof incomingMap !== 'object') return merged;
    
            Object.entries(incomingMap).forEach(([columnName, values]) => {
                const cleanedName = String(columnName || '').trim();
                if (!cleanedName) return;
    
                const baseValues = Array.isArray(merged[cleanedName]) ? merged[cleanedName] : [];
                const incomingValues = Array.isArray(values) ? values : [];
                merged[cleanedName] = Array.from(
                    new Set([
                        ...baseValues.map(v => String(v ?? '').trim()).filter(Boolean),
                        ...incomingValues.map(v => String(v ?? '').trim()).filter(Boolean),
                    ])
                ).slice(0, 50);
            });
    
            return merged;
        };
    
        // Keep preview-derived columns (including newly added variables) as baseline.
        const hasActivePreview = !!(window.participantsTsvData && typeof window.participantsTsvData === 'object' && Object.keys(window.participantsTsvData).length > 0);
        let participantsColumnMap = hasActivePreview
            ? { ...window.participantsTsvData }
            : {};
    
        const hasPreviewSchema = !!(window.lastParticipantsPreviewData && window.lastParticipantsPreviewData.neurobagel_schema);
    
        // Prefer currently saved project participants.json (important after conversion).
        let loadedProjectSchema = false;
        try {
            const schemaResponse = await fetch('/api/projects/participants');
            const schemaData = await schemaResponse.json();
            if (schemaData.success && schemaData.exists && schemaData.schema) {
                window.existingParticipantsData = schemaData.schema;
                loadedProjectSchema = true;
            }
        } catch (error) {
            console.warn('Could not load existing participants schema:', error);
        }
    
        // Fallback to current preview schema only if no saved project schema exists yet.
        if (!loadedProjectSchema && hasPreviewSchema) {
            window.existingParticipantsData = window.lastParticipantsPreviewData.neurobagel_schema;
        }
    
        // Only fetch project participants.tsv columns when there is NO active preview.
        // When a preview is active, the uploaded file's columns are the source of truth
        // for AVAILABLE/UNANNOTATED — merging stale on-disk columns would falsely show
        // columns as AVAILABLE that aren't in the current upload.
        const projectPath = resolveCurrentProjectPath();
        if (!hasActivePreview) {
            console.log('🔄 No active preview — fetching participants TSV columns from project...');
            try {
                const tsvResponse = await fetch(`/api/neurobagel/local-participants?project_path=${encodeURIComponent(projectPath)}`);
                console.log('📡 TSV columns response status:', tsvResponse.status);
                const tsvData = await tsvResponse.json();
                console.log('📊 TSV columns data:', tsvData);
                if (tsvData.columns) {
                    participantsColumnMap = mergeParticipantColumnMaps(participantsColumnMap, tsvData.columns);
                } else if (tsvData.error) {
                    console.error('❌ API returned error:', tsvData.error);
                }
            } catch (error) {
                console.error('❌ Could not load participants TSV columns:', error);
            }
        } else {
            console.log('🔄 Active preview present — using preview columns only for AVAILABLE detection.');
        }
    
        if (Array.isArray(window.pendingAdditionalParticipantColumns) && window.pendingAdditionalParticipantColumns.length > 0) {
            window.pendingAdditionalParticipantColumns.forEach((columnName) => {
                const cleanedName = String(columnName || '').trim();
                if (cleanedName && !Object.prototype.hasOwnProperty.call(participantsColumnMap, cleanedName)) {
                    participantsColumnMap[cleanedName] = [];
                }
            });
        }
    
        window.participantsTsvData = participantsColumnMap;
        console.log('✅ Set window.participantsTsvData:', Object.keys(window.participantsTsvData));
        
        // Check if widget is already loaded
        if (container.querySelector('#neurobagelAnnotationWidget')) {
            // Just re-render to update with latest TSV data if needed
            if (window.renderNeurobagelWidget) {
                await window.renderNeurobagelWidget();
            }
            return;
        }
        
        try {
            // Load the neurobagel widget HTML
            const response = await fetch(neurobagelWidgetUrl);
            if (response.ok) {
                const html = await response.text();
                
                // Parse HTML to separate markup from scripts
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                
                // Find and remove scripts
                const scripts = doc.querySelectorAll('script');
                const scriptTexts = [];
                scripts.forEach(script => {
                    scriptTexts.push(script.textContent);
                    script.remove();
                });
                
                // Insert the HTML without scripts
                container.innerHTML = doc.body.innerHTML;
                
                // Execute scripts in order
                scriptTexts.forEach(scriptText => {
                    try {
                        new Function(scriptText)();
                    } catch (err) {
                        console.error('Error executing widget script:', err);
                    }
                });
                
                // Initialize widget after a short delay
                await new Promise(resolve => setTimeout(resolve, 100));
                if (window.renderNeurobagelWidget) {
                    await window.renderNeurobagelWidget();
                }
    
                // Wrap renderNeurobagelSidebar so custom column additions/removals
                // are immediately reflected in the preview table.
                const _origSidebar = window.renderNeurobagelSidebar;
                if (typeof _origSidebar === 'function') {
                    window.renderNeurobagelSidebar = function() {
                        _origSidebar.apply(this, arguments);
                        if (window.lastParticipantsPreviewData) {
                            renderParticipantsPreviewTable(
                                window.lastParticipantsPreviewData,
                                window.neurobagelWidgetState?.schemaOverride || null
                            );
                        }
                    };
                }
            } else {
                container.innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        Use the <a href="https://annotate.neurobagel.org/" target="_blank">NeuroBagel Annotation Tool</a> 
                        to annotate your participants.json file, then import it back here.
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading NeuroBagel widget:', error);
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Could not load embedded widget (${error.message}). Use the external 
                    <a href="https://annotate.neurobagel.org/" target="_blank">NeuroBagel Annotation Tool</a>.
                </div>
            `;
        }
    }
    
}
