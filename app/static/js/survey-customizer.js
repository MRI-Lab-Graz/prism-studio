document.addEventListener('DOMContentLoaded', function() {
    // State
    let customizationState = {
        survey: {
            title: 'Custom Survey',
            language: 'en',
            languages: ['en'],
            base_language: 'en'
        },
        groups: [],
        exportFormat: 'limesurvey',
        exportOptions: {
            ls_version: '3',
            matrix: true,
            matrix_global: true
        },
        lsSettings: {
            welcomeText: '',
            endText: '',
            endUrl: '',
            endUrlDescription: '',
            showDataPolicy: '0',
            policyNotice: '',
            policyError: '',
            policyCheckboxLabel: '',
            navigationDelay: '0',
            questionIndex: '0',
            showGroupInfo: 'B',
            showQnumCode: 'X',
            showNoAnswer: 'Y',
            showXQuestions: 'Y',
            showWelcome: 'Y',
            allowPrev: 'N',
            noKeyboard: 'N',
            showProgress: 'Y',
            printAnswers: 'N',
            publicStatistics: 'N',
            publicGraphs: 'N',
            autoRedirect: 'N'
        }
    };

    // Original data for reset
    let originalState = null;
    let sortableInstances = [];
    let activeToolSettingsPanel = null; // Track which question has tool settings open
    let previewLanguage = 'en'; // Language shown in question descriptions (independent of export language)
    let detectedLanguages = []; // Languages detected in template content (for preview switcher only)

    // DOM Elements
    const loadingOverlay = document.getElementById('loadingOverlay');
    const noDataWarning = document.getElementById('noDataWarning');
    const customizerMain = document.getElementById('customizerMain');
    const groupsList = document.getElementById('groupsList');
    const questionsContainer = document.getElementById('questionsContainer');
    const exportBtn = document.getElementById('exportBtn');
    const resetBtn = document.getElementById('resetBtn');
    const addGroupBtn = document.getElementById('addGroupBtn');
    const addGroupModal = new bootstrap.Modal(document.getElementById('addGroupModal'));
    const renameGroupModal = new bootstrap.Modal(document.getElementById('renameGroupModal'));

    // Check if a project is active and show "save to project" option
    (async function checkProjectForSaveOption() {
        try {
            const r = await fetch('/api/projects/current');
            if (r.ok) {
                const d = await r.json();
                if (d.path) {
                    document.getElementById('saveToProjectRow').style.display = '';
                }
            }
        } catch (_) { /* no project — keep hidden */ }
    })();

    // Generate UUID
    function uuid() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Get text from multilingual object
    function getText(obj, lang) {
        if (!obj) return '';
        if (typeof obj === 'string') return obj;
        if (typeof obj === 'object') {
            return obj[lang] || obj['en'] || Object.values(obj)[0] || '';
        }
        return '';
    }

    // Field definitions per question type
    // Universal fields are always shown; type-specific fields show/hide based on detected type
    const QUESTION_TYPE_FIELDS = {
        universal: ['questionType', 'cssClass', 'hidden', 'pageBreak', 'relevance', 'helpText'],
        'N': ['validationMin', 'validationMax', 'integerOnly', 'inputWidth', 'inputSize', 'maximumChars', 'prefix', 'suffix', 'placeholder'],
        'S': ['inputWidth', 'inputSize', 'displayRows', 'maximumChars', 'numbersOnly', 'prefix', 'suffix', 'placeholder'],
        'T': ['inputWidth', 'inputSize', 'displayRows', 'maximumChars', 'numbersOnly', 'placeholder'],
        'L': ['displayColumns', 'alphasort'],
        '!': ['dropdownSize', 'dropdownPrefix', 'categorySeparator', 'alphasort'],
        'F': ['answerWidth', 'repeatHeadings', 'useDropdown'],
        '*': ['equation', 'numbersOnly'],
        'X': []
    };

    /**
     * Detect the LimeSurvey question type for a question.
     * Mirrors Python _determine_ls_question_type() logic.
     */
    function detectQuestionType(question) {
        // If toolOverrides has an explicit type, use it
        const ov = question.toolOverrides || {};
        if (ov.questionType) return ov.questionType;

        const orig = question.originalData || {};
        const lsConfig = orig.LimeSurvey || {};

        // Check LimeSurvey section explicit type
        if (lsConfig.questionType) return lsConfig.questionType;

        const inputType = (orig.InputType || '').toLowerCase();
        const levels = orig.Levels || question.levels || {};
        const hasLevels = levels && typeof levels === 'object' && Object.keys(levels).length > 0;

        // Calculated field
        if (inputType === 'calculated' || orig.Calculation) return '*';

        // Numerical
        if (inputType === 'numerical') return 'N';

        // Slider
        if (inputType === 'slider') return 'K';

        // Dropdown
        if (inputType === 'dropdown') return '!';

        // Many levels -> dropdown
        if (hasLevels && Object.keys(levels).length > 10) return '!';

        // Text
        if (inputType === 'text') {
            const textConfig = orig.TextConfig || {};
            return textConfig.multiline ? 'T' : 'S';
        }

        // Default based on levels
        return hasLevels ? 'L' : 'T';
    }

    /**
     * Check if a question should NOT be grouped into a matrix.
     * Mirrors Python _should_not_group() logic (without the removed >= 6 threshold).
     */
    function shouldNotGroup(question) {
        // Template-level MatrixGrouping flag
        if (question.matrixGroupingDisabled) return true;

        // Participants template should never be grouped
        const sourceFile = (question.sourceFile || '').toLowerCase();
        if (sourceFile.includes('participants')) return true;

        const orig = question.originalData || {};
        const inputType = (orig.InputType || question.inputType || '').toLowerCase();

        // Dropdown, numerical, text, calculated
        if (inputType === 'dropdown' || inputType === 'numerical' ||
            inputType === 'text' || inputType === 'calculated') return true;

        // Questions with "Other" option
        if (orig.OtherOption && orig.OtherOption.enabled) return true;

        return false;
    }

    /**
     * Compute matrix groups for a list of questions.
     * Returns array of { isMatrix, questions, levelsKey, matrixName }.
     */
    function computeMatrixGroups(questions, matrixMode, matrixGlobal) {
        const enabledQuestions = questions.filter(q => q.enabled);

        if (!matrixMode) {
            // No grouping: each question is standalone
            return enabledQuestions.map(q => ({
                isMatrix: false,
                questions: [q],
                levelsKey: null,
                matrixName: null
            }));
        }

        // Helper: serialize levels with sorted keys to match Python json.dumps(levels, sort_keys=True)
        function levelsKey(q) {
            const levels = q.levels || (q.originalData && q.originalData.Levels) || {};
            if (!levels || typeof levels !== 'object' || Object.keys(levels).length === 0) return null;
            const sorted = {};
            Object.keys(levels).sort().forEach(k => { sorted[k] = levels[k]; });
            return JSON.stringify(sorted);
        }

        if (matrixGlobal) {
            // Global grouping: group all questions with identical levels
            const groups = [];
            const keyToIdx = {};

            for (const q of enabledQuestions) {
                if (shouldNotGroup(q)) {
                    groups.push({ isMatrix: false, questions: [q], levelsKey: null, matrixName: null });
                    continue;
                }
                const key = levelsKey(q);
                if (key && key in keyToIdx) {
                    groups[keyToIdx[key]].questions.push(q);
                } else if (key) {
                    keyToIdx[key] = groups.length;
                    groups.push({ isMatrix: false, questions: [q], levelsKey: key, matrixName: null });
                } else {
                    groups.push({ isMatrix: false, questions: [q], levelsKey: null, matrixName: null });
                }
            }

            // Mark groups with 2+ questions as matrix
            for (const g of groups) {
                if (g.questions.length > 1) {
                    g.isMatrix = true;
                    g.matrixName = 'M' + g.questions[0].questionCode;
                }
            }
            return groups;
        } else {
            // Consecutive grouping: only group consecutive questions with matching levels
            const groups = [];
            let currentGroup = null;
            let lastKey = null;

            for (const q of enabledQuestions) {
                if (shouldNotGroup(q)) {
                    if (currentGroup) {
                        groups.push(currentGroup);
                        currentGroup = null;
                    }
                    groups.push({ isMatrix: false, questions: [q], levelsKey: null, matrixName: null });
                    lastKey = null;
                    continue;
                }

                const key = levelsKey(q);
                if (!currentGroup) {
                    currentGroup = { isMatrix: false, questions: [q], levelsKey: key, matrixName: null };
                    lastKey = key;
                } else if (key && key === lastKey) {
                    currentGroup.questions.push(q);
                } else {
                    groups.push(currentGroup);
                    currentGroup = { isMatrix: false, questions: [q], levelsKey: key, matrixName: null };
                    lastKey = key;
                }
            }
            if (currentGroup) groups.push(currentGroup);

            // Mark groups with 2+ questions as matrix
            for (const g of groups) {
                if (g.questions.length > 1) {
                    g.isMatrix = true;
                    g.matrixName = 'M' + g.questions[0].questionCode;
                }
            }
            return groups;
        }
    }

    // Load data from sessionStorage
    function loadFromSessionStorage() {
        loadingOverlay.classList.remove('d-none');

        try {
            const storedData = sessionStorage.getItem('surveyCustomizerData');
            if (!storedData) {
                showNoData();
                return;
            }

            const data = JSON.parse(storedData);
            if (!data.selectedFiles || data.selectedFiles.length === 0) {
                showNoData();
                return;
            }

            // Set language, version, and target tool
            customizationState.survey.language = data.language || 'en';
            customizationState.survey.languages = data.languages || [data.language || 'en'];
            customizationState.survey.base_language = data.base_language || data.language || 'en';
            customizationState.exportOptions.ls_version = data.ls_version || '3';
            customizationState.exportOptions.target_tool = data.target_tool || 'limesurvey';

            // Update UI
            document.getElementById('languageSelect').value = customizationState.survey.language;
            document.getElementById('lsVersionSelect').value = customizationState.exportOptions.ls_version;
            const targetToolEl = document.getElementById('targetTool');
            if (targetToolEl && data.target_tool) targetToolEl.value = data.target_tool;

            // Display language tags
            updateLanguageTags();

            // Set preview language to base language
            previewLanguage = customizationState.survey.base_language || customizationState.survey.language || 'en';
            updatePreviewLangSwitcher();

            // Restore LimeSurvey survey settings if saved
            const storedLsSettings = sessionStorage.getItem('surveyCustomizerLsSettings');
            if (storedLsSettings) {
                try {
                    const ls = JSON.parse(storedLsSettings);
                    customizationState.lsSettings = Object.assign({}, customizationState.lsSettings, ls);
                    populateLsSettingsForm(customizationState.lsSettings);
                } catch (e2) { /* ignore parse errors */ }
            }

            // Load file data via API
            loadQuestionsFromFiles(data.selectedFiles);

        } catch (e) {
            console.error('Error loading session data:', e);
            showNoData();
        }
    }

    // Load questions from selected files via API
    async function loadQuestionsFromFiles(selectedFiles) {
        try {
            const response = await fetch('/api/survey-customizer/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: selectedFiles, language: customizationState.survey.language || 'en' })
            });

            if (!response.ok) {
                throw new Error('Failed to load survey data');
            }

            const result = await response.json();
            if (result.error) {
                throw new Error(result.error);
            }

            // Build groups from loaded data
            customizationState.groups = result.groups;
            originalState = JSON.parse(JSON.stringify(customizationState));

            // Detect languages available in template content (for preview switcher only)
            // Do NOT overwrite customizationState.survey.languages — those are the user's export selection
            const groupLangs = new Set();
            (result.groups || []).forEach(g => {
                (g.detected_languages || []).forEach(l => groupLangs.add(l));
            });
            if (groupLangs.size > 0) {
                detectedLanguages = Array.from(groupLangs).sort();
            } else {
                detectedLanguages = customizationState.survey.languages || ['en'];
            }
            previewLanguage = customizationState.survey.base_language || customizationState.survey.language || 'en';
            updateLanguageTags();
            updatePreviewLangSwitcher();

            renderGroups();
            renderQuestions();
            showCustomizer();

        } catch (e) {
            console.error('Error loading questions:', e);
            alert('Error loading survey data: ' + e.message);
            showNoData();
        }
    }

    // Show states
    function showNoData() {
        loadingOverlay.classList.add('d-none');
        noDataWarning.classList.remove('d-none');
        customizerMain.classList.add('d-none');
    }

    function showCustomizer() {
        loadingOverlay.classList.add('d-none');
        noDataWarning.classList.add('d-none');
        customizerMain.classList.remove('d-none');
    }

    // Render groups in left panel
    function renderGroups() {
        groupsList.innerHTML = '';

        customizationState.groups.forEach((group, idx) => {
            const div = document.createElement('div');
            div.className = 'group-item';
            div.dataset.groupId = group.id;
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <i class="fas fa-grip-vertical drag-handle"></i>
                        <span class="group-name">${escapeHtml(group.name)}</span>
                        <div class="group-meta">${group.questions.length} question(s)</div>
                    </div>
                    <div class="group-actions">
                        <button class="btn btn-sm btn-link text-secondary p-0 rename-group-btn" title="Rename">
                            <i class="fas fa-pen"></i>
                        </button>
                        <button class="btn btn-sm btn-link text-danger p-0 ms-1 delete-group-btn" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;

            // Click to select
            div.addEventListener('click', (e) => {
                if (!e.target.closest('button')) {
                    document.querySelectorAll('.group-item').forEach(g => g.classList.remove('active'));
                    div.classList.add('active');
                    scrollToGroup(group.id);
                }
            });

            // Rename button
            div.querySelector('.rename-group-btn').addEventListener('click', () => {
                openRenameModal(group);
            });

            // Delete button
            div.querySelector('.delete-group-btn').addEventListener('click', () => {
                if (customizationState.groups.length <= 1) {
                    alert('Cannot delete the only remaining group.');
                    return;
                }
                if (confirm(`Delete group "${group.name}"? Questions will be moved to the previous group.`)) {
                    deleteGroup(group.id);
                }
            });

            groupsList.appendChild(div);
        });

        // Initialize sortable for groups
        initGroupsSortable();
    }

    // Render a single question item (full card with all controls)
    function renderSingleQuestion(container, group, q) {
        const qDiv = document.createElement('div');
        qDiv.className = 'question-item';
        qDiv.dataset.questionId = q.id;
        qDiv.dataset.groupId = group.id;
        const mandatoryId = `mandatory-${group.id}-${q.id}`;
        const enabledId = `enabled-${group.id}-${q.id}`;
        const hasOverrides = q.toolOverrides && Object.keys(q.toolOverrides).length > 0;
        qDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <i class="fas fa-grip-vertical drag-handle"></i>
                    <span class="question-code">${escapeHtml(q.questionCode)}</span>
                    ${q.runNumber > 1 ? `<span class="badge bg-info ms-1">run-${String(q.runNumber).padStart(2, '0')}</span>` : ''}
                    ${hasOverrides ? '<span class="badge bg-warning text-dark ms-1" title="Has tool-specific overrides"><i class="fas fa-wrench"></i></span>' : ''}
                </div>
                <div class="d-flex align-items-center gap-3">
                    <span class="tool-settings-toggle" data-gid="${group.id}" data-qid="${q.id}" title="LimeSurvey settings">
                        <i class="fas fa-cog"></i> LS
                    </span>
                    <div class="form-check form-switch" title="Required: Participant must answer this question">
                        <input class="form-check-input question-mandatory" type="checkbox" id="${mandatoryId}"
                               ${q.mandatory ? 'checked' : ''}>
                        <label class="form-check-label small text-muted" for="${mandatoryId}">Required</label>
                    </div>
                    <div class="form-check form-switch" title="Include: Export this question to LimeSurvey">
                        <input class="form-check-input question-enabled" type="checkbox" id="${enabledId}"
                               ${q.enabled ? 'checked' : ''}>
                        <label class="form-check-label small text-muted" for="${enabledId}">Include</label>
                    </div>
                </div>
            </div>
            <div class="question-desc" title="${escapeHtml(getText(q.originalData && q.originalData.Description, previewLanguage) || q.description || 'No description')}">${escapeHtml(getText(q.originalData && q.originalData.Description, previewLanguage) || q.description || 'No description')}</div>
            <div class="tool-settings-container" data-gid="${group.id}" data-qid="${q.id}"></div>
        `;

        // Tool settings toggle
        wireToolSettingsToggle(qDiv, group.id);

        // Mandatory toggle
        qDiv.querySelector('.question-mandatory').addEventListener('change', (e) => {
            toggleMandatory(group.id, q.id, e.target.checked);
        });

        // Enabled toggle
        qDiv.querySelector('.question-enabled').addEventListener('change', (e) => {
            toggleEnabled(group.id, q.id, e.target.checked);
            renderQuestions(); // Re-render to update matrix grouping
        });

        container.appendChild(qDiv);
    }

    // Render a matrix group (parent container with subquestions)
    function renderMatrixGroup(container, group, matrixGroup) {
        const firstQ = matrixGroup.questions[0];
        const matrixDiv = document.createElement('div');
        matrixDiv.className = 'matrix-parent';

        // Get levels summary
        const levels = firstQ.levels || (firstQ.originalData && firstQ.originalData.Levels) || {};
        const levelKeys = Object.keys(levels);
        let levelsSummary = '';
        if (levelKeys.length > 0) {
            const firstLabel = getText(levels[levelKeys[0]], previewLanguage) || levelKeys[0];
            const lastLabel = getText(levels[levelKeys[levelKeys.length - 1]], previewLanguage) || levelKeys[levelKeys.length - 1];
            levelsSummary = `${levelKeys.length} options: ${escapeHtml(firstLabel)} ... ${escapeHtml(lastLabel)}`;
        }

        // Get default matrix text from group instructions
        const instructions = group.instructions || {};
        const defaultMatrixText = getText(instructions, previewLanguage)
            || 'Please answer the following questions:';
        const currentMatrixText = firstQ.toolOverrides && firstQ.toolOverrides.matrixQuestionText
            ? firstQ.toolOverrides.matrixQuestionText
            : defaultMatrixText;

        const enabledCount = matrixGroup.questions.filter(q => q.enabled).length;
        const anyMandatory = matrixGroup.questions.some(q => q.mandatory);
        const mandatoryMatrixId = `matrix-mandatory-${group.id}-${firstQ.id}`;

        matrixDiv.innerHTML = `
            <div class="matrix-header">
                <i class="fas fa-th text-primary"></i>
                <span class="matrix-name">${escapeHtml(matrixGroup.matrixName)}</span>
                <span class="badge bg-primary">${enabledCount} items</span>
                <span class="badge bg-info">Array/Matrix</span>
                <div class="ms-auto d-flex align-items-center gap-3">
                    <span class="tool-settings-toggle" data-gid="${group.id}" data-qid="${firstQ.id}" title="Matrix LS settings">
                        <i class="fas fa-cog"></i> LS
                    </span>
                    <div class="form-check form-switch" title="Required: All subquestions in this matrix">
                        <input class="form-check-input matrix-mandatory" type="checkbox" id="${mandatoryMatrixId}"
                               ${anyMandatory ? 'checked' : ''}>
                        <label class="form-check-label small text-muted" for="${mandatoryMatrixId}">Required</label>
                    </div>
                </div>
            </div>
            <input type="text" class="matrix-text-input" value="${escapeHtml(currentMatrixText)}"
                   placeholder="Matrix parent question text" title="Text shown above the matrix in LimeSurvey">
            ${levelsSummary ? `<div class="matrix-levels-summary"><i class="fas fa-list-ol me-1"></i>${levelsSummary}</div>` : ''}
            <div class="matrix-subquestions" data-group-id="${group.id}">
            </div>
            <div class="tool-settings-container" data-gid="${group.id}" data-qid="${firstQ.id}"></div>
        `;

        // Wire matrix text input
        const textInput = matrixDiv.querySelector('.matrix-text-input');
        textInput.addEventListener('change', () => {
            const val = textInput.value.trim();
            if (!firstQ.toolOverrides) firstQ.toolOverrides = {};
            if (val && val !== defaultMatrixText) {
                firstQ.toolOverrides.matrixQuestionText = val;
            } else {
                delete firstQ.toolOverrides.matrixQuestionText;
            }
        });

        // Wire matrix mandatory toggle
        matrixDiv.querySelector('.matrix-mandatory').addEventListener('change', (e) => {
            const mandatory = e.target.checked;
            matrixGroup.questions.forEach(q => {
                q.mandatory = mandatory;
            });
        });

        // Wire matrix-level tool settings toggle (uses matrix description, not subquestion text)
        const matrixToggle = matrixDiv.querySelector('.tool-settings-toggle');
        if (matrixToggle) {
            matrixToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const settingsContainer = matrixDiv.querySelector('.tool-settings-container');
                const gid = settingsContainer.dataset.gid;
                const qid = settingsContainer.dataset.qid;

                if (settingsContainer.innerHTML.trim()) {
                    const panel = settingsContainer.querySelector('.tool-settings-panel');
                    if (panel) saveToolSettings(gid, qid, panel);
                    settingsContainer.innerHTML = '';
                    activeToolSettingsPanel = null;
                } else {
                    if (activeToolSettingsPanel) {
                        const prevPanel = activeToolSettingsPanel.querySelector('.tool-settings-panel');
                        if (prevPanel) {
                            saveToolSettings(activeToolSettingsPanel.dataset.gid, activeToolSettingsPanel.dataset.qid, prevPanel);
                        }
                        activeToolSettingsPanel.innerHTML = '';
                    }
                    const grp = customizationState.groups.find(g => g.id === gid);
                    const quest = grp ? grp.questions.find(qq => qq.id === qid) : null;
                    if (quest) {
                        // Build panel with matrix description instead of subquestion text
                        const matrixQuest = Object.assign({}, quest, {
                            description: currentMatrixText
                        });
                        settingsContainer.innerHTML = buildToolSettingsPanel(gid, matrixQuest);
                        activeToolSettingsPanel = settingsContainer;

                        const panel = settingsContainer.querySelector('.tool-settings-panel');
                        if (panel) {
                            updateTypeSpecificFields(panel);
                            const typeSelect = panel.querySelector('.ts-questionType');
                            if (typeSelect) {
                                typeSelect.addEventListener('change', () => {
                                    updateTypeSpecificFields(panel);
                                    saveToolSettings(gid, qid, panel);
                                });
                            }
                            panel.querySelectorAll('input, select').forEach(input => {
                                if (input !== typeSelect) {
                                    input.addEventListener('change', () => saveToolSettings(gid, qid, panel));
                                }
                            });
                        }
                    }
                }
            });
        }

        // Render subquestions
        const subContainer = matrixDiv.querySelector('.matrix-subquestions');
        matrixGroup.questions.forEach(q => {
            const subDiv = document.createElement('div');
            subDiv.className = 'matrix-subquestion';
            subDiv.dataset.questionId = q.id;
            subDiv.dataset.groupId = group.id;

            const desc = getText(q.originalData && q.originalData.Description, previewLanguage) || q.description || '';
            const enabledSubId = `enabled-sub-${group.id}-${q.id}`;
            const hasSubOverrides = q.toolOverrides && q.toolOverrides.questionText;

            subDiv.innerHTML = `
                <i class="fas fa-grip-vertical drag-handle" style="color:#adb5bd;cursor:grab;"></i>
                <span class="question-code">${escapeHtml(q.questionCode)}</span>
                ${hasSubOverrides ? '<span class="badge bg-warning text-dark" title="Has HTML override" style="font-size:0.65rem;"><i class="fas fa-code"></i></span>' : ''}
                <span class="sub-desc" title="${escapeHtml(desc)}">${escapeHtml(desc)}</span>
                <span class="sub-ls-toggle" data-gid="${group.id}" data-qid="${q.id}" title="Edit subquestion HTML text">
                    <i class="fas fa-code"></i>
                </span>
                <div class="form-check form-switch" title="Include this subquestion">
                    <input class="form-check-input question-enabled" type="checkbox" id="${enabledSubId}"
                           ${q.enabled ? 'checked' : ''}>
                </div>
                <div class="sub-settings-container" data-gid="${group.id}" data-qid="${q.id}"></div>
            `;

            // Subquestion LS toggle (HTML text only)
            subDiv.querySelector('.sub-ls-toggle').addEventListener('click', (e) => {
                e.stopPropagation();
                const settingsContainer = subDiv.querySelector('.sub-settings-container');
                if (settingsContainer.innerHTML.trim()) {
                    // Save and close
                    saveSubquestionSettings(group.id, q.id, settingsContainer);
                    settingsContainer.innerHTML = '';
                } else {
                    settingsContainer.innerHTML = buildSubquestionSettingsPanel(group.id, q);
                    // Auto-save on change
                    settingsContainer.querySelectorAll('input').forEach(input => {
                        input.addEventListener('change', () => {
                            saveSubquestionSettings(group.id, q.id, settingsContainer);
                        });
                    });
                }
            });

            subDiv.querySelector('.question-enabled').addEventListener('change', (e) => {
                toggleEnabled(group.id, q.id, e.target.checked);
                renderQuestions(); // Re-render to update matrix grouping
            });

            subContainer.appendChild(subDiv);
        });

        // Initialize sortable for subquestions within this matrix
        const sortable = new Sortable(subContainer, {
            group: 'questions',
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            onEnd: function(evt) {
                handleQuestionMove(evt);
            }
        });
        sortableInstances.push(sortable);

        container.appendChild(matrixDiv);
    }

    // Build a minimal settings panel for a matrix subquestion (HTML text only)
    function buildSubquestionSettingsPanel(groupId, question) {
        const ov = question.toolOverrides || {};
        return `
            <div class="sub-settings-panel">
                <label class="form-label">Subquestion Text <span class="html-hint" title="HTML tags are supported"><i class="fas fa-code"></i> HTML</span></label>
                <input type="text" class="form-control sub-ts-questionText" placeholder="${escapeHtml(question.description || '')}"
                       value="${escapeHtml(ov.questionText || '')}">
            </div>
        `;
    }

    // Save subquestion settings (HTML text only)
    function saveSubquestionSettings(groupId, questionId, containerEl) {
        const group = customizationState.groups.find(g => g.id === groupId);
        if (!group) return;
        const question = group.questions.find(q => q.id === questionId);
        if (!question) return;

        if (!question.toolOverrides) question.toolOverrides = {};
        const input = containerEl.querySelector('.sub-ts-questionText');
        if (input) {
            const val = input.value.trim();
            if (val) {
                question.toolOverrides.questionText = val;
            } else {
                delete question.toolOverrides.questionText;
            }
        }
    }

    // Wire tool settings toggle event listener for a container element
    function wireToolSettingsToggle(parentEl, groupId) {
        const toggle = parentEl.querySelector('.tool-settings-toggle');
        if (!toggle) return;

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const container = parentEl.querySelector('.tool-settings-container');
            const gid = container.dataset.gid;
            const qid = container.dataset.qid;

            if (container.innerHTML.trim()) {
                // Save and close
                const panel = container.querySelector('.tool-settings-panel');
                if (panel) saveToolSettings(gid, qid, panel);
                container.innerHTML = '';
                activeToolSettingsPanel = null;
            } else {
                // Close any other open panel first
                if (activeToolSettingsPanel) {
                    const prevPanel = activeToolSettingsPanel.querySelector('.tool-settings-panel');
                    if (prevPanel) {
                        saveToolSettings(
                            activeToolSettingsPanel.dataset.gid,
                            activeToolSettingsPanel.dataset.qid,
                            prevPanel
                        );
                    }
                    activeToolSettingsPanel.innerHTML = '';
                }
                // Open this one
                const grp = customizationState.groups.find(g => g.id === gid);
                const quest = grp ? grp.questions.find(qq => qq.id === qid) : null;
                if (quest) {
                    container.innerHTML = buildToolSettingsPanel(gid, quest);
                    activeToolSettingsPanel = container;

                    const panel = container.querySelector('.tool-settings-panel');
                    if (panel) {
                        updateTypeSpecificFields(panel);

                        const typeSelect = panel.querySelector('.ts-questionType');
                        if (typeSelect) {
                            typeSelect.addEventListener('change', () => {
                                updateTypeSpecificFields(panel);
                                saveToolSettings(gid, qid, panel);
                            });
                        }

                        panel.querySelectorAll('input, select').forEach(input => {
                            if (input !== typeSelect) {
                                input.addEventListener('change', () => {
                                    saveToolSettings(gid, qid, panel);
                                });
                            }
                        });
                    }
                }
            }
        });
    }

    // Render questions in right panel
    function renderQuestions() {
        questionsContainer.innerHTML = '';

        // Destroy existing sortables
        sortableInstances.forEach(s => s.destroy());
        sortableInstances = [];

        const matrixMode = customizationState.exportOptions.matrix;
        const matrixGlobal = customizationState.exportOptions.matrix_global;

        customizationState.groups.forEach((group, groupIdx) => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'question-group';
            groupDiv.dataset.groupId = group.id;
            groupDiv.innerHTML = `
                <div class="group-header">
                    <h5>
                        <i class="fas fa-folder-open text-primary"></i>
                        <span class="editable-group-name">${escapeHtml(group.name)}</span>
                        <span class="badge bg-secondary">${group.questions.length}</span>
                    </h5>
                </div>
                <div class="question-group-list" data-group-id="${group.id}">
                </div>
            `;

            const listDiv = groupDiv.querySelector('.question-group-list');

            if (matrixMode) {
                // Three-level hierarchy: compute matrix groups from enabled questions
                const matrixGroups = computeMatrixGroups(group.questions, matrixMode, matrixGlobal);

                for (const mg of matrixGroups) {
                    if (mg.isMatrix) {
                        renderMatrixGroup(listDiv, group, mg);
                    } else {
                        for (const q of mg.questions) {
                            renderSingleQuestion(listDiv, group, q);
                        }
                    }
                }

                // Render disabled questions as standalone so they can be re-enabled
                const disabledQuestions = group.questions.filter(q => !q.enabled);
                for (const q of disabledQuestions) {
                    renderSingleQuestion(listDiv, group, q);
                }
            } else {
                // Flat mode: render all questions as standalone items
                for (const q of group.questions) {
                    renderSingleQuestion(listDiv, group, q);
                }
            }

            questionsContainer.appendChild(groupDiv);

            // Initialize sortable for the group list (for standalone questions)
            const sortable = new Sortable(listDiv, {
                group: 'questions',
                animation: 150,
                handle: '.drag-handle',
                ghostClass: 'sortable-ghost',
                dragClass: 'sortable-drag',
                draggable: '.question-item',
                onEnd: function(evt) {
                    handleQuestionMove(evt);
                }
            });
            sortableInstances.push(sortable);
        });
    }

    // Initialize sortable for groups list
    function initGroupsSortable() {
        if (window.groupsSortable) {
            window.groupsSortable.destroy();
        }
        window.groupsSortable = new Sortable(groupsList, {
            animation: 150,
            handle: '.drag-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            onEnd: function(evt) {
                handleGroupMove(evt);
            }
        });
    }

    // Handle group reordering
    function handleGroupMove(evt) {
        const groupId = evt.item.dataset.groupId;
        const oldIndex = evt.oldIndex;
        const newIndex = evt.newIndex;

        if (oldIndex === newIndex) return;

        const [movedGroup] = customizationState.groups.splice(oldIndex, 1);
        customizationState.groups.splice(newIndex, 0, movedGroup);

        // Update order values
        customizationState.groups.forEach((g, i) => g.order = i);

        // Recalculate run numbers based on new positions
        recalculateRunNumbers();

        // Re-render to show updated run numbers
        renderGroups();
        renderQuestions();
    }

    // Recalculate run numbers for multi-run questionnaires based on group positions
    function recalculateRunNumbers() {
        // Group by sourceFile to find multi-run questionnaires
        const groupsBySource = {};
        customizationState.groups.forEach((group, index) => {
            const source = group.sourceFile;
            if (!source) return;
            if (!groupsBySource[source]) {
                groupsBySource[source] = [];
            }
            groupsBySource[source].push({ group, index });
        });

        // For each source, reassign run numbers based on position
        Object.entries(groupsBySource).forEach(([source, entries]) => {
            // Sort by current position (index)
            entries.sort((a, b) => a.index - b.index);

            const isMultiRun = entries.length > 1;

            entries.forEach((entry, runIdx) => {
                const group = entry.group;
                let baseName = group.name.replace(/\s*\(Run \d+\)$/, '');

                if (isMultiRun) {
                    const newRunNumber = runIdx + 1;
                    group.runNumber = newRunNumber;
                    group.name = `${baseName} (Run ${newRunNumber})`;
                    group.questions.forEach(q => { q.runNumber = newRunNumber; });
                } else {
                    // Single run remaining — clear run markers entirely
                    group.runNumber = null;
                    group.name = baseName;
                    group.questions.forEach(q => { q.runNumber = null; });
                }
            });
        });
    }

    // Handle question move between/within groups
    function handleQuestionMove(evt) {
        const questionId = evt.item.dataset.questionId;
        const fromGroupId = evt.from.dataset.groupId;
        const toGroupId = evt.to.dataset.groupId;
        const newIndex = evt.newIndex;

        // Find and remove from source
        const fromGroup = customizationState.groups.find(g => g.id === fromGroupId);
        const questionIdx = fromGroup.questions.findIndex(q => q.id === questionId);
        const [question] = fromGroup.questions.splice(questionIdx, 1);

        // Add to target
        const toGroup = customizationState.groups.find(g => g.id === toGroupId);
        toGroup.questions.splice(newIndex, 0, question);

        // Update display orders
        toGroup.questions.forEach((q, i) => q.displayOrder = i);
        if (fromGroupId !== toGroupId) {
            fromGroup.questions.forEach((q, i) => q.displayOrder = i);
        }

        // Update both panels — renderQuestions recomputes matrix groups after drag-and-drop
        renderGroups();
        renderQuestions();
    }

    // Toggle mandatory
    function toggleMandatory(groupId, questionId, mandatory) {
        const group = customizationState.groups.find(g => g.id === groupId);
        const question = group.questions.find(q => q.id === questionId);
        question.mandatory = mandatory;
        // No need to re-render, checkbox state is already updated
    }

    // Toggle enabled
    function toggleEnabled(groupId, questionId, enabled) {
        const group = customizationState.groups.find(g => g.id === groupId);
        const question = group.questions.find(q => q.id === questionId);
        question.enabled = enabled;
    }

    // Scroll to group in questions panel
    function scrollToGroup(groupId) {
        const groupDiv = questionsContainer.querySelector(`[data-group-id="${groupId}"]`);
        if (groupDiv) {
            groupDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // Add new group
    addGroupBtn.addEventListener('click', () => {
        document.getElementById('newGroupName').value = '';
        addGroupModal.show();
    });

    document.getElementById('confirmAddGroup').addEventListener('click', () => {
        const name = document.getElementById('newGroupName').value.trim();
        if (!name) {
            alert('Please enter a group name.');
            return;
        }

        const newGroup = {
            id: uuid(),
            name: name,
            order: customizationState.groups.length,
            questions: []
        };

        customizationState.groups.push(newGroup);
        addGroupModal.hide();
        renderGroups();
        renderQuestions();
    });

    // Rename group
    let renameGroupId = null;
    function openRenameModal(group) {
        renameGroupId = group.id;
        document.getElementById('renameGroupName').value = group.name;
        renameGroupModal.show();
    }

    document.getElementById('confirmRenameGroup').addEventListener('click', () => {
        const newName = document.getElementById('renameGroupName').value.trim();
        if (!newName) {
            alert('Please enter a group name.');
            return;
        }

        const group = customizationState.groups.find(g => g.id === renameGroupId);
        if (group) {
            group.name = newName;
        }

        renameGroupModal.hide();
        renderGroups();
        renderQuestions();
    });

    // Delete group
    function deleteGroup(groupId) {
        const groupIdx = customizationState.groups.findIndex(g => g.id === groupId);
        const group = customizationState.groups[groupIdx];

        // Move questions to previous group (or next if first)
        const targetIdx = groupIdx > 0 ? groupIdx - 1 : 1;
        const targetGroup = customizationState.groups[targetIdx];

        if (targetGroup && group.questions.length > 0) {
            targetGroup.questions.push(...group.questions);
            targetGroup.questions.forEach((q, i) => q.displayOrder = i);
        }

        customizationState.groups.splice(groupIdx, 1);
        customizationState.groups.forEach((g, i) => g.order = i);

        // Recalculate run numbers so remaining runs are sequential
        recalculateRunNumbers();

        renderGroups();
        renderQuestions();
    }

    // Reset changes
    resetBtn.addEventListener('click', () => {
        if (!originalState) return;
        if (confirm('Reset all changes to the original state?')) {
            customizationState = JSON.parse(JSON.stringify(originalState));
            renderGroups();
            renderQuestions();
        }
    });

    // Export
    exportBtn.addEventListener('click', async () => {
        // Get and validate survey name
        const surveyNameInput = document.getElementById('surveyName');
        const surveyName = surveyNameInput.value.trim();

        if (!surveyName) {
            surveyNameInput.classList.add('is-invalid');
            surveyNameInput.focus();
            alert('Please enter a survey name before exporting.');
            return;
        }
        surveyNameInput.classList.remove('is-invalid');

        // Close any open tool settings panel and save
        if (activeToolSettingsPanel) {
            const prevPanel = activeToolSettingsPanel.querySelector('.tool-settings-panel');
            if (prevPanel) {
                saveToolSettings(
                    activeToolSettingsPanel.dataset.gid,
                    activeToolSettingsPanel.dataset.qid,
                    prevPanel
                );
            }
            activeToolSettingsPanel.innerHTML = '';
            activeToolSettingsPanel = null;
        }

        // Update export options from UI
        customizationState.survey.title = surveyName;
        customizationState.exportFormat = document.getElementById('exportFormat').value;
        customizationState.survey.language = document.getElementById('languageSelect').value;
        customizationState.exportOptions.ls_version = document.getElementById('lsVersionSelect').value;
        customizationState.exportOptions.matrix = document.getElementById('matrixMode').checked;
        customizationState.exportOptions.matrix_global = document.getElementById('globalMatrix').checked;

        // Read LimeSurvey survey settings from form
        customizationState.lsSettings = {
            welcomeText: document.getElementById('lsWelcomeText').value,
            endText: document.getElementById('lsEndText').value,
            endUrl: document.getElementById('lsEndUrl').value,
            endUrlDescription: document.getElementById('lsEndUrlDescription').value,
            showDataPolicy: document.getElementById('lsShowDataPolicy').value,
            policyNotice: document.getElementById('lsPolicyNotice').value,
            policyError: document.getElementById('lsPolicyError').value,
            policyCheckboxLabel: document.getElementById('lsPolicyCheckboxLabel').value,
            navigationDelay: document.getElementById('lsNavigationDelay').value,
            questionIndex: document.getElementById('lsQuestionIndex').value,
            showGroupInfo: document.getElementById('lsShowGroupInfo').value,
            showQnumCode: document.getElementById('lsShowQnumCode').value,
            showNoAnswer: document.getElementById('lsShowNoAnswer').value,
            showXQuestions: document.getElementById('lsShowXQuestions').value,
            showWelcome: document.getElementById('lsShowWelcome').value,
            allowPrev: document.getElementById('lsAllowPrev').value,
            noKeyboard: document.getElementById('lsNoKeyboard').value,
            showProgress: document.getElementById('lsShowProgress').value,
            printAnswers: document.getElementById('lsPrintAnswers').value,
            publicStatistics: document.getElementById('lsPublicStatistics').value,
            publicGraphs: document.getElementById('lsPublicGraphs').value,
            autoRedirect: document.getElementById('lsAutoRedirect').value
        };

        // Persist LS settings to sessionStorage
        saveLsSettings();

        // Include "save to project" flag if checked
        const saveToProject = document.getElementById('saveToProject').checked;
        const exportPayload = Object.assign({}, customizationState);
        if (saveToProject) exportPayload.saveToProject = true;

        exportBtn.disabled = true;
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Exporting...';

        try {
            const response = await fetch('/api/survey-customizer/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(exportPayload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Export failed');
            }

            // Download the file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Use filename from Content-Disposition header, or generate from survey name
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = null;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (match && match[1]) {
                    filename = match[1].replace(/['"]/g, '');
                }
            }
            if (!filename) {
                // Generate filename from survey name and date
                const safeName = surveyName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_').trim() || 'survey';
                const dateStr = new Date().toISOString().split('T')[0];
                filename = `${safeName}_${dateStr}.lss`;
            }
            a.download = filename;

            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            // Show feedback if templates were saved to project
            const savedCount = response.headers.get('X-Templates-Saved');
            if (savedCount && parseInt(savedCount, 10) > 0) {
                const n = parseInt(savedCount, 10);
                const msg = n === 1
                    ? '1 template saved to project library.'
                    : `${n} templates saved to project library.`;
                const banner = document.createElement('div');
                banner.className = 'alert alert-success alert-dismissible fade show mt-2';
                banner.setAttribute('role', 'alert');
                banner.innerHTML = `<i class="fas fa-check-circle me-2"></i>${msg}` +
                    '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
                exportBtn.parentElement.appendChild(banner);
                setTimeout(() => { if (banner.parentElement) banner.remove(); }, 6000);
            }

        } catch (e) {
            console.error('Export error:', e);
            alert('Export failed: ' + e.message);
        } finally {
            exportBtn.disabled = false;
            exportBtn.innerHTML = '<i class="fas fa-file-export me-2"></i>Export Survey';
        }
    });

    // Display language tags in export settings
    function updateLanguageTags() {
        const container = document.getElementById('exportLanguageTags');
        if (!container) return;
        const langs = customizationState.survey.languages || ['en'];
        const baseLang = customizationState.survey.base_language || 'en';
        container.innerHTML = langs.map(l =>
            `<span class="lang-tag ${l === baseLang ? 'base' : ''}" title="${l === baseLang ? 'Base language' : 'Additional language'}">${l.toUpperCase()}</span>`
        ).join('');
    }

    // Update preview language switcher above question list
    function updatePreviewLangSwitcher() {
        const container = document.getElementById('previewLangSwitcher');
        if (!container) return;
        // Use the user's selected export languages for the preview switcher
        const langs = customizationState.survey.languages || ['en'];

        if (langs.length <= 1) {
            container.classList.add('d-none');
            container.innerHTML = '';
            return;
        }

        // Ensure previewLanguage is valid
        if (!langs.includes(previewLanguage)) {
            previewLanguage = langs[0];
        }

        container.classList.remove('d-none');
        container.innerHTML = '<span class="switcher-label"><i class="fas fa-eye me-1"></i>Preview:</span>' +
            langs.map(l =>
                `<span class="lang-tag clickable${l === previewLanguage ? ' active' : ''}" data-lang="${l}">${l.toUpperCase()}</span>`
            ).join('');

        // Click handlers
        container.querySelectorAll('.lang-tag.clickable').forEach(tag => {
            tag.addEventListener('click', () => {
                previewLanguage = tag.dataset.lang;
                container.querySelectorAll('.lang-tag.clickable').forEach(t => t.classList.remove('active'));
                tag.classList.add('active');
                updateQuestionDescriptions();
            });
        });
    }

    // Update question description text for current previewLanguage
    function updateQuestionDescriptions() {
        // Update standalone question items
        document.querySelectorAll('.question-item').forEach(qDiv => {
            const qid = qDiv.dataset.questionId;
            const gid = qDiv.dataset.groupId;
            if (!qid || !gid) return;

            const group = customizationState.groups.find(g => g.id === gid);
            if (!group) return;
            const q = group.questions.find(qq => qq.id === qid);
            if (!q) return;

            const desc = getText(q.originalData && q.originalData.Description, previewLanguage) || q.description || 'No description';
            const descEl = qDiv.querySelector('.question-desc');
            if (descEl) {
                descEl.textContent = desc;
                descEl.title = desc;
            }
        });

        // Update matrix subquestion descriptions
        document.querySelectorAll('.matrix-subquestion').forEach(subDiv => {
            const qid = subDiv.dataset.questionId;
            const gid = subDiv.dataset.groupId;
            if (!qid || !gid) return;

            const group = customizationState.groups.find(g => g.id === gid);
            if (!group) return;
            const q = group.questions.find(qq => qq.id === qid);
            if (!q) return;

            const desc = getText(q.originalData && q.originalData.Description, previewLanguage) || q.description || '';
            const descEl = subDiv.querySelector('.sub-desc');
            if (descEl) {
                descEl.textContent = desc;
                descEl.title = desc;
            }
        });
    }

    // Build LimeSurvey tool settings panel HTML for a question
    function buildToolSettingsPanel(groupId, question) {
        const ov = question.toolOverrides || {};
        const panelId = `tool-panel-${groupId}-${question.id}`;
        const detectedType = detectQuestionType(question);
        return `
            <div class="tool-settings-panel" id="${panelId}" data-detected-type="${detectedType}">
                <!-- Row 1: Universal fields -->
                <div class="row g-2">
                    <div class="col-md-3">
                        <label class="form-label">Question Type</label>
                        <select class="form-select ts-questionType">
                            <option value="">Auto-detect (${detectedType})</option>
                            <option value="L" ${ov.questionType === 'L' ? 'selected' : ''}>L - List (Radio)</option>
                            <option value="!" ${ov.questionType === '!' ? 'selected' : ''}>! - List (Dropdown)</option>
                            <option value="F" ${ov.questionType === 'F' ? 'selected' : ''}>F - Array (Matrix)</option>
                            <option value="N" ${ov.questionType === 'N' ? 'selected' : ''}>N - Numerical</option>
                            <option value="S" ${ov.questionType === 'S' ? 'selected' : ''}>S - Short Text</option>
                            <option value="T" ${ov.questionType === 'T' ? 'selected' : ''}>T - Long Text</option>
                            <option value="*" ${ov.questionType === '*' ? 'selected' : ''}>* - Equation</option>
                            <option value="X" ${ov.questionType === 'X' ? 'selected' : ''}>X - Boilerplate</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">CSS Class</label>
                        <input type="text" class="form-control ts-cssClass" placeholder="e.g. my-class"
                               value="${escapeHtml(ov.cssClass || '')}">
                    </div>
                    <div class="col-md-2 d-flex align-items-end gap-3">
                        <div class="form-check" title="Hidden question">
                            <input class="form-check-input ts-hidden" type="checkbox" ${ov.hidden ? 'checked' : ''}>
                            <label class="form-check-label small">Hidden</label>
                        </div>
                        <div class="form-check" title="Page break before this question">
                            <input class="form-check-input ts-pageBreak" type="checkbox" ${ov.pageBreak ? 'checked' : ''}>
                            <label class="form-check-label small">Page break</label>
                        </div>
                    </div>
                </div>
                <!-- Row 2: Question text override -->
                <div class="row g-2 mt-1">
                    <div class="col-md-8">
                        <label class="form-label">Question Text <span class="html-hint" title="HTML tags are supported"><i class="fas fa-code"></i> HTML</span></label>
                        <input type="text" class="form-control ts-questionText" placeholder="${escapeHtml(question.description || '')}"
                               value="${escapeHtml(ov.questionText || '')}">
                    </div>
                </div>
                <!-- Row 3: Relevance and help -->
                <div class="row g-2 mt-1">
                    <div class="col-md-4">
                        <label class="form-label">Relevance (Logic)</label>
                        <input type="text" class="form-control ts-relevance" placeholder="e.g. Q1 == 'Y'"
                               value="${escapeHtml(ov.relevance || '')}">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Help Text <span class="html-hint" title="HTML tags are supported"><i class="fas fa-code"></i> HTML</span></label>
                        <input type="text" class="form-control ts-helpText"
                               value="${escapeHtml(ov.helpText || '')}">
                    </div>
                </div>
                <!-- Row 3: Type-specific fields -->
                <div class="row g-2 mt-1">
                    <!-- Numerical / Text shared -->
                    <div class="col-md-2 ts-field" data-for-types="N,S,T">
                        <label class="form-label">Input Width (1-12)</label>
                        <input type="number" class="form-control ts-inputWidth" min="1" max="12"
                               value="${ov.inputWidth || ''}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="N,S,T">
                        <label class="form-label">Input Size</label>
                        <input type="number" class="form-control ts-inputSize" min="1"
                               value="${ov.inputSize || ''}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="S,T">
                        <label class="form-label">Display Rows</label>
                        <input type="number" class="form-control ts-displayRows" min="1" max="50"
                               value="${ov.displayRows || ''}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="N,S,T">
                        <label class="form-label">Max Chars</label>
                        <input type="number" class="form-control ts-maximumChars" min="1"
                               value="${ov.maximumChars || ''}">
                    </div>
                    <!-- Numerical validation -->
                    <div class="col-md-2 ts-field" data-for-types="N">
                        <label class="form-label">Val. Min</label>
                        <input type="number" class="form-control ts-validationMin"
                               value="${ov.validationMin != null ? ov.validationMin : ''}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="N">
                        <label class="form-label">Val. Max</label>
                        <input type="number" class="form-control ts-validationMax"
                               value="${ov.validationMax != null ? ov.validationMax : ''}">
                    </div>
                    <div class="col-md-1 ts-field d-flex align-items-end" data-for-types="N">
                        <div class="form-check" title="Integer Only">
                            <input class="form-check-input ts-integerOnly" type="checkbox" ${ov.integerOnly ? 'checked' : ''}>
                            <label class="form-check-label small">Int</label>
                        </div>
                    </div>
                    <!-- Prefix / Suffix / Placeholder (Numerical & Text) -->
                    <div class="col-md-2 ts-field" data-for-types="N,S,T">
                        <label class="form-label">Prefix</label>
                        <input type="text" class="form-control ts-prefix" value="${escapeHtml(ov.prefix || '')}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="N,S">
                        <label class="form-label">Suffix</label>
                        <input type="text" class="form-control ts-suffix" value="${escapeHtml(ov.suffix || '')}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="N,S,T">
                        <label class="form-label">Placeholder</label>
                        <input type="text" class="form-control ts-placeholder" value="${escapeHtml(ov.placeholder || '')}">
                    </div>
                    <!-- Numbers Only (Text & Equation) -->
                    <div class="col-md-1 ts-field d-flex align-items-end" data-for-types="S,T,*">
                        <div class="form-check" title="Numbers only">
                            <input class="form-check-input ts-numbersOnly" type="checkbox" ${ov.numbersOnly ? 'checked' : ''}>
                            <label class="form-check-label small">Num</label>
                        </div>
                    </div>
                    <!-- List Radio specific -->
                    <div class="col-md-2 ts-field" data-for-types="L">
                        <label class="form-label">Display Columns</label>
                        <input type="number" class="form-control ts-displayColumns" min="1" max="4"
                               value="${ov.displayColumns || ''}">
                    </div>
                    <div class="col-md-1 ts-field d-flex align-items-end" data-for-types="L,!">
                        <div class="form-check" title="Sort answers alphabetically">
                            <input class="form-check-input ts-alphasort" type="checkbox" ${ov.alphasort ? 'checked' : ''}>
                            <label class="form-check-label small">Sort</label>
                        </div>
                    </div>
                    <!-- List Dropdown specific -->
                    <div class="col-md-2 ts-field" data-for-types="!">
                        <label class="form-label">Dropdown Size</label>
                        <input type="number" class="form-control ts-dropdownSize" min="1"
                               value="${ov.dropdownSize || ''}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="!">
                        <label class="form-label">Dropdown Prefix</label>
                        <select class="form-select ts-dropdownPrefix">
                            <option value="" ${!ov.dropdownPrefix ? 'selected' : ''}>Default</option>
                            <option value="none" ${ov.dropdownPrefix === 'none' ? 'selected' : ''}>None</option>
                            <option value="order" ${ov.dropdownPrefix === 'order' ? 'selected' : ''}>Order number</option>
                        </select>
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="!">
                        <label class="form-label">Category Separator</label>
                        <input type="text" class="form-control ts-categorySeparator"
                               value="${escapeHtml(ov.categorySeparator || '')}">
                    </div>
                    <!-- Array/Matrix specific -->
                    <div class="col-md-2 ts-field" data-for-types="F">
                        <label class="form-label">Answer Width (%)</label>
                        <input type="number" class="form-control ts-answerWidth" min="1" max="100"
                               value="${ov.answerWidth || ''}">
                    </div>
                    <div class="col-md-2 ts-field" data-for-types="F">
                        <label class="form-label">Repeat Headings</label>
                        <input type="number" class="form-control ts-repeatHeadings" min="0"
                               value="${ov.repeatHeadings || ''}">
                    </div>
                    <div class="col-md-1 ts-field d-flex align-items-end" data-for-types="F">
                        <div class="form-check" title="Use dropdown instead of radio in matrix">
                            <input class="form-check-input ts-useDropdown" type="checkbox" ${ov.useDropdown ? 'checked' : ''}>
                            <label class="form-check-label small">Drop</label>
                        </div>
                    </div>
                    <!-- Equation specific -->
                    <div class="col-md-4 ts-field" data-for-types="*">
                        <label class="form-label">Equation</label>
                        <input type="text" class="form-control ts-equation" placeholder="Calculated field formula"
                               value="${escapeHtml(ov.equation || '')}">
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Show/hide type-specific fields based on the active question type.
     */
    function updateTypeSpecificFields(panelEl) {
        const typeSelect = panelEl.querySelector('.ts-questionType');
        const detectedType = panelEl.dataset.detectedType || 'T';
        const activeType = typeSelect.value || detectedType;

        panelEl.querySelectorAll('.ts-field').forEach(field => {
            const forTypes = (field.dataset.forTypes || '').split(',');
            if (forTypes.includes(activeType)) {
                field.classList.add('visible');
            } else {
                field.classList.remove('visible');
            }
        });
    }

    // Save tool settings from panel inputs back to question state
    function saveToolSettings(groupId, questionId, panelEl) {
        const group = customizationState.groups.find(g => g.id === groupId);
        if (!group) return;
        const question = group.questions.find(q => q.id === questionId);
        if (!question) return;

        const ov = question.toolOverrides || {};

        // Helpers: read value, set or delete from ov
        function readVal(selector, key, parser) {
            const el = panelEl.querySelector(selector);
            if (!el) return;
            const v = el.value;
            if (v !== '' && v !== undefined) {
                ov[key] = parser ? parser(v) : v;
            } else {
                delete ov[key];
            }
        }
        function readBool(selector, key) {
            const el = panelEl.querySelector(selector);
            if (!el) return;
            if (el.checked) ov[key] = true;
            else delete ov[key];
        }

        // Universal fields
        readVal('.ts-questionType', 'questionType', null);
        readVal('.ts-cssClass', 'cssClass', null);
        readBool('.ts-hidden', 'hidden');
        readBool('.ts-pageBreak', 'pageBreak');
        readVal('.ts-questionText', 'questionText', null);
        readVal('.ts-relevance', 'relevance', null);
        readVal('.ts-helpText', 'helpText', null);

        // Numerical / Text shared
        readVal('.ts-inputWidth', 'inputWidth', v => parseInt(v, 10));
        readVal('.ts-inputSize', 'inputSize', v => parseInt(v, 10));
        readVal('.ts-displayRows', 'displayRows', v => parseInt(v, 10));
        readVal('.ts-maximumChars', 'maximumChars', v => parseInt(v, 10));
        readVal('.ts-prefix', 'prefix', null);
        readVal('.ts-suffix', 'suffix', null);
        readVal('.ts-placeholder', 'placeholder', null);

        // Numerical validation
        readVal('.ts-validationMin', 'validationMin', v => parseFloat(v));
        readVal('.ts-validationMax', 'validationMax', v => parseFloat(v));
        readBool('.ts-integerOnly', 'integerOnly');

        // Text / Equation
        readBool('.ts-numbersOnly', 'numbersOnly');

        // List Radio / Dropdown
        readVal('.ts-displayColumns', 'displayColumns', v => parseInt(v, 10));
        readBool('.ts-alphasort', 'alphasort');
        readVal('.ts-dropdownSize', 'dropdownSize', v => parseInt(v, 10));
        readVal('.ts-dropdownPrefix', 'dropdownPrefix', null);
        readVal('.ts-categorySeparator', 'categorySeparator', null);

        // Array/Matrix
        readVal('.ts-answerWidth', 'answerWidth', v => parseInt(v, 10));
        readVal('.ts-repeatHeadings', 'repeatHeadings', v => parseInt(v, 10));
        readBool('.ts-useDropdown', 'useDropdown');

        // Equation
        readVal('.ts-equation', 'equation', null);

        question.toolOverrides = ov;
    }

    // Utility: escape HTML
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Wire matrix mode toggles to re-render question hierarchy
    document.getElementById('matrixMode').addEventListener('change', (e) => {
        customizationState.exportOptions.matrix = e.target.checked;
        renderQuestions();
    });
    document.getElementById('globalMatrix').addEventListener('change', (e) => {
        customizationState.exportOptions.matrix_global = e.target.checked;
        renderQuestions();
    });

    // --- Text templates ---

    // Welcome message templates
    const welcomeTemplates = {
        standard: '<h3>Welcome to Our Study</h3>\n<p>Thank you for your interest in participating in this research study.</p>\n<p>On the following pages you will be asked to answer a series of questionnaires.\nPlease read each question carefully and select the response that best applies to you.\nThere are no right or wrong answers.</p>\n<p>The survey will take approximately <strong>[DURATION] minutes</strong> to complete.</p>',
        academic: '<h3>[STUDY TITLE]</h3>\n<p>Principal Investigator: [PI NAME], [DEPARTMENT], [INSTITUTION]</p>\n<p>Thank you for participating in this research study. Your responses will contribute to\nour understanding of [RESEARCH TOPIC].</p>\n<p>Please complete the following questionnaires in one sitting. The survey takes approximately\n<strong>[DURATION] minutes</strong>. You may skip any question you prefer not to answer.</p>\n<p>If you have any questions, please contact <a href="mailto:[EMAIL]">[EMAIL]</a>.</p>',
        brief: '<p>Welcome! Please answer the following questions. This takes about <strong>[DURATION] minutes</strong>.</p>'
    };

    // End message templates
    const endTemplates = {
        standard: '<h3>Thank You!</h3>\n<p>Your responses have been recorded successfully.</p>\n<p>We greatly appreciate the time you have taken to complete this survey.\nYour contribution is valuable to our research.</p>\n<p>If you have any questions about this study, please contact us at <a href="mailto:[EMAIL]">[EMAIL]</a>.</p>',
        academic: '<h3>Study Complete</h3>\n<p>Thank you for completing this survey.</p>\n<p><strong>Purpose of this study:</strong> This research investigates [RESEARCH TOPIC].\nYour responses will help us [RESEARCH GOAL].</p>\n<p><strong>Principal Investigator:</strong> [PI NAME], [DEPARTMENT]<br>\n<strong>Contact:</strong> <a href="mailto:[EMAIL]">[EMAIL]</a></p>\n<p>If you experienced any discomfort during this survey, please contact [SUPPORT RESOURCE].</p>',
        brief: '<p>Thank you for completing the survey! Your response has been saved.</p>',
        redirect: '<p>Thank you for completing the survey. You will be redirected shortly.</p>\n<p>If you are not redirected automatically, please click the link below.</p>'
    };

    // Consent / data policy templates
    const consentTemplates = {
        standard: '<p>This study has been approved by [ETHICS COMMITTEE NAME] (approval number: [NUMBER]).</p>\n<p>Your participation is voluntary. You may withdraw at any time without giving a reason.</p>\n<p>Your data will be collected anonymously and used solely for research purposes.\nAll data will be stored securely in accordance with applicable data protection regulations.</p>\n<p>By clicking "Next", you confirm that you have read and understood this information\nand consent to participate.</p>',
        gdpr: '<p><strong>Data Protection Information (GDPR Art. 13/14)</strong></p>\n<p><strong>Data Controller:</strong> [INSTITUTION NAME], [ADDRESS]</p>\n<p><strong>Purpose:</strong> Your data is processed for scientific research purposes (GDPR Art. 6(1)(a) and Art. 9(2)(a)).</p>\n<p><strong>Data collected:</strong> Survey responses, timestamps, and basic demographic information.\nNo personally identifiable information beyond what you provide is collected.</p>\n<p><strong>Storage &amp; retention:</strong> Data is stored on secure servers within the EU/EEA.\nAnonymized research data will be retained for [DURATION] years in accordance with\ngood scientific practice. Raw data will be deleted after analysis.</p>\n<p><strong>Your rights:</strong> You have the right to access, rectify, or erase your data,\nand to withdraw consent at any time (GDPR Art. 15-21). Contact the Data Protection Officer\nat <a href="mailto:[DPO EMAIL]">[DPO EMAIL]</a>.</p>\n<p>By clicking "Next", you confirm that you consent to the processing of your data as described above.</p>',
        anonymous: '<p>This is an <strong>anonymous survey</strong>. No identifying information (name, email, IP address)\nis collected or stored. Your responses cannot be linked back to you.</p>\n<p>Your participation is voluntary. You may close the browser at any time to withdraw.\nOnce submitted, responses cannot be deleted as they are not linked to any individual.</p>\n<p>By continuing, you agree to participate.</p>',
        longitudinal: '<p>This study involves <strong>multiple data collection points</strong>. You will be asked to\ncomplete follow-up surveys at [TIMEPOINTS].</p>\n<p>A participant code will be used to link your responses across sessions.\nThis code does not contain personally identifiable information.</p>\n<p>Your participation is voluntary at each stage. You may withdraw from future sessions\nat any time without affecting your previous responses or any compensation due.</p>\n<p>All data will be stored securely and treated confidentially in accordance with\napplicable data protection regulations.</p>\n<p>By clicking "Next", you consent to participate in this session of the study.</p>',
        minimal: '<p>Your participation is voluntary and anonymous. You may stop at any time.</p>\n<p>By continuing, you consent to participate in this study.</p>'
    };

    // Wire up template dropdowns
    document.getElementById('lsWelcomeTemplate').addEventListener('change', function() {
        if (this.value && welcomeTemplates[this.value]) {
            document.getElementById('lsWelcomeText').value = welcomeTemplates[this.value];
        }
    });

    document.getElementById('lsEndTemplate').addEventListener('change', function() {
        if (this.value && endTemplates[this.value]) {
            document.getElementById('lsEndText').value = endTemplates[this.value];
        }
    });

    document.getElementById('lsConsentTemplate').addEventListener('change', function() {
        const policyTextarea = document.getElementById('lsPolicyNotice');
        if (this.value && consentTemplates[this.value]) {
            policyTextarea.value = consentTemplates[this.value];
        }
    });

    // Save LS settings to sessionStorage
    function saveLsSettings() {
        try {
            sessionStorage.setItem('surveyCustomizerLsSettings', JSON.stringify(customizationState.lsSettings));
        } catch (e) { /* ignore quota errors */ }
    }

    // Auto-save LS settings when any field changes
    document.getElementById('lsSettingsSection').addEventListener('change', function() {
        // Read current values into state
        customizationState.lsSettings = {
            welcomeText: document.getElementById('lsWelcomeText').value,
            endText: document.getElementById('lsEndText').value,
            endUrl: document.getElementById('lsEndUrl').value,
            endUrlDescription: document.getElementById('lsEndUrlDescription').value,
            showDataPolicy: document.getElementById('lsShowDataPolicy').value,
            policyNotice: document.getElementById('lsPolicyNotice').value,
            policyError: document.getElementById('lsPolicyError').value,
            policyCheckboxLabel: document.getElementById('lsPolicyCheckboxLabel').value,
            navigationDelay: document.getElementById('lsNavigationDelay').value,
            questionIndex: document.getElementById('lsQuestionIndex').value,
            showGroupInfo: document.getElementById('lsShowGroupInfo').value,
            showQnumCode: document.getElementById('lsShowQnumCode').value,
            showNoAnswer: document.getElementById('lsShowNoAnswer').value,
            showXQuestions: document.getElementById('lsShowXQuestions').value,
            showWelcome: document.getElementById('lsShowWelcome').value,
            allowPrev: document.getElementById('lsAllowPrev').value,
            noKeyboard: document.getElementById('lsNoKeyboard').value,
            showProgress: document.getElementById('lsShowProgress').value,
            printAnswers: document.getElementById('lsPrintAnswers').value,
            publicStatistics: document.getElementById('lsPublicStatistics').value,
            publicGraphs: document.getElementById('lsPublicGraphs').value,
            autoRedirect: document.getElementById('lsAutoRedirect').value
        };
        saveLsSettings();
    });

    // Also save on textarea input (change doesn't fire until blur for textareas)
    document.querySelectorAll('#lsSettingsSection textarea').forEach(el => {
        el.addEventListener('input', function() {
            // Debounced save: update state and persist
            const id = this.id;
            const keyMap = {
                lsWelcomeText: 'welcomeText', lsEndText: 'endText',
                lsPolicyNotice: 'policyNotice', lsPolicyError: 'policyError'
            };
            if (keyMap[id]) {
                customizationState.lsSettings[keyMap[id]] = this.value;
                saveLsSettings();
            }
        });
    });

    // Populate LS settings form from state (used after sessionStorage load)
    function populateLsSettingsForm(ls) {
        if (!ls) return;
        const fieldMap = {
            welcomeText: 'lsWelcomeText',
            endText: 'lsEndText',
            endUrl: 'lsEndUrl',
            endUrlDescription: 'lsEndUrlDescription',
            showDataPolicy: 'lsShowDataPolicy',
            policyNotice: 'lsPolicyNotice',
            policyError: 'lsPolicyError',
            policyCheckboxLabel: 'lsPolicyCheckboxLabel',
            navigationDelay: 'lsNavigationDelay',
            questionIndex: 'lsQuestionIndex',
            showGroupInfo: 'lsShowGroupInfo',
            showQnumCode: 'lsShowQnumCode',
            showNoAnswer: 'lsShowNoAnswer',
            showXQuestions: 'lsShowXQuestions',
            showWelcome: 'lsShowWelcome',
            allowPrev: 'lsAllowPrev',
            noKeyboard: 'lsNoKeyboard',
            showProgress: 'lsShowProgress',
            printAnswers: 'lsPrintAnswers',
            publicStatistics: 'lsPublicStatistics',
            publicGraphs: 'lsPublicGraphs',
            autoRedirect: 'lsAutoRedirect'
        };
        for (const [key, elId] of Object.entries(fieldMap)) {
            const el = document.getElementById(elId);
            if (el && ls[key] !== undefined) {
                el.value = ls[key];
            }
        }
    }

    // Initialize
    loadFromSessionStorage();
});
