document.addEventListener('DOMContentLoaded', async function() {
    const jsonFileInput = document.getElementById('jsonFileInput');
    const jsonFileBtn = document.getElementById('jsonFileBtn');
    const uploadArea = document.getElementById('uploadArea');
    const fileOpenCard = document.getElementById('fileOpenCard');
    const editorSection = document.getElementById('editorSection');
    const editorFileName = document.getElementById('editorFileName');
    const alertContainer = document.getElementById('alertContainer');
    const openDifferentFileBtn = document.getElementById('openDifferentFileBtn');

    // Check for autoload parameter (coming from project page e.g. ?autoload=participants&from=project)
    const urlParams = new URLSearchParams(window.location.search);
    const autoloadFile = urlParams.get('autoload');
    const fromProject = urlParams.get('from') === 'project';

    if (fromProject && autoloadFile) {
        fileOpenCard.style.display = 'none';
        editorSection.style.display = 'block';
        editorFileName.textContent = autoloadFile + '.json';
        await loadFileFromProject(autoloadFile);
    }

    // Open file button
    jsonFileBtn.addEventListener('click', () => jsonFileInput.click());

    // "Open different file" resets to the picker
    openDifferentFileBtn.addEventListener('click', () => {
        editorSection.style.display = 'none';
        fileOpenCard.style.display = 'block';
    });

    // File input change
    jsonFileInput.addEventListener('change', async function() {
        if (!jsonFileInput.files.length) return;
        await openJsonFile(jsonFileInput.files[0]);
        jsonFileInput.value = ''; // allow re-opening the same file
    });

    // Drag and drop support
    uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('dragover'); });
    uploadArea.addEventListener('dragleave', e => { e.preventDefault(); uploadArea.classList.remove('dragover'); });
    uploadArea.addEventListener('drop', async function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.name.toLowerCase().endsWith('.json')) {
            await openJsonFile(file);
        } else {
            showAlert('Please drop a .json file.', 'warning');
        }
    });

    async function openJsonFile(file) {
        try {
            const content = await file.text();
            const jsonData = JSON.parse(content);
            fileOpenCard.style.display = 'none';
            editorSection.style.display = 'block';
            editorFileName.textContent = file.name;
            await renderJSONForm(jsonData, file.name);
        } catch (e) {
            showAlert('Invalid JSON file: ' + e.message, 'danger');
        }
    }

    // Load a file by type from the current project via backend API
    async function loadFileFromProject(fileType) {
        try {
            const response = await fetch(`/editor/api/file/${fileType}`);
            if (!response.ok) {
                showAlert(`File ${fileType}.json not found in current project.`, 'warning');
                return;
            }
            const result = await response.json();
            if (result.success) {
                await renderJSONForm(result.data, `${fileType}.json`);
                showAlert(`Loaded ${fileType}.json from project`, 'success');
            } else {
                showAlert(result.error || 'Failed to load file', 'danger');
            }
        } catch (error) {
            showAlert('Error loading file: ' + error.message, 'danger');
        }
    }

    // Save / Download the edited JSON
    document.getElementById('saveBtn').addEventListener('click', async function() {
        try {
            let updatedJson;
            const fileName = (window.currentFilePath || 'file.json').split('/').pop();
            const fileType = fileName.replace('.json', '');

            if (fileType === 'participants') {
                updatedJson = {};
                document.querySelectorAll('[data-json-path]').forEach(textarea => {
                    const path = textarea.dataset.jsonPath;
                    const raw = textarea.value;
                    try {
                        let parsed;
                        if (raw.trim().startsWith('{') || raw.trim().startsWith('[')) parsed = JSON.parse(raw);
                        else if (raw === 'true' || raw === 'false') parsed = JSON.parse(raw);
                        else if (raw === 'null') parsed = null;
                        else if (!isNaN(raw) && raw !== '') parsed = Number(raw);
                        else parsed = raw;
                        const parts = path.split('.');
                        let cur = updatedJson;
                        for (let i = 0; i < parts.length - 1; i++) {
                            if (!cur[parts[i]]) cur[parts[i]] = {};
                            cur = cur[parts[i]];
                        }
                        cur[parts[parts.length - 1]] = parsed;
                    } catch (e) {
                        showAlert(`Invalid value for "${path}": ${e.message}`, 'warning');
                    }
                });
            } else {
                const form = document.querySelector('.bids-form');
                if (form && typeof BIDSFormGenerator !== 'undefined') {
                    updatedJson = BIDSFormGenerator.getFormData(form);
                } else {
                    const editor = document.getElementById('jsonEditor');
                    if (editor) {
                        updatedJson = JSON.parse(editor.value);
                    } else {
                        showAlert('No data to save', 'warning');
                        return;
                    }
                }
            }

            const blob = new Blob([JSON.stringify(updatedJson, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showAlert(`Downloaded: ${fileName}`, 'success');
        } catch (error) {
            showAlert('Error: ' + error.message, 'danger');
        }
    });

    // Render the JSON data as an editable form
    async function renderJSONForm(jsonData, filePath) {
        const formContainer = document.getElementById('formContainer');
        try {
            window.currentFilePath = filePath;
            window.currentFileData = jsonData;
            const fileName = filePath.split('/').pop();
            const fileType = fileName.replace('.json', '');

            // Try to get a BIDS schema for this file type
            const response = await fetch(`/editor/api/schema/${fileType}`);
            let schema = null;
            if (response.ok) {
                const schemaData = await response.json();
                if (schemaData.success) schema = schemaData.schema;
            }

            formContainer.innerHTML = '';

            if (schema && typeof BIDSFormGenerator !== 'undefined') {
                const form = BIDSFormGenerator.generateForm(schema, jsonData);
                formContainer.appendChild(form);
                showAlert(`Loaded: ${fileName}`, 'success');
            } else if (fileType === 'participants') {
                renderParticipantsForm(jsonData, fileName, formContainer);
            } else {
                // Generic textarea editor
                const jsonString = JSON.stringify(jsonData, null, 2);
                formContainer.innerHTML = `
                    <div class="mb-3">
                        <label for="jsonEditor" class="form-label">
                            <i class="fas fa-file-code me-2"></i>${fileName}
                        </label>
                        <textarea id="jsonEditor" class="form-control" rows="25"
                            style="font-family:'Courier New',monospace;font-size:13px;white-space:pre;overflow-wrap:normal;line-height:1.5;"></textarea>
                        <small class="text-muted d-block mt-2">
                            <i class="fas fa-info-circle me-1"></i>
                            Edit the JSON — click Save / Download when done
                        </small>
                    </div>
                `;
                document.getElementById('jsonEditor').value = jsonString;
                showAlert(`Loaded: ${fileName}`, 'success');
            }
        } catch (error) {
            formContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>Error rendering form: ${error.message}
                </div>`;
        }
    }

    // Participants.json — nested collapsible key/value form
    function renderParticipantsForm(jsonData, fileName, formContainer) {
        formContainer.innerHTML = `
            <div class="mb-3">
                <h5>${fileName}</h5>
                <p class="text-muted small">Edit JSON values. All keys are fixed.</p>
                <div id="participantsContainer"></div>
            </div>
        `;
        const container = document.getElementById('participantsContainer');

        function buildNestedForm(obj, parentKey = '', depth = 0) {
            const wrapper = document.createElement('div');
            Object.entries(obj).forEach(([key, value]) => {
                const fieldDiv = document.createElement('div');
                fieldDiv.className = 'mb-1';
                fieldDiv.style.paddingLeft = (depth * 15) + 'px';

                if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    const headerDiv = document.createElement('div');
                    headerDiv.className = 'd-flex align-items-center gap-2';
                    headerDiv.style.cssText = 'cursor:pointer;user-select:none;padding:0.25rem 0;';

                    const toggleBtn = document.createElement('i');
                    toggleBtn.className = 'fas fa-chevron-right';
                    toggleBtn.style.cssText = 'font-size:11px;color:#666;min-width:12px;text-align:center;';

                    const keyLabel = document.createElement('label');
                    keyLabel.className = 'form-label mb-0';
                    keyLabel.style.cssText = `font-weight:${depth === 0 ? '600' : 'normal'};font-size:${depth === 0 ? '13px' : '12px'};cursor:pointer;`;
                    keyLabel.textContent = key;

                    headerDiv.appendChild(toggleBtn);
                    headerDiv.appendChild(keyLabel);
                    fieldDiv.appendChild(headerDiv);

                    const contentDiv = document.createElement('div');
                    contentDiv.style.cssText = 'display:none;border-left:1px solid #dee2e6;margin-left:6px;padding-left:10px;margin-top:0.25rem;';
                    contentDiv.appendChild(buildNestedForm(value, `${parentKey}${key}.`, depth + 1));
                    fieldDiv.appendChild(contentDiv);

                    headerDiv.addEventListener('click', () => {
                        const isHidden = contentDiv.style.display === 'none';
                        contentDiv.style.display = isHidden ? 'block' : 'none';
                        toggleBtn.className = isHidden ? 'fas fa-chevron-down' : 'fas fa-chevron-right';
                        toggleBtn.style.color = isHidden ? '#0d6efd' : '#666';
                    });
                } else {
                    const labelDiv = document.createElement('div');
                    labelDiv.className = 'mb-1';
                    const keyLabel = document.createElement('label');
                    keyLabel.className = 'form-label mb-1';
                    keyLabel.style.cssText = 'font-size:12px;font-weight:500;';
                    keyLabel.textContent = key;
                    labelDiv.appendChild(keyLabel);
                    fieldDiv.appendChild(labelDiv);

                    const textarea = document.createElement('textarea');
                    textarea.className = 'form-control form-control-sm';
                    textarea.style.cssText = "font-family:'Courier New',monospace;font-size:11px;";
                    if (Array.isArray(value)) {
                        textarea.rows = 2;
                        textarea.style.whiteSpace = 'pre';
                        textarea.value = JSON.stringify(value, null, 2);
                    } else {
                        textarea.rows = (typeof value === 'string' && value.length > 50) ? 2 : 1;
                        textarea.value = value === null ? 'null' : String(value);
                    }
                    textarea.dataset.jsonPath = `${parentKey}${key}`;
                    fieldDiv.appendChild(textarea);
                }

                wrapper.appendChild(fieldDiv);
            });
            return wrapper;
        }

        Object.entries(jsonData).forEach(([colKey, colValue]) => {
            const section = document.createElement('div');
            section.className = 'mb-4 p-3 rounded';
            section.style.cssText = 'background-color:#f8f9fa;border:1px solid #dee2e6;';
            const header = document.createElement('h6');
            header.className = 'mb-3';
            header.style.cssText = 'font-weight:bold;color:#212529;';
            header.textContent = colKey;
            section.appendChild(header);
            section.appendChild(buildNestedForm(colValue, `${colKey}.`, 0));
            container.appendChild(section);
        });

        showAlert(`Loaded: ${fileName}`, 'info');
    }

    function showAlert(message, type = 'info') {
        const icons = { success: 'check-circle', danger: 'exclamation-circle', warning: 'exclamation-triangle', info: 'info-circle' };
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `<i class="fas fa-${icons[type] || 'info-circle'} me-2"></i>${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        alertContainer.appendChild(alert);
        if (type !== 'danger') setTimeout(() => { if (alert.parentNode) alert.remove(); }, 5000);
    }
});
