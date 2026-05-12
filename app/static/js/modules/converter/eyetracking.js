/**
 * Eyetracking Converter Module
 * Handles batch eyetracking conversion
 */

import { pollJobStatus } from '../../shared/job-polling.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { createPollingRunState, isPollingAbortError } from './polling-run-state.js';
import { createJobRunController } from './job-run-controller.js';

export function initEyetracking(elements) {
    const STATUS_POLL_INTERVAL_MS = 500;
    const STATUS_POLL_TIMEOUT_MS = 5 * 60 * 1000;
    const MAX_STATUS_POLL_ERRORS = 4;

    const {
        // Batch convert elements
        eyetrackingBatchFiles,
        browseServerEyetrackingFolderBtn,
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
        eyetrackingServerFolderHint,
        // Shared functions
        downloadBase64Zip
    } = elements;

    let eyetrackingServerFolderPath = '';
    let eyetrackingSourcedataRequestToken = 0;
    let eyetrackingSourcedataQuickSelectEl = null;
    let eyetrackingSourcedataFileSelectEl = null;
    const pollingRunState = createPollingRunState();
    const runController = createJobRunController();

    function prefersServerPicker() {
        return Boolean(
            window.PrismFileSystemMode
            && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
            && window.PrismFileSystemMode.prefersServerPicker()
        );
    }

    function applyEyetrackingPickerUiState() {
        const connectedToServer = prefersServerPicker();
        if (browseServerEyetrackingFolderBtn) {
            browseServerEyetrackingFolderBtn.classList.toggle('d-none', !connectedToServer);
        }
    }

    async function pickServerEyetrackingFolder() {
        if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFolder === 'function')) {
            return '';
        }

        return window.PrismFileSystemMode.pickFolder({
            title: 'Select Eyetracking Folder on Server',
            confirmLabel: 'Use This Folder',
            startPath: eyetrackingServerFolderPath || '',
        });
    }

    function ensureEyetrackingSourcedataQuickSelectElements() {
        if (eyetrackingSourcedataQuickSelectEl && eyetrackingSourcedataFileSelectEl) {
            return;
        }
        if (!eyetrackingBatchFiles) {
            return;
        }

        const pickerContainer = eyetrackingBatchFiles.closest('.studio-file-picker');
        if (!pickerContainer) {
            return;
        }

        eyetrackingSourcedataQuickSelectEl = pickerContainer.querySelector('#eyetrackingSourcedataQuickSelect');
        eyetrackingSourcedataFileSelectEl = pickerContainer.querySelector('#eyetrackingSourcedataFileSelect');

        if (eyetrackingSourcedataQuickSelectEl && eyetrackingSourcedataFileSelectEl) {
            return;
        }

        const inputGroup = eyetrackingBatchFiles.closest('.input-group');
        if (!inputGroup || !inputGroup.parentElement) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'eyetrackingSourcedataQuickSelect';
        wrapper.className = 'd-none mb-2';
        wrapper.innerHTML = `
            <div class="input-group input-group-sm">
                <span class="input-group-text bg-light"><i class="fas fa-folder-open text-muted"></i></span>
                <select class="form-select form-select-sm" id="eyetrackingSourcedataFileSelect">
                    <option value="">Loading sourcedata files...</option>
                </select>
            </div>
        `;

        inputGroup.parentElement.insertBefore(wrapper, inputGroup);
        eyetrackingSourcedataQuickSelectEl = wrapper;
        eyetrackingSourcedataFileSelectEl = wrapper.querySelector('#eyetrackingSourcedataFileSelect');
    }

    function resetEyetrackingSourcedataQuickSelect() {
        ensureEyetrackingSourcedataQuickSelectElements();
        if (!eyetrackingSourcedataFileSelectEl) {
            return;
        }

        eyetrackingSourcedataFileSelectEl.value = '';
        while (eyetrackingSourcedataFileSelectEl.options.length > 1) {
            eyetrackingSourcedataFileSelectEl.remove(1);
        }
    }

    function setEyetrackingSourcedataPlaceholder(label, { disabled = true } = {}) {
        ensureEyetrackingSourcedataQuickSelectElements();
        if (!eyetrackingSourcedataQuickSelectEl || !eyetrackingSourcedataFileSelectEl) {
            return;
        }

        eyetrackingSourcedataQuickSelectEl.classList.remove('d-none');
        resetEyetrackingSourcedataQuickSelect();

        let placeholderOption = eyetrackingSourcedataFileSelectEl.options[0];
        if (!placeholderOption) {
            placeholderOption = document.createElement('option');
            eyetrackingSourcedataFileSelectEl.appendChild(placeholderOption);
        }

        placeholderOption.value = '';
        placeholderOption.textContent = label;
        placeholderOption.disabled = disabled;
        eyetrackingSourcedataFileSelectEl.selectedIndex = 0;
        eyetrackingSourcedataFileSelectEl.disabled = disabled;
    }

    function refreshEyetrackingSourcedataQuickSelect(projectPath = resolveCurrentProjectPath()) {
        ensureEyetrackingSourcedataQuickSelectElements();
        if (!eyetrackingSourcedataQuickSelectEl || !eyetrackingSourcedataFileSelectEl) {
            return;
        }

        const previousValue = eyetrackingSourcedataFileSelectEl.value;
        const requestToken = ++eyetrackingSourcedataRequestToken;
        setEyetrackingSourcedataPlaceholder('Loading sourcedata files...', { disabled: true });

        const effectiveProjectPath = String(projectPath || '').trim();
        const endpoint = effectiveProjectPath
            ? `/api/projects/sourcedata-files?kind=eyetracking&project_path=${encodeURIComponent(effectiveProjectPath)}`
            : '/api/projects/sourcedata-files?kind=eyetracking';

        fetch(endpoint)
            .then((response) => response.json())
            .then((data) => {
                if (requestToken !== eyetrackingSourcedataRequestToken) {
                    return;
                }

                if (data.sourcedata_exists && Array.isArray(data.files) && data.files.length > 0) {
                    eyetrackingSourcedataQuickSelectEl.classList.remove('d-none');
                    resetEyetrackingSourcedataQuickSelect();
                    eyetrackingSourcedataFileSelectEl.disabled = false;

                    const placeholderOption = eyetrackingSourcedataFileSelectEl.options[0];
                    if (placeholderOption) {
                        placeholderOption.textContent = 'Load from sourcedata/...';
                        placeholderOption.disabled = false;
                    }

                    data.files.forEach((entry) => {
                        const option = document.createElement('option');
                        option.value = entry.name;
                        const sizeKB = (entry.size / 1024).toFixed(1);
                        option.textContent = `${entry.name} (${sizeKB} KB)`;
                        eyetrackingSourcedataFileSelectEl.appendChild(option);
                    });

                    if (previousValue && Array.from(eyetrackingSourcedataFileSelectEl.options).some((option) => option.value === previousValue)) {
                        eyetrackingSourcedataFileSelectEl.value = previousValue;
                    }
                } else if (data.sourcedata_exists) {
                    setEyetrackingSourcedataPlaceholder('No eyetracking files found in sourcedata/', {
                        disabled: true,
                    });
                } else {
                    setEyetrackingSourcedataPlaceholder('No sourcedata folder found for the current project', {
                        disabled: true,
                    });
                }
            })
            .catch(() => {
                if (requestToken !== eyetrackingSourcedataRequestToken) {
                    return;
                }
                setEyetrackingSourcedataPlaceholder('Could not load sourcedata files', {
                    disabled: true,
                });
            });
    }

    // --- Eyetracking Batch Convert ---
    function resetEyetrackingWorkflowState({ clearLog = true } = {}) {
        eyetrackingBatchError.classList.add('d-none');
        eyetrackingBatchError.textContent = '';
        eyetrackingBatchInfo.classList.add('d-none');
        eyetrackingBatchInfo.textContent = '';
        eyetrackingBatchProgress.classList.add('d-none');
        if (clearLog) {
            eyetrackingBatchLogContainer.classList.add('d-none');
            eyetrackingBatchLog.textContent = '';
        }
        if (eyetrackingBatchCancelBtn) {
            eyetrackingBatchCancelBtn.classList.add('d-none');
            eyetrackingBatchCancelBtn.disabled = false;
            eyetrackingBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
            eyetrackingBatchCancelBtn.onclick = null;
        }
    }

    function updateEyetrackingBatchBtn() {
        const hasFiles = eyetrackingBatchFiles && eyetrackingBatchFiles.files && eyetrackingBatchFiles.files.length > 0;
        const hasServerFolder = Boolean(eyetrackingServerFolderPath);
        clearEyetrackingBatchFilesBtn?.classList.toggle('d-none', !(hasFiles || hasServerFolder));
        if (eyetrackingBatchPreviewBtn) eyetrackingBatchPreviewBtn.disabled = !(hasFiles || hasServerFolder);
        if (eyetrackingBatchConvertBtn) eyetrackingBatchConvertBtn.disabled = !(hasFiles || hasServerFolder);
    }

    if (eyetrackingBatchFiles) {
        eyetrackingBatchFiles.addEventListener('change', function() {
            eyetrackingServerFolderPath = '';
            if (eyetrackingServerFolderHint) {
                eyetrackingServerFolderHint.textContent = '';
                eyetrackingServerFolderHint.classList.add('d-none');
            }
            resetEyetrackingWorkflowState();
            updateEyetrackingBatchBtn();
        });
        updateEyetrackingBatchBtn();
    }

    if (browseServerEyetrackingFolderBtn) {
        browseServerEyetrackingFolderBtn.addEventListener('click', async function() {
            const pickedPath = await pickServerEyetrackingFolder();
            if (!pickedPath) return;

            eyetrackingServerFolderPath = pickedPath;
            if (eyetrackingBatchFiles) {
                eyetrackingBatchFiles.value = '';
            }
            if (eyetrackingServerFolderHint) {
                eyetrackingServerFolderHint.textContent = `Server folder: ${pickedPath}`;
                eyetrackingServerFolderHint.classList.remove('d-none');
            }

            resetEyetrackingWorkflowState();
            updateEyetrackingBatchBtn();
        });
    }

    clearEyetrackingBatchFilesBtn?.addEventListener('click', function() {
        eyetrackingServerFolderPath = '';
        if (eyetrackingServerFolderHint) {
            eyetrackingServerFolderHint.textContent = '';
            eyetrackingServerFolderHint.classList.add('d-none');
        }
        if (eyetrackingBatchFiles) {
            eyetrackingBatchFiles.value = '';
            eyetrackingBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
        }
        resetEyetrackingWorkflowState();
    });

    window.addEventListener('prism-project-changed', function() {
        void runController.cancelActiveJob({
            buildCancelUrl: (jobId) => `/api/batch-convert-cancel/${encodeURIComponent(jobId)}`,
        }).catch(() => {});
        pollingRunState.abortActive('Eyetracking polling aborted due to project change.');
        resetEyetrackingWorkflowState();
        updateEyetrackingBatchBtn();
        refreshEyetrackingSourcedataQuickSelect();
    });

    window.addEventListener('prism-library-settings-changed', function() {
        applyEyetrackingPickerUiState();
    });

    if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
        window.PrismFileSystemMode.init().then(() => {
            applyEyetrackingPickerUiState();
        }).catch(() => {
            // Keep host picker behavior on init failure.
        });
    }

    applyEyetrackingPickerUiState();

    ensureEyetrackingSourcedataQuickSelectElements();
    if (eyetrackingSourcedataQuickSelectEl && eyetrackingSourcedataFileSelectEl) {
        refreshEyetrackingSourcedataQuickSelect();

        eyetrackingSourcedataFileSelectEl.addEventListener('change', async function() {
            const filename = this.value;
            if (!filename) {
                return;
            }

            try {
                const currentProjectPath = resolveCurrentProjectPath();
                const endpoint = currentProjectPath
                    ? `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}`
                    : `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}`;

                const response = await fetch(endpoint);
                if (!response.ok) {
                    throw new Error('Failed to load sourcedata file');
                }

                const blob = await response.blob();
                const file = new File([blob], filename, { type: blob.type });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);

                if (eyetrackingBatchFiles) {
                    eyetrackingBatchFiles.files = dataTransfer.files;
                    eyetrackingBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
                }

                eyetrackingServerFolderPath = '';
                if (eyetrackingServerFolderHint) {
                    eyetrackingServerFolderHint.textContent = '';
                    eyetrackingServerFolderHint.classList.add('d-none');
                }
            } catch (_error) {
                if (eyetrackingBatchError) {
                    eyetrackingBatchError.textContent = `Failed to load ${filename} from sourcedata.`;
                    eyetrackingBatchError.classList.remove('d-none');
                }
            } finally {
                refreshEyetrackingSourcedataQuickSelect();
            }
        });
    }

    if (eyetrackingBatchLogClearBtn) {
        eyetrackingBatchLogClearBtn.addEventListener('click', () => {
            if (eyetrackingBatchLog) eyetrackingBatchLog.textContent = '';
        });
    }

    async function runEyetrackingBatchConversion(dryRunMode) {
            if (!runController.tryStartRun()) {
                return;
            }

            eyetrackingBatchError.classList.add('d-none');
            eyetrackingBatchInfo.classList.add('d-none');
            eyetrackingBatchProgress.classList.remove('d-none');
            eyetrackingBatchLogContainer.classList.remove('d-none');
            eyetrackingBatchLog.textContent = '';
            if (eyetrackingBatchPreviewBtn) eyetrackingBatchPreviewBtn.disabled = true;
            if (eyetrackingBatchConvertBtn) eyetrackingBatchConvertBtn.disabled = true;

            const files = Array.from(eyetrackingBatchFiles.files || []);
            const isDryRun = dryRunMode;
            if (eyetrackingBatchDryRunCheckbox) {
                eyetrackingBatchDryRunCheckbox.checked = dryRunMode;
            }

            const formData = new FormData();
            if (eyetrackingServerFolderPath) {
                formData.append('folder_path', eyetrackingServerFolderPath);
            } else {
                files.forEach(f => formData.append('files', f));
            }
            formData.append('modality', 'eyetracking');
            formData.append('dry_run', isDryRun ? 'true' : 'false');
            formData.append('save_to_project', isDryRun ? 'false' : 'true');
            formData.append('dest_root', 'prism');
            const currentProjectPath = resolveCurrentProjectPath();
            if (!isDryRun && !currentProjectPath) {
                eyetrackingBatchError.textContent = 'Please select a project first from the top of the page';
                eyetrackingBatchError.classList.remove('d-none');
                eyetrackingBatchProgress.classList.add('d-none');
                updateEyetrackingBatchBtn();
                runController.finishRun();
                return;
            }
            if (currentProjectPath) {
                formData.append('project_path', currentProjectPath);
            }

            let activePollController = null;
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
                runController.setActiveJobId(jobId);

                const cancelHandler = async () => {
                    if (eyetrackingBatchCancelBtn) {
                        eyetrackingBatchCancelBtn.disabled = true;
                        eyetrackingBatchCancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Cancelling...';
                    }
                    try {
                        await runController.cancelActiveJob({
                            buildCancelUrl: (activeJobId) => `/api/batch-convert-cancel/${encodeURIComponent(activeJobId)}`,
                        });
                    } catch (_) { /* ignore */ }
                };

                if (eyetrackingBatchCancelBtn) {
                    eyetrackingBatchCancelBtn.classList.remove('d-none');
                    eyetrackingBatchCancelBtn.disabled = false;
                    eyetrackingBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    eyetrackingBatchCancelBtn.onclick = cancelHandler;
                }

                activePollController = pollingRunState.start();

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
                            const escaped = String(log.message).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                            if (eyetrackingBatchLog.innerHTML) eyetrackingBatchLog.innerHTML += '<br>';
                            eyetrackingBatchLog.innerHTML += `<span class="${colorClass}">${escaped}</span>`;
                        }
                        if (newLogs.length > 0) eyetrackingBatchLog.scrollTop = eyetrackingBatchLog.scrollHeight;
                    },
                    onRetryWarning: ({ attempt, maxAttempts, error }) => {
                        const escaped = String(`⚠️ Status check failed (${attempt}/${maxAttempts}): ${error.message || error}`)
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;');
                        if (eyetrackingBatchLog.innerHTML) eyetrackingBatchLog.innerHTML += '<br>';
                        eyetrackingBatchLog.innerHTML += `<span class="ansi-yellow">${escaped}</span>`;
                        eyetrackingBatchLog.scrollTop = eyetrackingBatchLog.scrollHeight;
                    },
                    intervalMs: STATUS_POLL_INTERVAL_MS,
                    timeoutMs: STATUS_POLL_TIMEOUT_MS,
                    maxConsecutiveErrors: MAX_STATUS_POLL_ERRORS,
                    signal: activePollController.signal,
                    abortErrorMessage: 'Eyetracking polling aborted due to project change.',
                    timeoutErrorMessage: 'Eyetracking conversion status timed out after 5 minutes. Please review logs and retry.',
                    statusFailureMessage: 'Failed to retrieve conversion status after multiple attempts.',
                    getFailureError: (nextStatusData) => nextStatusData.error || 'Batch conversion failed',
                });

                const result = statusData.result || {};

                if (isDryRun && result.dry_run) {
                    let infoMsg = `🧪 DRY-RUN PREVIEW\n\n`;
                    infoMsg += `✓ Would convert: ${result.converted || 0} files\n`;
                    if (result.errors) infoMsg += `✗ Errors: ${result.errors}\n`;
                    if (result.new_files) infoMsg += `📁 New files: ${result.new_files}\n`;
                    if (result.existing_files) infoMsg += `⚠️  Existing files: ${result.existing_files}\n`;
                    eyetrackingBatchInfo.textContent = infoMsg;
                } else {
                    let statusMsg = `✓ Converted ${result.converted || 0} files. ${result.errors || 0} errors.`;
                    const outputPaths = Array.isArray(result.project_output_paths)
                        ? result.project_output_paths.filter((value) => typeof value === 'string' && value.trim())
                        : [];
                    const saveTarget = result.project_output_path || outputPaths[0] || result.project_output_root || null;
                    const savedCount = Number.isFinite(result.project_output_count)
                        ? result.project_output_count
                        : outputPaths.length;
                    if (result.project_saved && saveTarget) {
                        statusMsg += `\n📁 Saved to project: ${saveTarget}`;
                        if (savedCount > 1) statusMsg += ` (${savedCount} files)`;
                        statusMsg += '.';
                    } else if ((result.converted || 0) > 0) {
                        statusMsg += `\n⚠️ Converted files were not copied into the project.`;
                    }
                    if (result.warnings && result.warnings.length > 0) statusMsg += `\n⚠️  Warnings:\n${result.warnings.join('\n')}`;
                    eyetrackingBatchInfo.textContent = statusMsg;
                }
                eyetrackingBatchInfo.classList.remove('d-none');
            } catch (err) {
                if (isPollingAbortError(err)) {
                    // Project-change listeners already reset UI state.
                } else if (err.message === 'Cancelled by user' || err.message === 'Conversion cancelled by user') {
                    eyetrackingBatchInfo.textContent = 'Conversion cancelled.';
                    eyetrackingBatchInfo.classList.remove('d-none');
                } else {
                    eyetrackingBatchError.textContent = err.message;
                    eyetrackingBatchError.classList.remove('d-none');
                }
            } finally {
                pollingRunState.clear(activePollController);
                runController.finishRun();
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
