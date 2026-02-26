/**
 * Biometrics Conversion Module
 * Handles biometrics file conversion, preview, and validation
 * Follows the initialization-from-hub pattern
 */

export function initBiometrics(elements) {
    // Destructure elements passed from converter.js
    const {
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
        appendLog,
        displayValidationResults,
        downloadBase64Zip,
        registerSessionInProject,
        getBiometricsSessionValue
    } = elements;

    // Local state for biometrics module
    let currentBiometricsZipBlob = null;

    // ===== UI RESET FUNCTIONS =====

    function resetBiometricsUI() {
        biometricsLogContainer.classList.add('d-none');
        biometricsValidationResultsContainer.classList.add('d-none');
        biometricsDownloadSection.classList.add('d-none');
        biometricsDownloadWarningSection.classList.add('d-none');
        biometricsDetectedContainer.classList.add('d-none');
        biometricsLog.innerHTML = '';
        biometricsValidationSummary.innerHTML = '';
        biometricsValidationDetails.innerHTML = '';
        biometricsDetectedList.innerHTML = '';
        currentBiometricsZipBlob = null;
    }

    function updateBiometricsBtn() {
        const hasFile = biometricsDataFile && biometricsDataFile.files && biometricsDataFile.files.length === 1;
        if (biometricsPreviewBtn) biometricsPreviewBtn.disabled = !hasFile;
        if (biometricsConvertBtn) biometricsConvertBtn.disabled = !hasFile;
        clearBiometricsDataFileBtn?.classList.toggle('d-none', !hasFile);
    }

    // ===== DOWNLOAD FUNCTION =====

    function downloadCurrentBiometricsZip() {
        if (!currentBiometricsZipBlob) return;
        const url = window.URL.createObjectURL(currentBiometricsZipBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prism_biometrics_dataset.zip';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    }

    // ===== FILE UPLOAD HANDLERS =====

    if (biometricsDataFile) {
        biometricsDataFile.addEventListener('change', updateBiometricsBtn);
        updateBiometricsBtn();
    }

    clearBiometricsDataFileBtn?.addEventListener('click', function() {
        if (biometricsDataFile) {
            biometricsDataFile.value = '';
            biometricsDataFile.dispatchEvent(new Event('change', { bubbles: true }));
        }
        biometricsError.classList.add('d-none');
        biometricsError.textContent = '';
        biometricsInfo.classList.add('d-none');
        biometricsInfo.textContent = '';
        resetBiometricsUI();
    });

    // ===== DOWNLOAD BUTTONS =====

    if (biometricsDownloadZipBtn) {
        biometricsDownloadZipBtn.addEventListener('click', downloadCurrentBiometricsZip);
    }
    if (biometricsDownloadZipWarningBtn) {
        biometricsDownloadZipWarningBtn.addEventListener('click', downloadCurrentBiometricsZip);
    }

    // ===== PREVIEW / DRY-RUN HANDLER =====

    if (biometricsPreviewBtn) {
        biometricsPreviewBtn.addEventListener('click', function() {
            biometricsError.classList.add('d-none');
            biometricsInfo.classList.add('d-none');
            biometricsError.textContent = '';
            biometricsInfo.textContent = '';
            resetBiometricsUI();

            const sessionVal = getBiometricsSessionValue();
            if (!sessionVal) {
                biometricsError.textContent = 'Please enter a session ID (e.g., 1, 2, 3).';
                biometricsError.classList.remove('d-none');
                (biometricsSessionCustom || biometricsSessionSelect)?.focus();
                return;
            }

            const file = biometricsDataFile.files && biometricsDataFile.files[0];
            if (!file) return;

            // Show log container
            biometricsLogContainer.classList.remove('d-none');
            biometricsLogBody.classList.remove('d-none');
            const icon = toggleBiometricsLogBtn.querySelector('i');
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');

            appendLog('🔍 PREVIEW MODE (Dry-Run)', 'info', biometricsLog);
            appendLog('═════════════════════════════════════', 'info', biometricsLog);
            appendLog(`Analyzing file: ${file.name}`, 'step', biometricsLog);
            appendLog('No files will be created.', 'info', biometricsLog);
            appendLog('', 'info', biometricsLog);

            const formData = new FormData();
            formData.append('data', file);
            formData.append('sheet', '0');
            formData.append('session', sessionVal);
            formData.append('dry_run', 'true');
            formData.append('validate', 'true');

            biometricsPreviewBtn.disabled = true;
            biometricsConvertBtn.disabled = true;

            console.log('[Biometrics Preview] About to fetch /api/biometrics-convert');
            console.log('[Biometrics Preview] FormData entries:');
            for (let [key, value] of formData.entries()) {
                console.log(`  ${key}: ${value instanceof File ? value.name : value}`);
            }

            fetch('/api/biometrics-convert', {
                method: 'POST',
                body: formData,
            })
            .then(async response => {
                console.log('[Biometrics Preview] Fetch completed, status:', response.status);
                const data = await response.json();
                
                console.log('[Biometrics Preview] Response received:', data);
                console.log('[Biometrics Preview] Response OK:', response.ok);
                console.log('[Biometrics Preview] Log entries:', data.log ? data.log.length : 0);
                
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
            biometricsError.classList.add('d-none');
            biometricsInfo.classList.add('d-none');
            biometricsError.textContent = '';
            biometricsInfo.textContent = '';
            resetBiometricsUI();

            const sessionVal = getBiometricsSessionValue();
            if (!sessionVal) {
                biometricsError.textContent = 'Please enter a session ID (e.g., 1, 2, 3).';
                biometricsError.classList.remove('d-none');
                (biometricsSessionCustom || biometricsSessionSelect)?.focus();
                return;
            }

            const file = biometricsDataFile.files && biometricsDataFile.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('data', file);
            // Library path is now resolved automatically (project first, then global)
            formData.append('sheet', '0');

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

            biometricsError.classList.add('d-none');
            biometricsInfo.classList.add('d-none');
            
            // Show log container
            biometricsLogContainer.classList.remove('d-none');
            biometricsLogBody.classList.remove('d-none');
            const icon = toggleBiometricsLogBtn.querySelector('i');
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-down');

            const file = biometricsDataFile.files && biometricsDataFile.files[0];

            appendLog(`Starting conversion of: ${file.name}`, 'info', biometricsLog);
            appendLog(`Using library: auto-resolved (project or global)`, 'step', biometricsLog);
            const formData = new FormData();
            formData.append('data', file);
            // Library path is now resolved automatically (project first, then global)

            const sessionVal = getBiometricsSessionValue();
            formData.append('session', sessionVal);
            appendLog(`Forcing session ID: ${sessionVal}`, 'step', biometricsLog);

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

                if (data.zip_base64) {
                    const byteCharacters = atob(data.zip_base64);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);
                    currentBiometricsZipBlob = new Blob([byteArray], {type: 'application/zip'});

                    appendLog('Conversion complete. Click the download button below.', 'success', biometricsLog);
                }

                // Register biometrics conversion in project.json
                const bioSessionVal = getBiometricsSessionValue();
                if (bioSessionVal && selectedTasks && selectedTasks.length) {
                    const bioFile = biometricsDataFile.files?.[0]?.name || '';
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
