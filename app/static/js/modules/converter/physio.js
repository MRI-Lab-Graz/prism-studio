/**
 * Physio Conversion Module
 * Handles batch physio file conversion
 * Supports auto-detection of sourcedata/physio folder
 * Follows the initialization-from-hub pattern
 */

import { pollJobStatus } from '../../shared/job-polling.js';

export function initPhysio(elements) {
    const STATUS_POLL_INTERVAL_MS = 500;
    const STATUS_POLL_TIMEOUT_MS = 5 * 60 * 1000;
    const MAX_STATUS_POLL_ERRORS = 4;

    // Destructure elements passed from converter-bootstrap.js
    const {
        // Batch mode
        physioBatchFiles,
        clearPhysioBatchFilesBtn,
        physioBatchFolder,
        clearPhysioBatchFolderBtn,
        physioBatchSamplingRate,
        physioGenerateReports,
        physioBatchDryRun,
        physioBatchPreviewBtn,
        physioBatchConvertBtn,
        physioBatchCancelBtn,
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

        if (physioBatchPreviewBtn) {
            physioBatchPreviewBtn.disabled = !shouldEnable;
        }
        if (physioBatchConvertBtn) {
            physioBatchConvertBtn.disabled = !shouldEnable;
            console.log('[Physio] Button update - hasFiles:', hasFiles, 'hasFolder:', hasFolder, 'hasAutoPath:', hasAutoPath, 'disabled:', !shouldEnable);
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
    
    if (physioBatchLogClearBtn) {
        physioBatchLogClearBtn.addEventListener('click', () => {
            if (physioBatchLog) physioBatchLog.textContent = '';
        });
    }

    async function runPhysioBatchConversion(dryRunMode) {
            console.log('[Physio] Convert button clicked');
            physioBatchError.classList.add('d-none');
            physioBatchInfo.classList.add('d-none');
            physioBatchProgress.classList.remove('d-none');
            physioBatchLogContainer.classList.remove('d-none');
            physioBatchLog.textContent = '';
            if (physioBatchPreviewBtn) physioBatchPreviewBtn.disabled = true;
            if (physioBatchConvertBtn) physioBatchConvertBtn.disabled = true;
            if (physioBatchCancelBtn) {
                physioBatchCancelBtn.classList.remove('d-none');
                physioBatchCancelBtn.disabled = false;
            }

            const progressBar = physioBatchProgress ? physioBatchProgress.querySelector('.progress-bar') : null;
            const startedAt = Date.now();
            const sourceLabel = (physioBatchFolderPath && physioBatchFolderPath.value)
                ? 'auto-detected sourcedata/physio'
                : ((physioBatchFolder && physioBatchFolder.files && physioBatchFolder.files.length > 0)
                    ? 'selected folder'
                    : 'selected files');

            const writeLocalLog = (message, cssClass = 'ansi-blue') => {
                const escaped = String(message)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                if (physioBatchLog.innerHTML) {
                    physioBatchLog.innerHTML += '<br>';
                }
                physioBatchLog.innerHTML += `<span class="${cssClass}">${escaped}</span>`;
                physioBatchLog.scrollTop = physioBatchLog.scrollHeight;
            };

            writeLocalLog(`⏳ Conversion started (${dryRunMode ? 'Preview / Dry-Run' : 'Convert'})`, 'ansi-cyan');
            writeLocalLog(`📂 Source: ${sourceLabel}`, 'ansi-blue');

            let progressTimer = null;
            if (progressBar) {
                progressTimer = window.setInterval(() => {
                    const elapsedSec = Math.floor((Date.now() - startedAt) / 1000);
                    progressBar.textContent = `Converting... ${elapsedSec}s`;
                }, 1000);
            }

            if (physioBatchDryRun) {
                physioBatchDryRun.checked = dryRunMode;
            }

            const filesFromInput = Array.from(physioBatchFiles.files || []);
            const filesFromFolder = Array.from(physioBatchFolder.files || []);
            const autoDetectedPath = physioBatchFolderPath ? physioBatchFolderPath.value : null;
            
            console.log('[Physio] Files from input:', filesFromInput.length, 'Files from folder:', filesFromFolder.length, 'Auto-detected path:', autoDetectedPath);
            
            const samplingRate = physioBatchSamplingRate ? physioBatchSamplingRate.value.trim() : '';
            const isDryRun = dryRunMode;

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
            formData.append('dest_root', 'prism');     // Save to project root
            formData.append('generate_physio_reports', (physioGenerateReports && physioGenerateReports.checked) ? 'true' : 'false');
            if (samplingRate) {
                formData.append('sampling_rate', samplingRate);
            }
            formData.append('dry_run', isDryRun ? 'true' : 'false');

            try {
                const response = await fetch('/api/batch-convert-start', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data && data.error ? data.error : 'Batch conversion failed');
                }

                const startData = await response.json();
                const jobId = startData && startData.job_id;
                if (!jobId) {
                    throw new Error('Batch conversion did not return a job id');
                }

                let cancelRequested = false;
                const cancelHandler = async () => {
                    if (cancelRequested) return;
                    cancelRequested = true;
                    if (physioBatchCancelBtn) {
                        physioBatchCancelBtn.disabled = true;
                        physioBatchCancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Cancelling...';
                    }
                    try {
                        const cancelResponse = await fetch(`/api/batch-convert-cancel/${encodeURIComponent(jobId)}`, {
                            method: 'POST'
                        });
                        const cancelData = await cancelResponse.json().catch(() => ({}));
                        if (!cancelResponse.ok) {
                            throw new Error(cancelData.error || 'Failed to cancel conversion');
                        }
                        writeLocalLog('⏹️ Cancellation requested. Waiting for cleanup...', 'ansi-yellow');
                    } catch (cancelError) {
                        physioBatchError.textContent = cancelError.message;
                        physioBatchError.classList.remove('d-none');
                        if (physioBatchCancelBtn) {
                            physioBatchCancelBtn.disabled = false;
                            physioBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                        }
                        cancelRequested = false;
                    }
                };

                if (physioBatchCancelBtn) {
                    physioBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    physioBatchCancelBtn.onclick = cancelHandler;
                }

                const statusData = await pollJobStatus({
                    fetchStatus: async (cursor) => {
                        const statusResponse = await fetch(`/api/batch-convert-status/${encodeURIComponent(jobId)}?cursor=${cursor}`);
                        if (!statusResponse.ok) {
                            const statusErr = await statusResponse.json().catch(() => null);
                            throw new Error(statusErr && statusErr.error ? statusErr.error : 'Failed to retrieve conversion status');
                        }
                        return statusResponse.json();
                    },
                    onLogs: (newLogs) => {
                        for (const log of newLogs) {
                            let colorClass = 'ansi-reset';
                            if (log.level === 'error') colorClass = 'ansi-red';
                            else if (log.level === 'warning') colorClass = 'ansi-yellow';
                            else if (log.level === 'success') colorClass = 'ansi-green';
                            else if (log.level === 'info') colorClass = 'ansi-blue';
                            else if (log.level === 'preview') colorClass = 'ansi-cyan';

                            const escaped = String(log.message)
                                .replace(/&/g, '&amp;')
                                .replace(/</g, '&lt;')
                                .replace(/>/g, '&gt;');
                            if (physioBatchLog.innerHTML) {
                                physioBatchLog.innerHTML += '<br>';
                            }
                            physioBatchLog.innerHTML += `<span class="${colorClass}">${escaped}</span>`;
                        }
                        if (newLogs.length > 0) {
                            physioBatchLog.scrollTop = physioBatchLog.scrollHeight;
                        }
                    },
                    onRetryWarning: ({ attempt, maxAttempts, error }) => {
                        writeLocalLog(
                            `⚠️ Status check failed (${attempt}/${maxAttempts}): ${error.message || error}`,
                            'ansi-yellow',
                        );
                    },
                    intervalMs: STATUS_POLL_INTERVAL_MS,
                    timeoutMs: STATUS_POLL_TIMEOUT_MS,
                    maxConsecutiveErrors: MAX_STATUS_POLL_ERRORS,
                    timeoutErrorMessage: 'Physio conversion status timed out after 5 minutes. Please review logs and retry.',
                    statusFailureMessage: 'Failed to retrieve conversion status after multiple attempts.',
                    getFailureError: (nextStatusData) => nextStatusData.error || 'Batch conversion failed',
                });

                const result = statusData.result || {};

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
                if (err.message === 'Cancelled by user' || err.message === 'Conversion cancelled by user') {
                    physioBatchInfo.textContent = 'Conversion cancelled. Temporary staged output was cleaned up and nothing was copied into the project.';
                    physioBatchInfo.classList.remove('d-none');
                } else {
                    physioBatchError.textContent = err.message;
                    physioBatchError.classList.remove('d-none');
                }
            } finally {
                if (progressTimer) {
                    window.clearInterval(progressTimer);
                }
                if (progressBar) {
                    progressBar.textContent = 'Converting...';
                }
                physioBatchProgress.classList.add('d-none');
                if (physioBatchCancelBtn) {
                    physioBatchCancelBtn.classList.add('d-none');
                    physioBatchCancelBtn.disabled = false;
                    physioBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    physioBatchCancelBtn.onclick = null;
                }
                updatePhysioBatchBtn();
            }
    }

    if (physioBatchPreviewBtn) {
        physioBatchPreviewBtn.addEventListener('click', async function() {
            await runPhysioBatchConversion(true);
        });
    }

    if (physioBatchConvertBtn) {
        physioBatchConvertBtn.addEventListener('click', async function() {
            await runPhysioBatchConversion(false);
        });
    }
}
