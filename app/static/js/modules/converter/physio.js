/**
 * Physio Conversion Module
 * Handles batch physio file conversion
 * Supports auto-detection of sourcedata/physio folder
 * Follows the initialization-from-hub pattern
 */

import { fetchWithApiFallback } from '../../shared/api.js';
import { pollJobStatus } from '../../shared/job-polling.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { createPollingRunState, isPollingAbortError } from './polling-run-state.js';
import { createJobRunController } from './job-run-controller.js';
import { pickServerFolder, prefersServerPicker } from './server-picker.js';

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
        browseServerPhysioFolderBtn,
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

    let physioServerFolderPath = '';
    let physioSourcedataRequestToken = 0;
    let physioSourcedataQuickSelectEl = null;
    let physioSourcedataFileSelectEl = null;
    const pollingRunState = createPollingRunState();
    const runController = createJobRunController();

    function applyPhysioPickerUiState() {
        const connectedToServer = prefersServerPicker();
        if (browseServerPhysioFolderBtn) {
            browseServerPhysioFolderBtn.classList.toggle('d-none', !connectedToServer);
        }
    }

    async function pickServerPhysioFolder() {
        return pickServerFolder({
            title: 'Select Physio Folder on Server',
            confirmLabel: 'Use This Folder',
            startPath: physioServerFolderPath || '',
        });
    }

    function ensurePhysioSourcedataQuickSelectElements() {
        if (physioSourcedataQuickSelectEl && physioSourcedataFileSelectEl) {
            return;
        }
        if (!physioBatchFiles) {
            return;
        }

        const pickerContainer = physioBatchFiles.closest('.studio-file-picker');
        if (!pickerContainer) {
            return;
        }

        physioSourcedataQuickSelectEl = pickerContainer.querySelector('#physioSourcedataQuickSelect');
        physioSourcedataFileSelectEl = pickerContainer.querySelector('#physioSourcedataFileSelect');

        if (physioSourcedataQuickSelectEl && physioSourcedataFileSelectEl) {
            return;
        }

        const inputGroup = physioBatchFiles.closest('.input-group');
        if (!inputGroup || !inputGroup.parentElement) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'physioSourcedataQuickSelect';
        wrapper.className = 'd-none mb-2';
        wrapper.innerHTML = `
            <div class="input-group input-group-sm">
                <span class="input-group-text bg-light"><i class="fas fa-folder-open text-muted"></i></span>
                <select class="form-select form-select-sm" id="physioSourcedataFileSelect">
                    <option value="">Loading sourcedata files...</option>
                </select>
            </div>
        `;

        inputGroup.parentElement.insertBefore(wrapper, inputGroup);
        physioSourcedataQuickSelectEl = wrapper;
        physioSourcedataFileSelectEl = wrapper.querySelector('#physioSourcedataFileSelect');
    }

    function resetPhysioSourcedataQuickSelect() {
        ensurePhysioSourcedataQuickSelectElements();
        if (!physioSourcedataFileSelectEl) {
            return;
        }

        physioSourcedataFileSelectEl.value = '';
        while (physioSourcedataFileSelectEl.options.length > 1) {
            physioSourcedataFileSelectEl.remove(1);
        }
    }

    function setPhysioSourcedataPlaceholder(label, { disabled = true } = {}) {
        ensurePhysioSourcedataQuickSelectElements();
        if (!physioSourcedataQuickSelectEl || !physioSourcedataFileSelectEl) {
            return;
        }

        physioSourcedataQuickSelectEl.classList.remove('d-none');
        resetPhysioSourcedataQuickSelect();

        let placeholderOption = physioSourcedataFileSelectEl.options[0];
        if (!placeholderOption) {
            placeholderOption = document.createElement('option');
            physioSourcedataFileSelectEl.appendChild(placeholderOption);
        }

        placeholderOption.value = '';
        placeholderOption.textContent = label;
        placeholderOption.disabled = disabled;
        physioSourcedataFileSelectEl.selectedIndex = 0;
        physioSourcedataFileSelectEl.disabled = disabled;
    }

    function refreshPhysioSourcedataQuickSelect(projectPath = resolveCurrentProjectPath()) {
        ensurePhysioSourcedataQuickSelectElements();
        if (!physioSourcedataQuickSelectEl || !physioSourcedataFileSelectEl) {
            return;
        }

        const previousValue = physioSourcedataFileSelectEl.value;
        const requestToken = ++physioSourcedataRequestToken;
        setPhysioSourcedataPlaceholder('Loading sourcedata files...', { disabled: true });

        const effectiveProjectPath = String(projectPath || '').trim();
        const endpoint = effectiveProjectPath
            ? `/api/projects/sourcedata-files?kind=physio&project_path=${encodeURIComponent(effectiveProjectPath)}`
            : '/api/projects/sourcedata-files?kind=physio';

        fetchWithApiFallback(endpoint)
            .then((response) => response.json())
            .then((data) => {
                if (requestToken !== physioSourcedataRequestToken) {
                    return;
                }

                if (data.sourcedata_exists && Array.isArray(data.files) && data.files.length > 0) {
                    physioSourcedataQuickSelectEl.classList.remove('d-none');
                    resetPhysioSourcedataQuickSelect();
                    physioSourcedataFileSelectEl.disabled = false;

                    const placeholderOption = physioSourcedataFileSelectEl.options[0];
                    if (placeholderOption) {
                        placeholderOption.textContent = 'Load from sourcedata/...';
                        placeholderOption.disabled = false;
                    }

                    data.files.forEach((entry) => {
                        const option = document.createElement('option');
                        option.value = entry.name;
                        const sizeKB = (entry.size / 1024).toFixed(1);
                        option.textContent = `${entry.name} (${sizeKB} KB)`;
                        physioSourcedataFileSelectEl.appendChild(option);
                    });

                    if (previousValue && Array.from(physioSourcedataFileSelectEl.options).some((option) => option.value === previousValue)) {
                        physioSourcedataFileSelectEl.value = previousValue;
                    }
                } else if (data.sourcedata_exists) {
                    setPhysioSourcedataPlaceholder('No physio files found in sourcedata/', {
                        disabled: true,
                    });
                } else {
                    setPhysioSourcedataPlaceholder('No sourcedata folder found for the current project', {
                        disabled: true,
                    });
                }
            })
            .catch(() => {
                if (requestToken !== physioSourcedataRequestToken) {
                    return;
                }
                setPhysioSourcedataPlaceholder('Could not load sourcedata files', {
                    disabled: true,
                });
            });
    }

    // ===== BATCH FILE CONVERSION =====

    function clearAutoDetectedPhysioSource() {
        if (physioBatchFolderPath) {
            physioBatchFolderPath.value = '';
        }
    }

    function clearPhysioSourceHint() {
        if (autoDetectHint) {
            autoDetectHint.textContent = '';
        }
    }

    function resetPhysioWorkflowState({ clearLog = true } = {}) {
        physioBatchError.classList.add('d-none');
        physioBatchError.textContent = '';
        physioBatchInfo.classList.add('d-none');
        physioBatchInfo.textContent = '';
        physioBatchProgress.classList.add('d-none');
        if (clearLog) {
            physioBatchLogContainer.classList.add('d-none');
            physioBatchLog.textContent = '';
        }
        if (physioBatchCancelBtn) {
            physioBatchCancelBtn.classList.add('d-none');
            physioBatchCancelBtn.disabled = false;
            physioBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
            physioBatchCancelBtn.onclick = null;
        }
    }

    // Auto-detect sourcedata/physio folder
    if (autoDetectPhysioBtn) {
        autoDetectPhysioBtn.addEventListener('click', async function() {
            try {
                const currentProjectPath = resolveCurrentProjectPath();
                if (!currentProjectPath) {
                    throw new Error('Please select a project first from the top of the page');
                }

                autoDetectPhysioBtn.disabled = true;
                autoDetectPhysioBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Detecting...';
                resetPhysioWorkflowState();
                clearAutoDetectedPhysioSource();
                physioServerFolderPath = '';
                clearPhysioSourceHint();
                
                const response = await fetchWithApiFallback(`/api/check-sourcedata-physio?project_path=${encodeURIComponent(currentProjectPath)}`);
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
                if (physioBatchError) {
                    physioBatchError.innerHTML = `<i class="fas fa-exclamation-circle me-2"></i>${error.message}`;
                    physioBatchError.classList.remove('d-none');
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
        const hasServerFolderPath = Boolean(physioServerFolderPath);
        const shouldEnable = hasFiles || hasFolder || hasAutoPath || hasServerFolderPath;

        clearPhysioBatchFilesBtn?.classList.toggle('d-none', !hasFiles);
        clearPhysioBatchFolderBtn?.classList.toggle('d-none', !(hasFolder || hasAutoPath || hasServerFolderPath));

        if (physioBatchPreviewBtn) {
            physioBatchPreviewBtn.disabled = !shouldEnable;
        }
        if (physioBatchConvertBtn) {
            physioBatchConvertBtn.disabled = !shouldEnable;
            console.log('[Physio] Button update - hasFiles:', hasFiles, 'hasFolder:', hasFolder, 'hasAutoPath:', hasAutoPath, 'disabled:', !shouldEnable);
        }
    }

    if (physioBatchFiles) {
        physioBatchFiles.addEventListener('change', function() {
            physioServerFolderPath = '';
            clearAutoDetectedPhysioSource();
            clearPhysioSourceHint();
            resetPhysioWorkflowState();
            updatePhysioBatchBtn();
        });
        updatePhysioBatchBtn();
    }

    if (physioBatchFolder) {
        physioBatchFolder.addEventListener('change', function() {
            physioServerFolderPath = '';
            clearAutoDetectedPhysioSource();
            clearPhysioSourceHint();
            resetPhysioWorkflowState();
            updatePhysioBatchBtn();
        });
        updatePhysioBatchBtn();
    }

    if (browseServerPhysioFolderBtn) {
        browseServerPhysioFolderBtn.addEventListener('click', async function() {
            const pickedPath = await pickServerPhysioFolder();
            if (!pickedPath) return;

            physioServerFolderPath = pickedPath;
            clearAutoDetectedPhysioSource();
            if (physioBatchFiles) {
                physioBatchFiles.value = '';
            }
            if (physioBatchFolder) {
                physioBatchFolder.value = '';
            }
            if (autoDetectHint) {
                autoDetectHint.innerHTML = `<i class="fas fa-server me-1"></i>Server folder selected: ${pickedPath}`;
            }

            resetPhysioWorkflowState();
            updatePhysioBatchBtn();
        });
    }

    clearPhysioBatchFilesBtn?.addEventListener('click', function() {
        if (physioBatchFiles) {
            physioBatchFiles.value = '';
            physioBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });

    clearPhysioBatchFolderBtn?.addEventListener('click', function() {
        physioServerFolderPath = '';
        if (physioBatchFolder) {
            physioBatchFolder.value = '';
            physioBatchFolder.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (physioBatchFolderPath) {
            physioBatchFolderPath.value = '';
        }
        clearPhysioSourceHint();
        resetPhysioWorkflowState();
        updatePhysioBatchBtn();
    });

    window.addEventListener('prism-project-changed', function() {
        void runController.cancelActiveJob({
            buildCancelUrl: (jobId) => `/api/batch-convert-cancel/${encodeURIComponent(jobId)}`,
        }).catch(() => {});
        pollingRunState.abortActive('Physio polling aborted due to project change.');
        physioServerFolderPath = '';
        clearAutoDetectedPhysioSource();
        clearPhysioSourceHint();
        resetPhysioWorkflowState();
        updatePhysioBatchBtn();
        refreshPhysioSourcedataQuickSelect();
    });

    window.addEventListener('prism-library-settings-changed', function() {
        applyPhysioPickerUiState();
    });

    if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
        window.PrismFileSystemMode.init().then(() => {
            applyPhysioPickerUiState();
        }).catch(() => {
            // Keep host picker behavior on init failure.
        });
    }

    applyPhysioPickerUiState();

    ensurePhysioSourcedataQuickSelectElements();
    if (physioSourcedataQuickSelectEl && physioSourcedataFileSelectEl) {
        refreshPhysioSourcedataQuickSelect();

        physioSourcedataFileSelectEl.addEventListener('change', async function() {
            const filename = this.value;
            if (!filename) {
                return;
            }

            try {
                const currentProjectPath = resolveCurrentProjectPath();
                const endpoint = currentProjectPath
                    ? `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}`
                    : `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}`;

                const response = await fetchWithApiFallback(endpoint);
                if (!response.ok) {
                    throw new Error('Failed to load sourcedata file');
                }

                const blob = await response.blob();
                const file = new File([blob], filename, { type: blob.type });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);

                if (physioBatchFiles) {
                    physioBatchFiles.files = dataTransfer.files;
                    physioBatchFiles.dispatchEvent(new Event('change', { bubbles: true }));
                }
                if (physioBatchFolder) {
                    physioBatchFolder.value = '';
                }
                clearAutoDetectedPhysioSource();
                clearPhysioSourceHint();
                physioServerFolderPath = '';
            } catch (_error) {
                if (physioBatchError) {
                    physioBatchError.innerHTML = `<i class="fas fa-exclamation-circle me-2"></i>Failed to load ${filename} from sourcedata.`;
                    physioBatchError.classList.remove('d-none');
                }
            } finally {
                refreshPhysioSourcedataQuickSelect();
            }
        });
    }
    
    if (physioBatchLogClearBtn) {
        physioBatchLogClearBtn.addEventListener('click', () => {
            if (physioBatchLog) physioBatchLog.textContent = '';
        });
    }

    async function runPhysioBatchConversion(dryRunMode) {
            if (!runController.tryStartRun()) {
                return;
            }

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
                if (!physioBatchLog) {
                    return;
                }
                if (physioBatchLog.childNodes.length > 0) {
                    physioBatchLog.appendChild(document.createElement('br'));
                }
                const line = document.createElement('span');
                line.className = cssClass;
                line.textContent = String(message);
                physioBatchLog.appendChild(line);
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
            const manualServerPath = physioServerFolderPath || '';
            
            console.log('[Physio] Files from input:', filesFromInput.length, 'Files from folder:', filesFromFolder.length, 'Auto-detected path:', autoDetectedPath);
            
            const samplingRate = physioBatchSamplingRate ? physioBatchSamplingRate.value.trim() : '';
            const isDryRun = dryRunMode;
            const currentProjectPath = resolveCurrentProjectPath();

            if (!isDryRun && !currentProjectPath) {
                physioBatchError.textContent = 'Please select a project first from the top of the page';
                physioBatchError.classList.remove('d-none');
                physioBatchProgress.classList.add('d-none');
                updatePhysioBatchBtn();
                runController.finishRun();
                return;
            }

            const formData = new FormData();
            
            // If we have an auto-detected folder path, use it
            if (autoDetectedPath) {
                console.log('[Physio] Using auto-detected folder path for conversion');
                formData.append('folder_path', autoDetectedPath);
            } else if (manualServerPath) {
                console.log('[Physio] Using server-picked folder path for conversion');
                formData.append('folder_path', manualServerPath);
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
                    runController.finishRun();
                    return;
                }
                
                // Add files to form data
                files.forEach(f => formData.append('files', f));
            }
            
            formData.append('dataset_name', 'Physio Dataset');  // Default name (not used when saving to project)
            formData.append('modality', 'physio');
            formData.append('save_to_project', isDryRun ? 'false' : 'true');  // Don't save if dry-run
            formData.append('dest_root', 'prism');     // Save to project root
            if (currentProjectPath) {
                formData.append('project_path', currentProjectPath);
            }
            formData.append('generate_physio_reports', (physioGenerateReports && physioGenerateReports.checked) ? 'true' : 'false');
            if (samplingRate) {
                formData.append('sampling_rate', samplingRate);
            }
            formData.append('dry_run', isDryRun ? 'true' : 'false');

            let activePollController = null;
            try {
                const response = await fetchWithApiFallback('/api/batch-convert-start', {
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
                    if (physioBatchCancelBtn) {
                        physioBatchCancelBtn.disabled = true;
                        physioBatchCancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Cancelling...';
                    }
                    try {
                        await runController.cancelActiveJob({
                            buildCancelUrl: (activeJobId) => `/api/batch-convert-cancel/${encodeURIComponent(activeJobId)}`,
                        });
                        writeLocalLog('⏹️ Cancellation requested. Waiting for cleanup...', 'ansi-yellow');
                    } catch (cancelError) {
                        physioBatchError.textContent = cancelError.message;
                        physioBatchError.classList.remove('d-none');
                        if (physioBatchCancelBtn) {
                            physioBatchCancelBtn.disabled = false;
                            physioBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                        }
                    }
                };

                if (physioBatchCancelBtn) {
                    physioBatchCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    physioBatchCancelBtn.onclick = cancelHandler;
                }

                activePollController = pollingRunState.start();

                const statusData = await pollJobStatus({
                    fetchStatus: async (cursor) => {
                        const statusResponse = await fetchWithApiFallback(`/api/batch-convert-status/${encodeURIComponent(jobId)}?cursor=${cursor}`);
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

                            writeLocalLog(log.message, colorClass);
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
                    signal: activePollController.signal,
                    abortErrorMessage: 'Physio polling aborted due to project change.',
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
                    const outputPaths = Array.isArray(result.project_output_paths)
                        ? result.project_output_paths.filter((value) => typeof value === 'string' && value.trim())
                        : [];
                    const saveTarget = result.project_output_path || outputPaths[0] || result.project_output_root || null;
                    const savedCount = Number.isFinite(result.project_output_count)
                        ? result.project_output_count
                        : outputPaths.length;
                    let infoMsg = `✅ Converted ${result.converted || 0} files. ${result.errors || 0} errors.`;
                    if (result.project_saved && saveTarget) {
                        infoMsg += `\n📁 Saved to project: ${saveTarget}`;
                        if (savedCount > 1) {
                            infoMsg += ` (${savedCount} files)`;
                        }
                        infoMsg += '.';
                    } else if ((result.converted || 0) > 0) {
                        infoMsg += '\n⚠️ Converted files were not copied into the project.';
                    }
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
                if (isPollingAbortError(err)) {
                    // Project-change listeners already reset converter state.
                } else if (err.message === 'Cancelled by user' || err.message === 'Conversion cancelled by user') {
                    physioBatchInfo.textContent = 'Conversion cancelled. Temporary staged output was cleaned up and nothing was copied into the project.';
                    physioBatchInfo.classList.remove('d-none');
                } else {
                    physioBatchError.textContent = err.message;
                    physioBatchError.classList.remove('d-none');
                }
            } finally {
                pollingRunState.clear(activePollController);
                runController.finishRun();
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
