import { fetchWithRelativePathFallback } from './shared/api.js';

function parseEditorConfig() {
    const configNode = document.getElementById('libraryEditorConfig');
    if (!configNode) {
        throw new Error('Library editor config is missing.');
    }

    const rawConfig = String(configNode.textContent || '').trim();
    if (!rawConfig) {
        throw new Error('Library editor config is empty.');
    }

    const parsed = JSON.parse(rawConfig);
    return {
        filename: String(parsed.filename || '').trim(),
        content: parsed.content && typeof parsed.content === 'object' ? parsed.content : {},
    };
}

function createLevelRow(value = '', label = '') {
    return `
        <div class="input-group mb-1 level-row">
            <input type="text" class="form-control" data-help-key="libraryLevelValue" placeholder="Value (e.g. 1)" value="${value}" style="max-width: 100px;">
            <input type="text" class="form-control" data-help-key="libraryLevelLabel" placeholder="Label (e.g. Strongly Disagree)" value="${label}">
            <button type="button" class="btn btn-outline-secondary" data-action="remove-level"><i class="bi bi-x"></i></button>
        </div>
    `;
}

function createQuestionCard(key, question) {
    const card = document.createElement('div');
    card.className = 'card mb-3 shadow-sm question-card';
    card.dataset.originalKey = key;

    let levelsHtml = '';
    if (question.Levels && typeof question.Levels === 'object') {
        Object.entries(question.Levels).forEach(([value, label]) => {
            levelsHtml += createLevelRow(value, label);
        });
    }

    card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center bg-white">
            <div class="input-group" style="max-width: 400px;">
                <span class="input-group-text bg-light fw-bold">ID</span>
                <input type="text" class="form-control fw-bold question-id" data-help-key="libraryQuestionId" value="${key}" placeholder="Question ID (e.g. Q1)">
            </div>
            <button type="button" class="btn btn-outline-danger btn-sm" data-action="remove-question">
                <i class="bi bi-trash"></i>
            </button>
        </div>
        <div class="card-body">
            <div class="mb-3">
                <label class="form-label small text-muted">Question Text / Description</label>
                <textarea class="form-control question-desc" data-help-key="libraryQuestionDescription" rows="2">${question.Description || ''}</textarea>
            </div>

            <div class="row g-3 mb-3">
                <div class="col-md-3">
                    <label class="form-label small text-muted">Type</label>
                    <select class="form-select question-type" data-help-key="libraryQuestionType">
                        <option value="integer" ${question.DataType === 'integer' ? 'selected' : ''}>Integer</option>
                        <option value="float" ${question.DataType === 'float' ? 'selected' : ''}>Float</option>
                        <option value="string" ${question.DataType === 'string' ? 'selected' : ''}>String</option>
                        <option value="boolean" ${question.DataType === 'boolean' ? 'selected' : ''}>Boolean</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label small text-muted">Unit</label>
                    <input type="text" class="form-control question-units" data-help-key="libraryQuestionUnit" value="${question.Unit || ''}">
                </div>
            </div>

            <div class="row g-3 mb-3 bg-light p-2 rounded mx-0">
                <div class="col-md-3">
                    <label class="form-label small text-muted">Min</label>
                    <input type="number" class="form-control question-min" data-help-key="libraryQuestionMin" value="${question.MinValue !== undefined ? question.MinValue : ''}">
                </div>
                <div class="col-md-3">
                    <label class="form-label small text-muted">Max</label>
                    <input type="number" class="form-control question-max" data-help-key="libraryQuestionMax" value="${question.MaxValue !== undefined ? question.MaxValue : ''}">
                </div>
                <div class="col-md-3">
                    <label class="form-label small text-muted text-warning">Warn Min</label>
                    <input type="number" class="form-control question-warn-min" data-help-key="libraryQuestionWarnMin" value="${question.WarnMinValue !== undefined ? question.WarnMinValue : ''}">
                </div>
                <div class="col-md-3">
                    <label class="form-label small text-muted text-warning">Warn Max</label>
                    <input type="number" class="form-control question-warn-max" data-help-key="libraryQuestionWarnMax" value="${question.WarnMaxValue !== undefined ? question.WarnMaxValue : ''}">
                </div>
            </div>

            <div class="levels-section">
                <label class="form-label small text-muted">Answer Levels (Likert / Categories)</label>
                <div class="levels-container">
                    ${levelsHtml}
                </div>
                <button type="button" class="btn btn-sm btn-outline-secondary mt-2" data-action="add-level">
                    <i class="bi bi-plus"></i> Add Level
                </button>
            </div>
        </div>
    `;

    return card;
}

function addLevelRow(button) {
    const container = button.previousElementSibling;
    if (!container) {
        return;
    }

    const wrapper = document.createElement('div');
    wrapper.innerHTML = createLevelRow();
    container.appendChild(wrapper.firstElementChild);
}

document.addEventListener('DOMContentLoaded', () => {
    let config;
    try {
        config = parseEditorConfig();
    } catch (error) {
        window.alert(error.message || 'Could not initialize Library Editor.');
        return;
    }

    let currentData = config.content;
    const filename = config.filename;

    const metaName = document.getElementById('meta-name');
    const metaDesc = document.getElementById('meta-desc');
    const questionsContainer = document.getElementById('questions-container');
    const simpleView = document.getElementById('simple-view');
    const simpleTab = document.getElementById('simple-tab');
    const jsonTab = document.getElementById('json-tab');
    const advancedUnavailableNotice = document.getElementById('libraryAdvancedUnavailableNotice');
    const addQuestionCardBtn = document.getElementById('addQuestionCardBtn');
    const saveSurveyBtn = document.getElementById('saveSurveyBtn');

    if (!metaName || !metaDesc || !questionsContainer || !simpleView || !saveSurveyBtn) {
        return;
    }

    let editor = null;
    const jsonEditorContainer = document.getElementById('jsoneditor');

    if (typeof window.JSONEditor === 'function' && jsonEditorContainer) {
        const options = { mode: 'tree', modes: ['code', 'tree'] };
        editor = new window.JSONEditor(jsonEditorContainer, options);
        editor.set(currentData);
    } else if (jsonTab) {
        jsonTab.classList.add('disabled');
        jsonTab.disabled = true;
        jsonTab.setAttribute('aria-disabled', 'true');
        jsonTab.setAttribute('title', 'Advanced JSON is unavailable in this runtime.');
        jsonTab.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
        });
        if (advancedUnavailableNotice) {
            advancedUnavailableNotice.classList.remove('d-none');
        }
    }

    function renderSimpleEditor(data) {
        metaName.value = data.Name || '';
        metaDesc.value = data.Description || '';

        questionsContainer.innerHTML = '';
        const questions = data.Questions || {};

        Object.entries(questions).forEach(([key, question]) => {
            questionsContainer.appendChild(createQuestionCard(key, question));
        });
    }

    function scrapeSimpleEditor() {
        const data = { ...currentData };

        data.Name = metaName.value;
        data.Description = metaDesc.value;

        const questions = {};
        document.querySelectorAll('.question-card').forEach((card) => {
            const id = card.querySelector('.question-id')?.value.trim();
            if (!id) {
                return;
            }

            const question = {};
            question.Description = card.querySelector('.question-desc')?.value || '';
            question.DataType = card.querySelector('.question-type')?.value || 'integer';

            const units = card.querySelector('.question-units')?.value || '';
            if (units) {
                question.Unit = units;
            }

            const min = card.querySelector('.question-min')?.value || '';
            if (min !== '') {
                question.MinValue = Number(min);
            }

            const max = card.querySelector('.question-max')?.value || '';
            if (max !== '') {
                question.MaxValue = Number(max);
            }

            const warnMin = card.querySelector('.question-warn-min')?.value || '';
            if (warnMin !== '') {
                question.WarnMinValue = Number(warnMin);
            }

            const warnMax = card.querySelector('.question-warn-max')?.value || '';
            if (warnMax !== '') {
                question.WarnMaxValue = Number(warnMax);
            }

            const levels = {};
            let hasLevels = false;
            card.querySelectorAll('.level-row').forEach((row) => {
                const inputs = row.querySelectorAll('input');
                const value = (inputs[0]?.value || '').trim();
                const label = (inputs[1]?.value || '').trim();
                if (value) {
                    levels[value] = label;
                    hasLevels = true;
                }
            });
            if (hasLevels) {
                question.Levels = levels;
            }

            questions[id] = question;
        });

        data.Questions = questions;
        return data;
    }

    function syncToSimple() {
        if (!editor) {
            return;
        }

        try {
            currentData = editor.get();
            renderSimpleEditor(currentData);
        } catch (_error) {
            window.alert('Invalid JSON in Advanced View. Please fix it before switching.');
        }
    }

    function syncToJson() {
        if (!editor) {
            return;
        }

        currentData = scrapeSimpleEditor();
        editor.set(currentData);
    }

    function addQuestionCard() {
        const newId = `New_Question_${questionsContainer.children.length + 1}`;
        const defaultQuestion = {
            Description: '',
            DataType: 'integer',
            Levels: { '1': 'No', '2': 'Yes' },
        };
        questionsContainer.appendChild(createQuestionCard(newId, defaultQuestion));
        setTimeout(() => window.scrollTo(0, document.body.scrollHeight), 100);
    }

    async function saveSurvey() {
        let dataToSave;
        if (simpleView.classList.contains('active') || !editor) {
            dataToSave = scrapeSimpleEditor();
            if (editor) {
                editor.set(dataToSave);
            }
            currentData = dataToSave;
        } else {
            dataToSave = editor.get();
            currentData = dataToSave;
        }

        try {
            const response = await fetchWithRelativePathFallback(`/library/api/save/${encodeURIComponent(filename)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSave),
            });
            const payload = await response.json().catch(() => ({}));

            if (!response.ok || !payload.success) {
                throw new Error(payload.error || `Error saving draft (${response.status})`);
            }

            const originalHtml = saveSurveyBtn.innerHTML;
            saveSurveyBtn.innerHTML = '<i class="bi bi-check"></i> Saved!';
            saveSurveyBtn.classList.remove('btn-success');
            saveSurveyBtn.classList.add('btn-outline-success');
            setTimeout(() => {
                saveSurveyBtn.innerHTML = originalHtml;
                saveSurveyBtn.classList.add('btn-success');
                saveSurveyBtn.classList.remove('btn-outline-success');
            }, 2000);
        } catch (error) {
            window.alert(error.message || 'Network error while saving draft.');
        }
    }

    questionsContainer.addEventListener('click', (event) => {
        const actionButton = event.target.closest('button[data-action]');
        if (!actionButton) {
            return;
        }

        const action = actionButton.getAttribute('data-action');
        if (action === 'remove-question') {
            actionButton.closest('.question-card')?.remove();
            return;
        }
        if (action === 'add-level') {
            addLevelRow(actionButton);
            return;
        }
        if (action === 'remove-level') {
            actionButton.closest('.level-row')?.remove();
        }
    });

    saveSurveyBtn.addEventListener('click', saveSurvey);
    simpleTab?.addEventListener('click', syncToSimple);
    jsonTab?.addEventListener('click', syncToJson);
    addQuestionCardBtn?.addEventListener('click', addQuestionCard);

    renderSimpleEditor(currentData);
});
