/**
 * Survey participant-metadata workflow module.
 *
 * Extracted from survey-convert.js to keep converter workflow orchestration thin
 * while preserving existing behavior.
 */

import { fetchWithApiFallback } from '../../shared/api.js';

export function createSurveyParticipantsMetadataController({ escapeHtml }) {
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
                    const response = await fetchWithApiFallback('/api/projects/participants', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            survey_schema_merge_mode: 'survey_selected',
                            survey_selected_schema: schema,
                        })
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

    return {
        displayParticipantMetadataSection,
    };
}
