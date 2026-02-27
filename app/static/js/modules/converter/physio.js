/**
 * Physio Conversion Module
 * Handles single and batch physio file conversion
 * Supports auto-detection of sourcedata/physio folder
 * Follows the initialization-from-hub pattern
 */

export function initPhysio(elements) {
    // Destructure elements passed from converter-bootstrap.js
    const {
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
        // Shared from converter
        appendLog
    } = elements;

    // ===== SINGLE FILE CONVERSION =====

    function updatePhysioBtn() {
        const hasFile = physioRawFile && physioRawFile.files && physioRawFile.files.length === 1;
        if (physioConvertBtn) physioConvertBtn.disabled = !hasFile;
    }

    if (physioRawFile) {
        physioRawFile.addEventListener('change', updatePhysioBtn);
        updatePhysioBtn();
    }

    if (physioConvertBtn) {
        physioConvertBtn.addEventListener('click', function() {
            physioError.classList.add('d-none');
            physioInfo.classList.add('d-none');
            physioError.textContent = '';
            physioInfo.textContent = '';

            const file = physioRawFile.files && physioRawFile.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('raw', file);
            formData.append('task', physioTask ? physioTask.value.trim() : 'rest');
            if (physioSamplingRate && physioSamplingRate.value) {
                formData.append('sampling_rate', physioSamplingRate.value);
            }

            physioConvertBtn.disabled = true;
            physioInfo.textContent = 'Converting... this may take a moment.';
            physioInfo.classList.remove('d-none');

            fetch('/api/physio-convert', {
                method: 'POST',
                body: formData,
            })
            .then(async response => {
                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    const msg = data && data.error ? data.error : 'Conversion failed';
                    throw new Error(msg);
                }
                const blob = await response.blob();
                return blob;
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'varioport_edfplus.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
                physioInfo.textContent = 'Done. Your ZIP download should start automatically.';
                physioInfo.classList.remove('d-none');
            })
            .catch(err => {
                physioError.textContent = err.message;
                physioError.classList.remove('d-none');
            })
            .finally(() => {
                updatePhysioBtn();
            });
        });
    }

    // ===== BATCH FILE CONVERSION =====

    // Auto-detect sourcedata/physio folder
    if (autoDetectPhysioBtn) {
        autoDetectPhysioBtn.addEventListener('click', async function() {
            try {
                autoDetectPhysioBtn.disabled = true;
                autoDetectPhysioBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Detecting...';
                
                const response = await fetch('/api/check-sourcedata-physio');
                const result = await response.json();
                
                if (result.exists) {
                    // Store the folder path in hidden field for direct use
                    if (physioBatchFolderPath) {
                        physioBatchFolderPath.value = result.path;
                        console.log('[Physio] Auto-detected folder path stored:', result.path);
                    }
                    
                    // Show hint message
                    if (autoDetectHint) {
                        autoDetectHint.innerHTML = `<i class="fas fa-check text-success me-1"></i>${result.message}`;
                    }
                    
                    // Show success info
                    if (physioBatchInfo) {
                        physioBatchInfo.innerHTML = `<i class="fas fa-folder-check me-2 text-success"></i><strong>✅ sourcedata/physio folder auto-selected!</strong> Ready to convert. Click the button below to start.`;
                        physioBatchInfo.classList.remove('d-none');
                    }
                    
                    // Update button state as if folder was selected
                    updatePhysioBatchBtn();
                } else {
                    if (autoDetectHint) {
                        autoDetectHint.innerHTML = `<i class="fas fa-times text-danger me-1"></i>${result.message}`;
                    }
                    if (physioBatchError) {
                        physioBatchError.innerHTML = `<i class="fas fa-exclamation-circle me-2"></i>${result.message}`;
                        physioBatchError.classList.remove('d-none');
                    }
                }
            } catch (error) {
                if (autoDetectHint) {
                    autoDetectHint.innerHTML = `<i class="fas fa-times text-danger me-1"></i>Error: ${error.message}`;
                }
            } finally {
                autoDetectPhysioBtn.disabled = false;
                autoDetectPhysioBtn.innerHTML = '<i class="fas fa-folder-open me-2"></i>Auto-detect';
            }
        });
    }

    function updatePhysioBatchBtn() {
        const hasFiles = physioBatchFiles && physioBatchFiles.files && physioBatchFiles.files.length > 0;
        const hasFolder = physioBatchFolder && physioBatchFolder.files && physioBatchFolder.files.length > 0;
        const hasAutoPath = physioBatchFolderPath && physioBatchFolderPath.value && physioBatchFolderPath.value.length > 0;
        const shouldEnable = hasFiles || hasFolder || hasAutoPath;

        clearPhysioBatchFilesBtn?.classList.toggle('d-none', !hasFiles);
        clearPhysioBatchFolderBtn?.classList.toggle('d-none', !(hasFolder || hasAutoPath));
        
        if (physioBatchConvertBtn) {
            physioBatchConvertBtn.disabled = !shouldEnable;
            console.log('[Physio] Button update - hasFiles:', hasFiles, 'hasFolder:', hasFolder, 'hasAutoPath:', hasAutoPath, 'disabled:', !shouldEnable);
        }
        
        // Update button text based on dry-run mode
        if (physioBatchConvertBtn) {
            const isDryRun = physioBatchDryRun && physioBatchDryRun.checked;
            if (isDryRun) {
                physioBatchConvertBtn.innerHTML = '<i class="fas fa-flask me-2"></i>Preview Conversion';
                physioBatchConvertBtn.classList.remove('btn-warning');
                physioBatchConvertBtn.classList.add('btn-info');
            } else {
                physioBatchConvertBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Convert & Save to Project';
                physioBatchConvertBtn.classList.remove('btn-info');
                physioBatchConvertBtn.classList.add('btn-warning');
            }
        }
    }

    if (physioBatchFiles) {
        physioBatchFiles.addEventListener('change', updatePhysioBatchBtn);
        updatePhysioBatchBtn();
    }

    if (physioBatchFolder) {
        physioBatchFolder.addEventListener('change', updatePhysioBatchBtn);
        updatePhysioBatchBtn();
    }

    clearPhysioBatchFilesBtn?.addEventListener('click', function() {
        if (physioBatchFiles) {
            physioBatchFiles.value = '';
            physioBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
        }
        physioBatchError.classList.add('d-none');
        physioBatchError.textContent = '';
    });

    clearPhysioBatchFolderBtn?.addEventListener('click', function() {
        if (physioBatchFolder) {
            physioBatchFolder.value = '';
            physioBatchFolder.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (physioBatchFolderPath) {
            physioBatchFolderPath.value = '';
        }
        if (autoDetectHint) {
            autoDetectHint.textContent = '';
        }
        physioBatchError.classList.add('d-none');
        physioBatchError.textContent = '';
        physioBatchInfo.classList.add('d-none');
        physioBatchInfo.textContent = '';
        updatePhysioBatchBtn();
    });
    
    if (physioBatchDryRun) {
        physioBatchDryRun.addEventListener('change', updatePhysioBatchBtn);
    }

    if (physioBatchLogClearBtn) {
        physioBatchLogClearBtn.addEventListener('click', () => {
            if (physioBatchLog) physioBatchLog.textContent = '';
        });
    }

    if (physioBatchConvertBtn) {
        physioBatchConvertBtn.addEventListener('click', async function() {
            console.log('[Physio] Convert button clicked');
            physioBatchError.classList.add('d-none');
            physioBatchInfo.classList.add('d-none');
            physioBatchProgress.classList.remove('d-none');
            physioBatchLogContainer.classList.remove('d-none');
            physioBatchLog.textContent = '';
            physioBatchConvertBtn.disabled = true;

            const filesFromInput = Array.from(physioBatchFiles.files || []);
            const filesFromFolder = Array.from(physioBatchFolder.files || []);
            const autoDetectedPath = physioBatchFolderPath ? physioBatchFolderPath.value : null;
            
            console.log('[Physio] Files from input:', filesFromInput.length, 'Files from folder:', filesFromFolder.length, 'Auto-detected path:', autoDetectedPath);
            
            const samplingRate = physioBatchSamplingRate ? (physioBatchSamplingRate.value.trim() || '512') : '512';
            const isDryRun = physioBatchDryRun && physioBatchDryRun.checked;

            const formData = new FormData();
            
            // If we have an auto-detected folder path, use it
            if (autoDetectedPath) {
                console.log('[Physio] Using auto-detected folder path for conversion');
                formData.append('folder_path', autoDetectedPath);
            } else {
                // Use manually selected files
                let allFiles = [...filesFromInput, ...filesFromFolder];
                
                // Filter for .raw and .vpd files only (in case folder contains other files)
                const files = allFiles.filter(f => f.name.toLowerCase().endsWith('.raw') || f.name.toLowerCase().endsWith('.vpd'));
                
                console.log('[Physio] Filtered files:', files.length);
                if (files.length === 0) {
                    physioBatchError.textContent = 'No .raw or .vpd files selected. Please select files or a folder.';
                    physioBatchError.classList.remove('d-none');
                    physioBatchProgress.classList.add('d-none');
                    updatePhysioBatchBtn();
                    return;
                }
                
                // Add files to form data
                files.forEach(f => formData.append('files', f));
            }
            
            formData.append('dataset_name', 'Physio Dataset');  // Default name (not used when saving to project)
            formData.append('modality', 'physio');
            formData.append('save_to_project', isDryRun ? 'false' : 'true');  // Don't save if dry-run
            formData.append('dest_root', 'rawdata');     // Save to rawdata
            formData.append('sampling_rate', samplingRate);
            formData.append('dry_run', isDryRun ? 'true' : 'false');

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
                    physioBatchLog.innerHTML = logLines.join('<br>');
                    physioBatchLog.scrollTop = physioBatchLog.scrollHeight;
                } else if (result.log) {
                    physioBatchLog.textContent = result.log;
                }

                if (isDryRun && result.dry_run) {
                    // Dry-run preview mode
                    let infoMsg = `🧪 DRY-RUN PREVIEW\n\n`;
                    infoMsg += `Files that would be converted: ${result.converted || 0}\n`;
                    infoMsg += `Files with errors: ${result.errors || 0}\n`;
                    infoMsg += `New files would be created: ${result.new_files || 0}\n`;
                    infoMsg += `Files already exist: ${result.existing_files || 0}\n\n`;
                    infoMsg += `✅ Preview completed without errors! Ready to convert for real.`;
                    
                    physioBatchInfo.textContent = infoMsg;
                    physioBatchInfo.classList.remove('d-none');
                    
                    // Change button to "Convert for Real"
                    physioBatchConvertBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Convert for Real';
                    physioBatchConvertBtn.disabled = false;
                    physioBatchConvertBtn.classList.add('btn-success');
                    physioBatchConvertBtn.classList.remove('btn-warning');
                } else {
                    // Actual conversion mode
                    const warnings = result.warnings || [];
                    let infoMsg = `✅ Converted ${result.converted || 0} files to project dataset root. ${result.errors || 0} errors.`;
                    if (warnings.length) {
                        infoMsg += '\n\n⚠️ Warnings:\n' + warnings.join('\n');
                    }
                    
                    physioBatchInfo.textContent = infoMsg;
                    physioBatchInfo.classList.remove('d-none');
                    
                    // Reset dry-run checkbox after successful conversion
                    if (physioBatchDryRun) {
                        physioBatchDryRun.checked = false;
                    }
                }
            } catch (err) {
                physioBatchError.textContent = err.message;
                physioBatchError.classList.remove('d-none');
            } finally {
                physioBatchProgress.classList.add('d-none');
                updatePhysioBatchBtn();
            }
        });
    }
}
