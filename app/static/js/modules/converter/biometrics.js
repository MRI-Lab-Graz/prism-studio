/**
 * Biometrics Conversion Module
 * Handles biometrics file conversion, preview, and validation
 * Follows the initialization-from-hub pattern
 */

import { resolveCurrentProjectPath } from '../../shared/project-state.js';

export function initBiometrics(elements) {
    // Destructure elements passed from converter-bootstrap.js
    const {
        biometricsDataFile,
        browseServerBiometricsFileBtn,
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
        biometricsDetectedContainer,
        biometricsDetectedList,
        biometricsConfirmBtn,
        biometricsSelectAll,
        biometricsSessionSelect,
        biometricsSessionCustom,
        appendLog,
        displayValidationResults,
        registerSessionInProject,
        getBiometricsSessionValue
    } = elements;

    let biometricsServerFilePath = '';

    function prefersServerPicker() {
        return Boolean(
            window.PrismFileSystemMode
            && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
            && window.PrismFileSystemMode.prefersServerPicker()
        );
    }

    function getSelectedBiometricsFile() {
        return (biometricsDataFile && biometricsDataFile.files && biometricsDataFile.files[0])
            ? biometricsDataFile.files[0]
            : null;
    }

    function getSelectedBiometricsFilename() {
        const selectedFile = getSelectedBiometricsFile();
        if (selectedFile && selectedFile.name) {
            return selectedFile.name;
        }
        if (biometricsServerFilePath) {
            const tokens = biometricsServerFilePath.split('/');
            return tokens[tokens.length - 1] || biometricsServerFilePath;
        }
        return '';
    }

    function hasSelectedBiometricsInput() {
        return Boolean(getSelectedBiometricsFile() || biometricsServerFilePath);
    }

    function appendBiometricsInputToFormData(formData) {
        const selectedFile = getSelectedBiometricsFile();
        if (selectedFile) {
            formData.append('data', selectedFile);
            return selectedFile;
        }
        if (biometricsServerFilePath) {
            formData.append('source_file_path', biometricsServerFilePath);
        }
        return null;
    }

    async function pickServerBiometricsFile() {
        if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFile === 'function')) {
            return '';
        }

        return window.PrismFileSystemMode.pickFile({
            title: 'Select Biometrics File on Server',
            confirmLabel: 'Use This File',
            extensions: '.xlsx,.csv,.tsv',
            startPath: biometricsServerFilePath || ''
        });
    }

    function applyBiometricsPickerUiState() {
        const connectedToServer = prefersServerPicker();

        if (browseServerBiometricsFileBtn) {
            browseServerBiometricsFileBtn.classList.toggle('d-none', !connectedToServer);
        }

        if (biometricsDataFile) {
            biometricsDataFile.disabled = connectedToServer;
            biometricsDataFile.title = connectedToServer ? 'Connected-to-server mode: use Server picker.' : '';
            if (connectedToServer && biometricsDataFile.files && biometricsDataFile.files.length > 0) {
                biometricsDataFile.value = '';
            }
        }

        if (!connectedToServer && biometricsServerFilePath) {
            biometricsServerFilePath = '';
            resetBiometricsWorkflowState();
        }

        updateBiometricsBtn();
    }

    // ===== UI RESET FUNCTIONS =====

    function resetBiometricsUI() {
        biometricsLogContainer.classList.add('d-none');
        biometricsValidationResultsContainer.classList.add('d-none');
        biometricsDetectedContainer.classList.add('d-none');
        biometricsLog.innerHTML = '';
        biometricsValidationSummary.innerHTML = '';
        biometricsValidationDetails.innerHTML = '';
        biometricsDetectedList.innerHTML = '';
    }

    function clearBiometricsMessages() {
        biometricsError.classList.add('d-none');
        biometricsInfo.classList.add('d-none');
        biometricsError.textContent = '';
        biometricsInfo.textContent = '';
    }

    function resetBiometricsWorkflowState() {
        clearBiometricsMessages();
        resetBiometricsUI();
        if (biometricsSelectAll) {
            biometricsSelectAll.checked = true;
        }
    }

    function updateBiometricsBtn() {
        const hasFile = hasSelectedBiometricsInput();
        if (biometricsPreviewBtn) biometricsPreviewBtn.disabled = !hasFile;
        if (biometricsConvertBtn) biometricsConvertBtn.disabled = !hasFile;
        clearBiometricsDataFileBtn?.classList.toggle('d-none', !hasFile);
    }

    function getProjectSaveSummary(data) {
        const outputPaths = Array.isArray(data && data.project_output_paths)
            ? data.project_output_paths.filter((value) => typeof value === 'string' && value.trim())
            : [];
        const target = (data && (data.project_output_path || outputPaths[0] || data.project_output_root)) || 'the active project';
        const outputCount = Number.isFinite(data && data.project_output_count)
            ? data.project_output_count
            : outputPaths.length;
        const countNote = outputCount > 1 ? ` (${outputCount} files)` : '';

        return { target, countNote };
    }

    // ===== FILE UPLOAD HANDLERS =====

    if (biometricsDataFile) {
        biometricsDataFile.addEventListener('change', function() {
            biometricsServerFilePath = '';
            resetBiometricsWorkflowState();
            updateBiometricsBtn();
        });
        updateBiometricsBtn();
    }

    if (browseServerBiometricsFileBtn) {
        browseServerBiometricsFileBtn.addEventListener('click', async function() {
            const pickedPath = await pickServerBiometricsFile();
            if (!pickedPath) return;

            biometricsServerFilePath = pickedPath;
            if (biometricsDataFile) {
                biometricsDataFile.value = '';
            }

            resetBiometricsWorkflowState();
            updateBiometricsBtn();
        });
    }

    clearBiometricsDataFileBtn?.addEventListener('click', function() {
        biometricsServerFilePath = '';
        if (biometricsDataFile) {
            biometricsDataFile.value = '';
            biometricsDataFile.dispatchEvent(new Event('change', { bubbles: true }));
        }
        resetBiometricsWorkflowState();
    });

    window.addEventListener('prism-project-changed', function() {
        resetBiometricsWorkflowState();
        updateBiometricsBtn();
    });

    window.addEventListener('prism-library-settings-changed', function() {
        applyBiometricsPickerUiState();
    });

    if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
        window.PrismFileSystemMode.init().then(() => {
            applyBiometricsPickerUiState();
        }).catch(() => {
            // Keep host picker behavior on init failure.
        });
    }

    applyBiometricsPickerUiState();

    // ===== PREVIEW / DRY-RUN HANDLER =====

    if (biometricsPreviewBtn) {
        biometricsPreviewBtn.addEventListener('click', function() {
            resetBiometricsWorkflowState();

            const sessionVal = getBiometricsSessionValue();
            if (!sessionVal) {
                biometricsError.textContent = 'Please enter a session ID (e.g., 1, 2, 3).';
                biometricsError.classList.remove('d-none');
                (biometricsSessionCustom || biometricsSessionSelect)?.focus();
                return;
            }

            if (!hasSelectedBiometricsInput()) return;
            const selectedFilename = getSelectedBiometricsFilename();

            // Show log container
            biometricsLogContainer.classList.remove('d-none');
            biometricsLogBody.classList.remove('d-none');
            const icon = toggleBiometricsLogBtn.querySelector('i');
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');

            appendLog('🔍 PREVIEW MODE (Dry-Run)', 'info', biometricsLog);
            appendLog('═════════════════════════════════════', 'info', biometricsLog);
            appendLog(`Analyzing file: ${selectedFilename}`, 'step', biometricsLog);
            appendLog('No files will be created.', 'info', biometricsLog);
            appendLog('', 'info', biometricsLog);

            const formData = new FormData();
            appendBiometricsInputToFormData(formData);
            formData.append('sheet', '0');
            formData.append('session', sessionVal);
            formData.append('dry_run', 'true');
            formData.append('validate', 'true');
            const currentProjectPath = resolveCurrentProjectPath();
            if (currentProjectPath) {
                formData.append('project_path', currentProjectPath);
            }

            biometricsPreviewBtn.disabled = true;
            biometricsConvertBtn.disabled = true;

            fetch('/api/biometrics-convert', {
                method: 'POST',
                body: formData,
            })
            .then(async response => {
                const data = await response.json();

                if (data.log && Array.isArray(data.log)) {
                    data.log.forEach(entry => {
                        appendLog(entry.message, entry.type || entry.level || 'info', biometricsLog);
                    });
                }

                if (!response.ok) {
                    throw new Error(data.error || 'Preview failed');
                }
                return data;
            })
            .then(data => {
                if (data.validation) {
                    const v = data.validation;
                    const errorCount = (v.errors || []).length;
                    const warningCount = (v.warnings || []).length;
                    
                    if (errorCount === 0 && warningCount === 0) {
                        appendLog('✓ Validation passed - dataset structure is valid!', 'success', biometricsLog);
                    } else if (errorCount === 0) {
                        appendLog(`⚠ Validation passed with ${warningCount} warning(s)`, 'warning', biometricsLog);
                    } else {
                        appendLog(`✗ Validation failed with ${errorCount} error(s)`, 'error', biometricsLog);
                    }
                    
                    displayValidationResults(data.validation, 'biometrics');
                }
                appendLog('', 'info', biometricsLog);
                appendLog('Preview complete. Check validation results above.', 'info', biometricsLog);
            })
            .catch(err => {
                appendLog(`Error: ${err.message}`, 'error', biometricsLog);
                biometricsError.textContent = err.message;
                biometricsError.classList.remove('d-none');
            })
            .finally(() => {
                biometricsPreviewBtn.disabled = false;
                biometricsConvertBtn.disabled = false;
            });
        });
    }

    // ===== DETECTION & TASK SELECTION HANDLER =====

    if (biometricsConvertBtn) {
        biometricsConvertBtn.addEventListener('click', function() {
            resetBiometricsWorkflowState();

            const sessionVal = getBiometricsSessionValue();
            if (!sessionVal) {
                biometricsError.textContent = 'Please enter a session ID (e.g., 1, 2, 3).';
                biometricsError.classList.remove('d-none');
                (biometricsSessionCustom || biometricsSessionSelect)?.focus();
                return;
            }

            if (!hasSelectedBiometricsInput()) return;

            const formData = new FormData();
            appendBiometricsInputToFormData(formData);
            // Library path is now resolved automatically (project first, then global)
            formData.append('sheet', '0');
            const currentProjectPath = resolveCurrentProjectPath();
            if (currentProjectPath) {
                formData.append('project_path', currentProjectPath);
            }

            biometricsConvertBtn.disabled = true;
            biometricsInfo.textContent = 'Analyzing file...';
            biometricsInfo.classList.remove('d-none');

            fetch('/api/biometrics-detect', {
                method: 'POST',
                body: formData,
            })
            .then(async response => {
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data && data.error ? data.error : 'Detection failed');
                }
                return response.json();
            })
            .then(data => {
                biometricsInfo.classList.add('d-none');
                if (!data.tasks || data.tasks.length === 0) {
                    biometricsError.textContent = 'No biometrics tasks detected in the file. Please check your templates and column names.';
                    biometricsError.classList.remove('d-none');
                    return;
                }

                // Show detected tasks
                biometricsDetectedContainer.classList.remove('d-none');
                biometricsDetectedList.innerHTML = '';
                data.tasks.forEach(task => {
                    const col = document.createElement('div');
                    col.className = 'col-md-4';
                    col.innerHTML = `
                        <div class="form-check">
                            <input class="form-check-input biometrics-task-check" type="checkbox" value="${task}" id="task_${task}" checked>
                            <label class="form-check-label small" for="task_${task}">
                                ${task}
                            </label>
                        </div>
                    `;
                    biometricsDetectedList.appendChild(col);
                });
            })
            .catch(err => {
                biometricsError.textContent = err.message;
                biometricsError.classList.remove('d-none');
            })
            .finally(() => {
                biometricsConvertBtn.disabled = false;
            });
        });
    }

    // ===== SELECT ALL TASKS HANDLER =====

    if (biometricsSelectAll) {
        biometricsSelectAll.addEventListener('change', function() {
            const checks = document.querySelectorAll('.biometrics-task-check');
            checks.forEach(c => c.checked = biometricsSelectAll.checked);
        });
    }

    // ===== CONFIRM & CONVERT HANDLER =====

    if (biometricsConfirmBtn) {
        biometricsConfirmBtn.addEventListener('click', function() {
            const selectedTasks = Array.from(document.querySelectorAll('.biometrics-task-check:checked')).map(c => c.value);
            if (selectedTasks.length === 0) {
                alert('Please select at least one task to export.');
                return;
            }

            clearBiometricsMessages();
            
            // Show log container
            biometricsLogContainer.classList.remove('d-none');
            biometricsLogBody.classList.remove('d-none');
            const icon = toggleBiometricsLogBtn.querySelector('i');
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');

            const selectedFilename = getSelectedBiometricsFilename();
            if (!selectedFilename) return;

            appendLog(`Starting conversion of: ${selectedFilename}`, 'info', biometricsLog);
            appendLog(`Using library: auto-resolved (project or global)`, 'step', biometricsLog);
            const formData = new FormData();
            appendBiometricsInputToFormData(formData);
            // Library path is now resolved automatically (project first, then global)

            const sessionVal = getBiometricsSessionValue();
            formData.append('session', sessionVal);
            appendLog(`Forcing session ID: ${sessionVal}`, 'step', biometricsLog);

            const currentProjectPath = resolveCurrentProjectPath();
            if (!currentProjectPath) {
                biometricsError.textContent = 'Please select a project first from the top of the page';
                biometricsError.classList.remove('d-none');
                return;
            }
            formData.append('project_path', currentProjectPath);

            formData.append('save_to_project', 'true');
            appendLog('Output will be saved under the active project', 'step', biometricsLog);
            formData.append('validate', 'true');
            selectedTasks.forEach(t => formData.append('tasks[]', t));

            biometricsConfirmBtn.disabled = true;
            appendLog('Uploading file and starting conversion...', 'info', biometricsLog);

            fetch('/api/biometrics-convert', {
                method: 'POST',
                body: formData,
            })
            .then(async response => {
                const data = await response.json();
                
                // Process logs even if response is not ok
                if (data.log && Array.isArray(data.log)) {
                    data.log.forEach(entry => {
                        appendLog(entry.message, entry.type || entry.level || 'info', biometricsLog);
                    });
                }

                if (!response.ok) {
                    throw new Error(data.error || 'Conversion failed');
                }
                return data;
            })
            .then(data => {
                // Logs already processed above
                if (data.validation) {
                    const v = data.validation;
                    const errorCount = (v.errors || []).length;
                    const warningCount = (v.warnings || []).length;
                    
                    if (errorCount === 0 && warningCount === 0) {
                        appendLog('✓ Validation passed - dataset is valid!', 'success', biometricsLog);
                    } else if (errorCount === 0) {
                        appendLog(`⚠ Validation passed with ${warningCount} warning(s)`, 'warning', biometricsLog);
                    } else {
                        appendLog(`✗ Validation failed with ${errorCount} error(s)`, 'error', biometricsLog);
                    }
                    
                    displayValidationResults(data.validation, 'biometrics');
                }

                if (data.project_saved) {
                    const saveSummary = getProjectSaveSummary(data);
                    appendLog(`✓ Data saved to project: ${saveSummary.target}${saveSummary.countNote}`, 'success', biometricsLog);
                    biometricsInfo.textContent = `Conversion complete. First saved path: ${saveSummary.target}${saveSummary.countNote}`;
                } else {
                    appendLog('⚠ Conversion finished, but nothing was copied into the project.', 'warning', biometricsLog);
                    biometricsInfo.textContent = 'Conversion finished, but nothing was copied into the project. Review the conversion log.';
                }
                biometricsInfo.classList.remove('d-none');

                // Register biometrics conversion in project.json
                const bioSessionVal = getBiometricsSessionValue();
                if (data.project_saved && bioSessionVal && selectedTasks && selectedTasks.length) {
                    const bioFile = getSelectedBiometricsFilename();
                    registerSessionInProject(bioSessionVal, selectedTasks, 'biometrics', bioFile, 'biometrics');
                }
            })
            .catch(err => {
                appendLog(`Error: ${err.message}`, 'error', biometricsLog);
                biometricsError.textContent = err.message;
                biometricsError.classList.remove('d-none');
            })
            .finally(() => {
                biometricsConfirmBtn.disabled = false;
            });
        });
    }
}
