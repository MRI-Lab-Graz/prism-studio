/**
 * Eyetracking Converter Module
 * Handles batch eyetracking conversion
 */

export function initEyetracking(elements) {
    const {
        // Batch convert elements
        eyetrackingBatchFiles,
        clearEyetrackingBatchFilesBtn,
        eyetrackingBatchDatasetName,
        eyetrackingBatchPreviewBtn,
        eyetrackingBatchConvertBtn,
        eyetrackingBatchCancelBtn,
        eyetrackingBatchError,
        eyetrackingBatchInfo,
        eyetrackingBatchProgress,
        eyetrackingBatchLogContainer,
        eyetrackingBatchLog,
        eyetrackingBatchLogClearBtn,
        eyetrackingBatchDryRunCheckbox,
        // Shared functions
        downloadBase64Zip
    } = elements;

    // --- Eyetracking Batch Convert ---
    function updateEyetrackingBatchBtn() {
        const hasFiles = eyetrackingBatchFiles && eyetrackingBatchFiles.files && eyetrackingBatchFiles.files.length > 0;
        clearEyetrackingBatchFilesBtn?.classList.toggle('d-none', !hasFiles);
        if (eyetrackingBatchPreviewBtn) eyetrackingBatchPreviewBtn.disabled = !hasFiles;
        if (eyetrackingBatchConvertBtn) eyetrackingBatchConvertBtn.disabled = !hasFiles;
    }

    if (eyetrackingBatchFiles) {
        eyetrackingBatchFiles.addEventListener('change', updateEyetrackingBatchBtn);
        updateEyetrackingBatchBtn();
    }

    clearEyetrackingBatchFilesBtn?.addEventListener('click', function() {
        if (eyetrackingBatchFiles) {
            eyetrackingBatchFiles.value = '';
            eyetrackingBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
        }
        eyetrackingBatchError.classList.add('d-none');
        eyetrackingBatchError.textContent = '';
        eyetrackingBatchInfo.classList.add('d-none');
        eyetrackingBatchInfo.textContent = '';
    });

    if (eyetrackingBatchLogClearBtn) {
        eyetrackingBatchLogClearBtn.addEventListener('click', () => {
            if (eyetrackingBatchLog) eyetrackingBatchLog.textContent = '';
        });
    }

    async function runEyetrackingBatchConversion(dryRunMode) {
            eyetrackingBatchError.classList.add('d-none');
            eyetrackingBatchInfo.classList.add('d-none');
            eyetrackingBatchProgress.classList.remove('d-none');
            eyetrackingBatchLogContainer.classList.remove('d-none');
            eyetrackingBatchLog.textContent = '';
            if (eyetrackingBatchPreviewBtn) eyetrackingBatchPreviewBtn.disabled = true;
            if (eyetrackingBatchConvertBtn) eyetrackingBatchConvertBtn.disabled = true;

            const files = Array.from(eyetrackingBatchFiles.files);
            const isDryRun = dryRunMode;
            if (eyetrackingBatchDryRunCheckbox) {
                eyetrackingBatchDryRunCheckbox.checked = dryRunMode;
            }

            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            formData.append('modality', 'eyetracking');
            formData.append('dry_run', isDryRun ? 'true' : 'false');
            formData.append('save_to_project', isDryRun ? 'false' : 'true');
            formData.append('dest_root', 'prism');

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
                    if (eyetrackingBatchCancelBtn) {
                        eyetrackingBatchCancelBtn.disabled = true;
                        eyetrackingBatchCancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Cancelling...';
                    }
                    try {
                        await fetch(`/api/batch-convert-cancel/${encodeURIComponent(jobId)}`, { method: 'POST' });
                    } catch (_) { /* ignore */ }
                };

                if (eyetrackingBatchCancelBtn) {
                    eyetrackingBatchCancelBtn.classList.remove('d-none');
                    eyetrackingBatchCancelBtn.disabled = false;
                    eyetrackingBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    eyetrackingBatchCancelBtn.onclick = cancelHandler;
                }

                let cursor = 0;
                let result = null;

                while (true) {
                    await new Promise(resolve => setTimeout(resolve, 500));

                    const statusResponse = await fetch(`/api/batch-convert-status/${encodeURIComponent(jobId)}?cursor=${cursor}`);
                    if (!statusResponse.ok) {
                        const statusErr = await statusResponse.json().catch(() => null);
                        throw new Error(statusErr && statusErr.error ? statusErr.error : 'Failed to retrieve conversion status');
                    }

                    const statusData = await statusResponse.json();
                    const newLogs = Array.isArray(statusData.logs) ? statusData.logs : [];

                    for (const log of newLogs) {
                        let colorClass = 'ansi-reset';
                        if (log.level === 'error') colorClass = 'ansi-red';
                        else if (log.level === 'warning') colorClass = 'ansi-yellow';
                        else if (log.level === 'success') colorClass = 'ansi-green';
                        else if (log.level === 'info') colorClass = 'ansi-blue';
                        else if (log.level === 'preview') colorClass = 'ansi-cyan';
                        const escaped = String(log.message).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                        if (eyetrackingBatchLog.innerHTML) eyetrackingBatchLog.innerHTML += '<br>';
                        eyetrackingBatchLog.innerHTML += `<span class="${colorClass}">${escaped}</span>`;
                    }
                    if (newLogs.length > 0) eyetrackingBatchLog.scrollTop = eyetrackingBatchLog.scrollHeight;

                    cursor = Number.isInteger(statusData.next_cursor) ? statusData.next_cursor : cursor + newLogs.length;

                    if (statusData.done) {
                        if (!statusData.success) {
                            throw new Error(statusData.error || 'Batch conversion failed');
                        }
                        result = statusData.result || {};
                        break;
                    }
                }

                if (isDryRun && result.dry_run) {
                    let infoMsg = `🧪 DRY-RUN PREVIEW\n\n`;
                    infoMsg += `✓ Would convert: ${result.converted || 0} files\n`;
                    if (result.errors) infoMsg += `✗ Errors: ${result.errors}\n`;
                    if (result.new_files) infoMsg += `📁 New files: ${result.new_files}\n`;
                    if (result.existing_files) infoMsg += `⚠️  Existing files: ${result.existing_files}\n`;
                    eyetrackingBatchInfo.textContent = infoMsg;
                } else {
                    let statusMsg = `✓ Converted ${result.converted || 0} files. ${result.errors || 0} errors.`;
                    if (result.project_saved) statusMsg += `\n📁 Files also saved to project.`;
                    if (result.warnings && result.warnings.length > 0) statusMsg += `\n⚠️  Warnings:\n${result.warnings.join('\n')}`;
                    eyetrackingBatchInfo.textContent = statusMsg;
                }
                eyetrackingBatchInfo.classList.remove('d-none');
            } catch (err) {
                if (err.message === 'Cancelled by user' || err.message === 'Conversion cancelled by user') {
                    eyetrackingBatchInfo.textContent = 'Conversion cancelled.';
                    eyetrackingBatchInfo.classList.remove('d-none');
                } else {
                    eyetrackingBatchError.textContent = err.message;
                    eyetrackingBatchError.classList.remove('d-none');
                }
            } finally {
                eyetrackingBatchProgress.classList.add('d-none');
                if (eyetrackingBatchCancelBtn) {
                    eyetrackingBatchCancelBtn.classList.add('d-none');
                    eyetrackingBatchCancelBtn.disabled = false;
                    eyetrackingBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    eyetrackingBatchCancelBtn.onclick = null;
                }
                updateEyetrackingBatchBtn();
            }
    }

    if (eyetrackingBatchPreviewBtn) {
        eyetrackingBatchPreviewBtn.addEventListener('click', async function() {
            await runEyetrackingBatchConversion(true);
        });
    }

    if (eyetrackingBatchConvertBtn) {
        eyetrackingBatchConvertBtn.addEventListener('click', async function() {
            await runEyetrackingBatchConversion(false);
        });
    }
}
