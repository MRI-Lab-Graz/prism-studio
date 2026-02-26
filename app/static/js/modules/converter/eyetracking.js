/**
 * Eyetracking Converter Module
 * Handles both single file and batch eyetracking conversion
 */

export function initEyetracking(elements) {
    const {
        // Single convert elements
        eyetrackingSingleFile,
        eyetrackingSubject,
        eyetrackingSession,
        eyetrackingTask,
        eyetrackingSingleConvertBtn,
        eyetrackingSingleError,
        eyetrackingSingleInfo,
        // Batch convert elements
        eyetrackingBatchFiles,
        clearEyetrackingBatchFilesBtn,
        eyetrackingBatchDatasetName,
        eyetrackingBatchConvertBtn,
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

    // --- Eyetracking Single Convert ---
    function updateEyetrackingSingleBtn() {
        const hasFile = eyetrackingSingleFile && eyetrackingSingleFile.files && eyetrackingSingleFile.files.length === 1;
        const hasSubject = eyetrackingSubject && eyetrackingSubject.value.trim().length > 0;
        if (eyetrackingSingleConvertBtn) eyetrackingSingleConvertBtn.disabled = !(hasFile && hasSubject);
    }

    if (eyetrackingSingleFile) {
        eyetrackingSingleFile.addEventListener('change', updateEyetrackingSingleBtn);
    }
    if (eyetrackingSubject) {
        eyetrackingSubject.addEventListener('input', updateEyetrackingSingleBtn);
    }
    updateEyetrackingSingleBtn();

    if (eyetrackingSingleConvertBtn) {
        eyetrackingSingleConvertBtn.addEventListener('click', async function() {
            eyetrackingSingleError.classList.add('d-none');
            eyetrackingSingleInfo.classList.add('d-none');
            eyetrackingSingleConvertBtn.disabled = true;

            const file = eyetrackingSingleFile.files[0];
            const subject = eyetrackingSubject.value.trim();
            const session = eyetrackingSession ? eyetrackingSession.value.trim() : '';
            const task = eyetrackingTask ? eyetrackingTask.value.trim() : 'gaze';

            const formData = new FormData();
            formData.append('edf', file);
            formData.append('subject', subject);
            formData.append('task', task);
            if (session) formData.append('session', session);

            eyetrackingSingleInfo.textContent = 'Converting... this may take a moment.';
            eyetrackingSingleInfo.classList.remove('d-none');

            try {
                const response = await fetch('/api/eyetracking-convert', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    throw new Error(data && data.error ? data.error : 'Conversion failed');
                }

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'eyetracking_prism.zip';
                document.body.appendChild(a);
                a.click();
                a.remove();
                eyetrackingSingleInfo.textContent = 'Done. Your ZIP download should start automatically.';
            } catch (err) {
                eyetrackingSingleError.textContent = err.message;
                eyetrackingSingleError.classList.remove('d-none');
                eyetrackingSingleInfo.classList.add('d-none');
            } finally {
                updateEyetrackingSingleBtn();
            }
        });
    }

    // --- Eyetracking Batch Convert ---
    function updateEyetrackingBatchBtn() {
        const hasFiles = eyetrackingBatchFiles && eyetrackingBatchFiles.files && eyetrackingBatchFiles.files.length > 0;
        clearEyetrackingBatchFilesBtn?.classList.toggle('d-none', !hasFiles);
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

    // Handle dry-run checkbox state change for eyetracking
    if (eyetrackingBatchDryRunCheckbox) {
        eyetrackingBatchDryRunCheckbox.addEventListener('change', function() {
            if (eyetrackingBatchConvertBtn) {
                if (this.checked) {
                    eyetrackingBatchConvertBtn.innerHTML = '<i class="fas fa-flask me-2"></i>Preview (Dry-Run)';
                } else {
                    eyetrackingBatchConvertBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Convert All & Download';
                }
            }
        });
    }

    if (eyetrackingBatchConvertBtn) {
        eyetrackingBatchConvertBtn.addEventListener('click', async function() {
            eyetrackingBatchError.classList.add('d-none');
            eyetrackingBatchInfo.classList.add('d-none');
            eyetrackingBatchProgress.classList.remove('d-none');
            eyetrackingBatchLogContainer.classList.remove('d-none');
            eyetrackingBatchLog.textContent = '';
            eyetrackingBatchConvertBtn.disabled = true;

            const files = Array.from(eyetrackingBatchFiles.files);
            const isDryRun = document.getElementById('eyetrackingBatchDryRun')?.checked || false;

            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            formData.append('modality', 'eyetracking');
            formData.append('dry_run', isDryRun ? 'true' : 'false');
            formData.append('save_to_project', 'true');
            formData.append('dest_root', 'rawdata');

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
                    eyetrackingBatchLog.innerHTML = logLines.join('<br>');
                    eyetrackingBatchLog.scrollTop = eyetrackingBatchLog.scrollHeight;
                } else if (result.log) {
                    eyetrackingBatchLog.textContent = result.log;
                }

                if (isDryRun && result.dry_run) {
                    // Dry-run preview mode
                    let infoMsg = `🧪 DRY-RUN PREVIEW\n\n`;
                    infoMsg += `✓ Would convert: ${result.converted || 0} files\n`;
                    if (result.errors) infoMsg += `✗ Errors: ${result.errors}\n`;
                    if (result.new_files) infoMsg += `📁 New files: ${result.new_files}\n`;
                    if (result.existing_files) infoMsg += `⚠️  Existing files: ${result.existing_files}\n`;
                    eyetrackingBatchInfo.textContent = infoMsg;
                } else {
                    // Download the ZIP
                    if (result.zip) {
                        downloadBase64Zip(result.zip, `Eyetracking_prism.zip`);
                    }
                    let statusMsg = `✓ Converted ${result.converted || 0} files. ${result.errors || 0} errors.`;
                    if (result.project_saved) {
                        statusMsg += `\n📁 Files also saved to project.`;
                    }
                    if (result.warnings && result.warnings.length > 0) {
                        statusMsg += `\n⚠️  Warnings:\n${result.warnings.join('\n')}`;
                    }
                    eyetrackingBatchInfo.textContent = statusMsg;
                }
                eyetrackingBatchInfo.classList.remove('d-none');
            } catch (err) {
                eyetrackingBatchError.textContent = err.message;
                eyetrackingBatchError.classList.remove('d-none');
            } finally {
                eyetrackingBatchProgress.classList.add('d-none');
                updateEyetrackingBatchBtn();
            }
        });
    }
}
