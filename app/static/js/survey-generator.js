<script>
document.addEventListener('DOMContentLoaded', function() {
    const libraryContent = document.getElementById('libraryContent');
    const libraryEmpty = document.getElementById('libraryEmpty');
    const libraryError = document.getElementById('libraryError');
    const generateLssBtn = document.getElementById('generateLssBtn');
    const generateBoilerplateBtn = document.getElementById('generateBoilerplateBtn');
    const customizeExportBtn = document.getElementById('customizeExportBtn');
    const toolbarCard = document.getElementById('toolbarCard');
    const baseLanguageSelect = document.getElementById('baseLanguageSelect');
    const exportLanguageCheckboxes = document.getElementById('exportLanguageCheckboxes');
    const languageWarnings = document.getElementById('languageWarnings');
    const languageWarningList = document.getElementById('languageWarningList');
    const sourceInfoText = document.getElementById('sourceInfoText');
    const reloadLibraryBtn = document.getElementById('reloadLibraryBtn');
    const templateSearch = document.getElementById('templateSearch');
    const targetToolSelect = document.getElementById('targetToolSelect');

    let currentLibraryData = null;
    let currentLanguage = 'en';
    let selectedExportLanguages = ['en'];
    let allDetectedLanguages = [];

    // Target tool configuration
    const toolConfig = {
        limesurvey: { label: 'LimeSurvey', exportEndpoint: '/api/generate-lss', fileExt: '.lss', optionsClass: 'tool-options-limesurvey' },
        // Future tools:
        // redcap: { label: 'REDCap', exportEndpoint: '/api/generate-redcap', fileExt: '.csv', optionsClass: 'tool-options-redcap' },
        // qualtrics: { label: 'Qualtrics', exportEndpoint: '/api/generate-qsf', fileExt: '.qsf', optionsClass: 'tool-options-qualtrics' },
    };

    function getSelectedTool() { return targetToolSelect.value; }
    function getToolConfig() { return toolConfig[getSelectedTool()] || toolConfig.limesurvey; }

    // Helper: Button loading state
    function setButtonLoading(btn, isLoading, loadingText = 'Loading...', originalText = null) {
        if (isLoading) {
            const current = btn.innerHTML;
            btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>${loadingText}`;
            btn.disabled = true;
            return current;
        } else {
            btn.innerHTML = originalText || btn.innerHTML.replace(/<i[^>]*spinner[^>]*>.*?<\/i>\s*/, '');
            btn.disabled = false;
            return null;
        }
    }

    // Show/hide tool-specific option groups based on selected tool
    function updateToolOptions() {
        const tool = getSelectedTool();
        Object.values(toolConfig).forEach(cfg => {
            document.querySelectorAll('.' + cfg.optionsClass).forEach(el => {
                el.style.display = 'none';
            });
        });
        const activeCfg = toolConfig[tool];
        if (activeCfg) {
            document.querySelectorAll('.' + activeCfg.optionsClass).forEach(el => {
                el.style.display = '';
            });
        }
        // Update Quick Export button label
        generateLssBtn.innerHTML = `<i class="fas fa-file-export me-1"></i>Quick Export (${activeCfg ? activeCfg.fileExt : ''})`;
    }

    targetToolSelect.addEventListener('change', updateToolOptions);

    const sectionConfig = {
        survey:       { container: 'surveySection',       list: 'surveyList',       count: 'surveyCount' },
        biometrics:   { container: 'biometricsSection',   list: 'biometricsList',   count: 'biometricsCount' },
        participants: { container: 'participantsSection',  list: 'participantsList',  count: 'participantsCount' },
        other:        { container: 'otherSection',         list: 'otherList',         count: 'otherCount' },
    };

    function getText(obj, lang) {
        if (!obj) return '';
        if (typeof obj === 'string') return obj;
        if (typeof obj === 'object') return obj[lang] || obj['en'] || Object.values(obj)[0] || '';
        return '';
    }

    function escapeHtml(s) {
        if (!s) return '';
        const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
    }

    function sourceBadgeHtml(source) {
        if (source === 'both') return '<span class="badge source-badge-both">Global + Project</span>';
        if (source === 'project') return '<span class="badge source-badge-project">Project</span>';
        return '<span class="badge source-badge-global">Global</span>';
    }

    function hasAllExportLanguages(fileLangs) {
        // Template must have ALL selected export languages
        return selectedExportLanguages.every(lang => fileLangs.includes(lang));
    }

    // --- Build a compact template row ---
    function createTemplateRow(file, index, sectionKey) {
        const fileId = `tpl-${sectionKey}-${index}`;
        const detailsId = `details-${sectionKey}-${index}`;
        const fileLangs = file.detected_languages || ['en'];
        const hasLang = hasAllExportLanguages(fileLangs);

        const div = document.createElement('div');
        div.className = `tpl-row ${hasLang ? '' : 'tpl-no-lang'}`;
        div.dataset.filename = (file.filename || '').toLowerCase();
        div.dataset.originalName = getText(file.original_name, 'en').toLowerCase();
        div.dataset.description = getText(file.description, 'en').toLowerCase();
        div.dataset.detectedLanguages = fileLangs.join(',');
        div.dataset.filePath = file.path;
        div.dataset.sectionKey = sectionKey;
        div.dataset.index = index;

        const origName = getText(file.original_name, currentLanguage);
        const desc = getText(file.description, currentLanguage);
        const itemCount = file.question_count || 0;

        // Matrix detection
        const hasPotentialMatrix = (() => {
            const levelMap = new Map();
            (file.questions || []).forEach(q => {
                if (q.levels && Object.keys(q.levels).length > 0) {
                    const s = JSON.stringify(q.levels);
                    if (!levelMap.has(s)) levelMap.set(s, 0);
                    levelMap.set(s, levelMap.get(s) + 1);
                }
            });
            for (const c of levelMap.values()) { if (c > 1) return true; }
            return false;
        })();

        div.innerHTML = `
            <div class="d-flex align-items-center">
                <input class="form-check-input file-checkbox me-2 flex-shrink-0" type="checkbox" value="${escapeHtml(file.path)}"
                       id="${fileId}" data-details-id="${detailsId}"
                       data-filename="${escapeHtml(file.filename)}"
                       data-detected-languages="${fileLangs.join(',')}"
                       ${hasLang ? '' : 'disabled'}>
                <div class="flex-grow-1 min-width-0">
                    <div class="d-flex align-items-center flex-wrap gap-1">
                        <span class="tpl-name">${escapeHtml(origName || file.filename)}</span>
                        ${sourceBadgeHtml(file.source)}
                        <span class="badge bg-secondary" style="font-size:0.65rem;">${itemCount} items</span>
                        ${fileLangs.map(l => `<span class="lang-badge ${l === currentLanguage ? 'lang-badge-available' : ''}" style="font-size:0.6rem;">${l.toUpperCase()}</span>`).join('')}
                        ${hasPotentialMatrix ? '<span class="badge bg-success" style="font-size:0.6rem;"><i class="fas fa-th me-1"></i>Matrix</span>' : ''}
                        ${!hasLang ? `<span class="badge bg-danger tpl-missing-badge" style="font-size:0.6rem;">Missing: ${selectedExportLanguages.filter(l => !fileLangs.includes(l)).map(l => l.toUpperCase()).join(', ')}</span>` : ''}
                    </div>
                    ${desc ? `<div class="tpl-desc">${escapeHtml(desc)}</div>` : ''}
                </div>
                <button class="btn btn-sm btn-link text-muted p-0 ms-2 flex-shrink-0 tpl-expand-btn" data-target="${detailsId}" title="Show details & questions">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </div>
            <!-- Settings row (visible when selected) -->
            <div class="tpl-settings-row d-none" id="settings-${fileId}">
                <label><input type="checkbox" class="form-check-input matrix-checkbox me-1" ${hasPotentialMatrix ? 'checked' : ''}> Matrix</label>
                <label><input type="checkbox" class="form-check-input global-matrix-checkbox me-1" checked> Global</label>
                <label>Run: <input type="number" class="form-control form-control-sm run-number-input d-inline-block ms-1" min="1" max="99" value="1" style="width:50px;"></label>
            </div>
            <!-- Expandable details -->
            <div class="tpl-questions-panel d-none" id="${detailsId}">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-muted fw-bold">Questions (${itemCount})</small>
                    <div>
                        <button class="btn btn-link btn-sm p-0 text-secondary select-all-q me-2" data-target="${detailsId}">All</button>
                        <button class="btn btn-link btn-sm p-0 text-secondary deselect-all-q" data-target="${detailsId}">None</button>
                    </div>
                </div>
                ${(file.questions || []).map(q => {
                    const qDesc = getText(q.description, currentLanguage);
                    const levelsCount = q.levels ? Object.keys(q.levels).length : 0;
                    return `<div class="q-item d-flex align-items-baseline">
                        <input class="form-check-input question-checkbox me-2 flex-shrink-0" type="checkbox" value="${escapeHtml(q.id)}" checked>
                        <span class="q-id me-2">${escapeHtml(q.id)}</span>
                        <span class="q-desc flex-grow-1">${escapeHtml(qDesc)}</span>
                        ${levelsCount > 0 ? `<span class="q-levels-inline flex-shrink-0">${levelsCount} levels</span>` : ''}
                    </div>`;
                }).join('')}
                ${file.study ? `
                <div class="border-top mt-2 pt-2">
                    <div class="row small text-muted">
                        <div class="col-auto">${file.study.Authors ? `<b>Authors:</b> ${escapeHtml(Array.isArray(file.study.Authors) ? file.study.Authors.join(', ') : file.study.Authors)}` : ''}</div>
                        <div class="col-auto">${file.study.DOI ? `<b>DOI:</b> <a href="https://doi.org/${file.study.DOI}" target="_blank">${escapeHtml(file.study.DOI)}</a>` : ''}</div>
                        <div class="col-auto">${file.study.LicenseID ? `<b>License:</b> ${escapeHtml(file.study.LicenseID)}` : ''}</div>
                        <div class="col-auto">${file.study.ItemCount ? `<b>Items:</b> ${file.study.ItemCount}` : ''}</div>
                    </div>
                </div>` : ''}
            </div>
        `;

        // Toggle expand
        div.querySelector('.tpl-expand-btn').addEventListener('click', function(e) {
            e.stopPropagation();
            const panel = document.getElementById(this.dataset.target);
            const icon = this.querySelector('i');
            if (panel.classList.contains('d-none')) {
                panel.classList.remove('d-none');
                icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
            } else {
                panel.classList.add('d-none');
                icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
            }
        });

        // Toggle checkbox shows settings row
        const checkbox = div.querySelector('.file-checkbox');
        const settingsRow = div.querySelector(`#settings-${fileId}`);
        checkbox.addEventListener('change', function() {
            if (this.checked) {
                div.classList.add('tpl-selected');
                settingsRow.classList.remove('d-none');
            } else {
                div.classList.remove('tpl-selected');
                settingsRow.classList.add('d-none');
            }
            updateGenerateBtn();
            validateLanguageCoverage();
        });

        return div;
    }

    // --- Render ---
    function renderLibrary() {
        if (!currentLibraryData) return;

        let hasAnyFiles = false;
        let hasAnyVisible = false;
        Object.keys(sectionConfig).forEach(key => {
            const cfg = sectionConfig[key];
            const container = document.getElementById(cfg.container);
            const listEl = document.getElementById(cfg.list);
            const countEl = document.getElementById(cfg.count);
            listEl.innerHTML = '';

            const files = currentLibraryData[key];
            if (files && files.length > 0) {
                hasAnyFiles = true;
                // Count files that have all export languages
                const visibleFiles = files.filter(f => hasAllExportLanguages(f.detected_languages || ['en']));
                const totalFiles = files.length;

                container.classList.remove('d-none');
                countEl.textContent = visibleFiles.length < totalFiles
                    ? `(${visibleFiles.length}/${totalFiles})`
                    : `(${totalFiles})`;

                files.forEach((file, idx) => {
                    const row = createTemplateRow(file, idx, key);
                    listEl.appendChild(row);
                    if (hasAllExportLanguages(file.detected_languages || ['en'])) hasAnyVisible = true;
                });
            } else {
                container.classList.add('d-none');
            }
        });

        if (hasAnyFiles) {
            libraryContent.classList.remove('d-none');
            libraryEmpty.classList.add('d-none');
        } else {
            libraryContent.classList.add('d-none');
            libraryEmpty.classList.remove('d-none');
        }
        updateGenerateBtn();
        applySearchFilter();
    }

    // --- Search ---
    templateSearch.addEventListener('input', applySearchFilter);

    function applySearchFilter() {
        const query = templateSearch.value.trim().toLowerCase();
        document.querySelectorAll('.tpl-row').forEach(row => {
            if (!query) {
                row.classList.remove('tpl-hidden-search');
                return;
            }
            const fn = row.dataset.filename || '';
            const on = row.dataset.originalName || '';
            const desc = row.dataset.description || '';
            const match = fn.includes(query) || on.includes(query) || desc.includes(query);
            if (match) row.classList.remove('tpl-hidden-search');
            else row.classList.add('tpl-hidden-search');
        });
    }

    // --- Language Management ---
    function buildLanguageUI(detectedLangs) {
        allDetectedLanguages = detectedLangs;
        if (detectedLangs.length === 0) {
            toolbarCard.classList.add('d-none');
            currentLanguage = 'en';
            selectedExportLanguages = ['en'];
            return;
        }

        baseLanguageSelect.innerHTML = '';
        detectedLangs.forEach(lang => {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang.toUpperCase();
            if (lang === 'en') opt.selected = true;
            baseLanguageSelect.appendChild(opt);
        });
        currentLanguage = baseLanguageSelect.value || detectedLangs[0];

        exportLanguageCheckboxes.innerHTML = '';
        selectedExportLanguages = [currentLanguage];
        detectedLangs.forEach(lang => {
            const isBase = lang === currentLanguage;
            const wrapper = document.createElement('div');
            wrapper.className = 'form-check form-check-inline mb-0';
            wrapper.innerHTML = `
                <input class="form-check-input export-lang-cb" type="checkbox" value="${lang}"
                       id="export-lang-${lang}" ${isBase ? 'checked' : ''}>
                <label class="form-check-label small" for="export-lang-${lang}">${lang.toUpperCase()}</label>
            `;
            exportLanguageCheckboxes.appendChild(wrapper);
            wrapper.querySelector('input').addEventListener('change', function() {
                updateSelectedExportLanguages();
                updateLanguageFiltering();
                validateLanguageCoverage();
            });
        });
        toolbarCard.classList.remove('d-none');
    }

    function updateSelectedExportLanguages() {
        selectedExportLanguages = [];
        document.querySelectorAll('.export-lang-cb:checked').forEach(cb => selectedExportLanguages.push(cb.value));
        if (!selectedExportLanguages.includes(currentLanguage)) {
            selectedExportLanguages.unshift(currentLanguage);
            const baseCb = document.getElementById(`export-lang-${currentLanguage}`);
            if (baseCb) baseCb.checked = true;
        }
    }

    // Re-apply language filtering to existing rows without full re-render
    function updateLanguageFiltering() {
        document.querySelectorAll('.tpl-row').forEach(row => {
            const fileLangs = (row.dataset.detectedLanguages || 'en').split(',');
            const hasAll = hasAllExportLanguages(fileLangs);
            const cb = row.querySelector('.file-checkbox');
            const missingBadge = row.querySelector('.tpl-missing-badge');

            if (hasAll) {
                row.classList.remove('tpl-no-lang');
                if (cb) cb.disabled = false;
                if (missingBadge) missingBadge.remove();
            } else {
                row.classList.add('tpl-no-lang');
                if (cb) {
                    // Uncheck and deselect if it was checked
                    if (cb.checked) {
                        cb.checked = false;
                        row.classList.remove('tpl-selected');
                        const settingsRow = row.querySelector('[id^="settings-"]');
                        if (settingsRow) settingsRow.classList.add('d-none');
                    }
                    cb.disabled = true;
                }
                // Update or add missing badge
                const missingLangs = selectedExportLanguages.filter(l => !fileLangs.includes(l)).map(l => l.toUpperCase()).join(', ');
                if (missingBadge) {
                    missingBadge.textContent = `Missing: ${missingLangs}`;
                } else {
                    const badgeRow = row.querySelector('.d-flex.align-items-center.flex-wrap');
                    if (badgeRow) {
                        const badge = document.createElement('span');
                        badge.className = 'badge bg-danger tpl-missing-badge';
                        badge.style.fontSize = '0.6rem';
                        badge.textContent = `Missing: ${missingLangs}`;
                        badgeRow.appendChild(badge);
                    }
                }
            }
        });
        // Update section counts
        Object.keys(sectionConfig).forEach(key => {
            const cfg = sectionConfig[key];
            const listEl = document.getElementById(cfg.list);
            const countEl = document.getElementById(cfg.count);
            if (!listEl || !countEl) return;
            const allRows = listEl.querySelectorAll('.tpl-row');
            const visibleRows = listEl.querySelectorAll('.tpl-row:not(.tpl-no-lang)');
            if (allRows.length === 0) return;
            countEl.textContent = visibleRows.length < allRows.length
                ? `(${visibleRows.length}/${allRows.length})`
                : `(${allRows.length})`;
        });
        updateGenerateBtn();
    }

    function validateLanguageCoverage() {
        const warnings = [];
        document.querySelectorAll('.file-checkbox:checked').forEach(cb => {
            const fileLangs = (cb.dataset.detectedLanguages || 'en').split(',');
            const filename = cb.dataset.filename || 'unknown';
            selectedExportLanguages.forEach(lang => {
                if (!fileLangs.includes(lang)) {
                    warnings.push(`<li class="lang-warning-item"><code>${filename}</code> may not have <strong>${lang.toUpperCase()}</strong> translations</li>`);
                }
            });
        });
        if (warnings.length > 0) {
            languageWarningList.innerHTML = warnings.join('');
            languageWarnings.classList.remove('d-none');
        } else {
            languageWarnings.classList.add('d-none');
        }
    }

    baseLanguageSelect.addEventListener('change', function() {
        currentLanguage = this.value;
        const baseCb = document.getElementById(`export-lang-${currentLanguage}`);
        if (baseCb && !baseCb.checked) baseCb.checked = true;
        updateSelectedExportLanguages();
        validateLanguageCoverage();
        renderLibrary();
    });

    // --- Load ---
    async function loadMergedLibrary() {
        libraryContent.classList.add('d-none');
        libraryEmpty.classList.add('d-none');
        libraryError.classList.add('d-none');
        toolbarCard.classList.add('d-none');
        sourceInfoText.textContent = 'Loading...';

        try {
            const response = await fetch('/api/list-library-files-merged');
            const data = await response.json();
            if (data.error) {
                libraryError.textContent = data.error;
                libraryError.classList.remove('d-none');
                sourceInfoText.textContent = 'Failed to load.';
                return;
            }

            currentLibraryData = data;

            const sources = data.sources || {};
            const parts = [];
            if (sources.global_library_path) parts.push(`Global: ${sources.global_library_path}`);
            if (sources.project_library_path && sources.project_library_exists) parts.push(`Project: ${sources.project_library_path}`);
            else if (sources.project_library_path) parts.push(`Project: not found`);
            sourceInfoText.textContent = parts.length > 0 ? parts.join('  |  ') : 'No libraries configured';

            const langSet = new Set();
            ['participants', 'survey', 'biometrics', 'other'].forEach(key => {
                (data[key] || []).forEach(file => {
                    (file.detected_languages || []).forEach(l => langSet.add(l));
                });
            });
            buildLanguageUI(Array.from(langSet).sort());
            renderLibrary();
        } catch (err) {
            libraryError.textContent = 'Error loading: ' + err;
            libraryError.classList.remove('d-none');
            sourceInfoText.textContent = 'Failed.';
        }
    }

    reloadLibraryBtn.addEventListener('click', loadMergedLibrary);

    // --- Section Select/Deselect ---
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.select-all-section, .deselect-all-section');
        if (!btn) return;
        const targetId = btn.dataset.target;
        const el = document.getElementById(targetId);
        if (!el) return;
        const isSelect = btn.classList.contains('select-all-section');
        el.querySelectorAll('.file-checkbox:not(:disabled)').forEach(cb => {
            cb.checked = isSelect;
            const row = cb.closest('.tpl-row');
            const settingsRow = row.querySelector('[id^="settings-"]');
            if (isSelect) { row.classList.add('tpl-selected'); settingsRow?.classList.remove('d-none'); }
            else { row.classList.remove('tpl-selected'); settingsRow?.classList.add('d-none'); }
        });
        updateGenerateBtn();
        validateLanguageCoverage();
    });

    // Question select/deselect all
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.select-all-q, .deselect-all-q');
        if (!btn) return;
        const targetId = btn.dataset.target;
        const panel = document.getElementById(targetId);
        if (!panel) return;
        const checked = btn.classList.contains('select-all-q');
        panel.querySelectorAll('.question-checkbox').forEach(cb => cb.checked = checked);
    });

    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('file-checkbox')) {
            updateGenerateBtn();
            validateLanguageCoverage();
        }
    });

    function updateGenerateBtn() {
        const anyChecked = document.querySelectorAll('.file-checkbox:checked').length > 0;
        generateLssBtn.disabled = !anyChecked;
        generateBoilerplateBtn.disabled = !anyChecked;
        customizeExportBtn.disabled = !anyChecked;
    }

    // --- Helper: collect selected files config ---
    function collectSelectedFiles(forCustomizer) {
        const selectedFiles = [];
        document.querySelectorAll('.file-checkbox:checked').forEach(cb => {
            const row = cb.closest('.tpl-row');
            const detailsId = cb.dataset.detailsId;
            const panel = document.getElementById(detailsId);
            const questionCheckboxes = panel ? panel.querySelectorAll('.question-checkbox:checked') : [];
            const selectedQuestions = Array.from(questionCheckboxes).map(qcb => qcb.value);

            const matrixCb = row.querySelector('.matrix-checkbox');
            const globalCb = row.querySelector('.global-matrix-checkbox');
            const runInput = row.querySelector('.run-number-input');

            const isMatrix = matrixCb ? matrixCb.checked : false;
            const isGlobal = globalCb ? globalCb.checked : false;
            const runNumber = runInput ? parseInt(runInput.value, 10) || 1 : 1;

            if (selectedQuestions.length > 0) {
                if (forCustomizer) {
                    selectedFiles.push({
                        path: cb.value,
                        includeQuestions: selectedQuestions,
                        matrix: isMatrix,
                        matrix_global: isGlobal,
                        runNumber: runNumber,
                    });
                } else {
                    const cfg = { path: cb.value, include: selectedQuestions, matrix: isMatrix, matrix_global: isGlobal };
                    if (runNumber > 1) cfg.run = runNumber;
                    selectedFiles.push(cfg);
                }
            }
        });
        return selectedFiles;
    }

    // --- Boilerplate ---
    generateBoilerplateBtn.addEventListener('click', function() {
        const selected = [];
        document.querySelectorAll('.file-checkbox:checked').forEach(cb => selected.push(cb.value));
        if (selected.length === 0) return;

        const originalText = setButtonLoading(generateBoilerplateBtn, true, '...');

        fetch('/api/generate-boilerplate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: selected, language: currentLanguage }),
        })
        .then(r => r.ok ? r.json() : r.json().then(e => { throw new Error(e.error); }))
        .then(data => {
            if (data.md) { downloadBlob(data.md, 'text/markdown', `${data.filename_base}.md`); }
            if (data.html) { downloadBlob(data.html, 'text/html', `${data.filename_base}.html`); }
        })
        .catch(err => alert(err.message))
        .finally(() => {
            setButtonLoading(generateBoilerplateBtn, false, null, originalText);
        });
    });

    // --- Quick Export ---
    generateLssBtn.addEventListener('click', function() {
        const files = collectSelectedFiles(false);
        if (files.length === 0) { alert("Select at least one file and one question."); return; }

        const cfg = getToolConfig();
        const originalText = setButtonLoading(generateLssBtn, true, '...');

        const payload = {
            files, languages: selectedExportLanguages, base_language: currentLanguage,
            language: currentLanguage, target_tool: getSelectedTool(),
        };
        // Tool-specific payload fields
        if (getSelectedTool() === 'limesurvey') {
            payload.ls_version = document.getElementById('lsVersionSelect').value;
        }

        fetch(cfg.exportEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(r => { if (r.ok) return r.blob(); throw new Error('Export failed'); })
        .then(blob => {
            const langSuffix = selectedExportLanguages.length > 1 ? selectedExportLanguages.join('_') : currentLanguage;
            downloadBlobObj(blob, `survey_export_${langSuffix}${cfg.fileExt}`);
        })
        .catch(err => alert(err.message))
        .finally(() => {
            setButtonLoading(generateLssBtn, false, null, originalText);
        });
    });

    // --- Customize & Export ---
    customizeExportBtn.addEventListener('click', function() {
        const files = collectSelectedFiles(true);
        if (files.length === 0) { alert("Select at least one file and one question."); return; }

        const payload = {
            selectedFiles: files,
            languages: selectedExportLanguages,
            base_language: currentLanguage,
            language: currentLanguage,
            target_tool: getSelectedTool(),
        };
        // Tool-specific session data
        if (getSelectedTool() === 'limesurvey') {
            payload.ls_version = document.getElementById('lsVersionSelect').value;
        }

        sessionStorage.setItem('surveyCustomizerData', JSON.stringify(payload));
        window.location.href = '/survey-customizer';
    });

    // --- Utility ---
    function downloadBlob(content, type, filename) {
        const blob = new Blob([content], { type });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = filename;
        document.body.appendChild(a); a.click(); a.remove();
    }
    function downloadBlobObj(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = filename;
        document.body.appendChild(a); a.click(); a.remove();
    }

    // --- Init ---
    updateToolOptions();
    loadMergedLibrary();
});
</script>
