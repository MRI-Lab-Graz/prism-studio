// File upload handling
document.addEventListener('DOMContentLoaded', function() {
    // Validation Mode Toggles
    const modeRadios = document.querySelectorAll('input[name="validation_mode"]');
    const bidsOptions = document.getElementById('bids_options');
    const bidsWarningsCheckbox = document.getElementById('bids_warnings');
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const currentProjectPathInput = document.getElementById('currentProjectPath');
    const currentProjectNameInput = document.getElementById('currentProjectName');
    const currentProjectTargetDetails = document.getElementById('currentProjectTargetDetails');
    const currentProjectBadge = document.getElementById('currentProjectBadge');
    const targetCurrentProject = document.getElementById('targetCurrentProject');
    const targetOtherFolder = document.getElementById('targetOtherFolder');
    
    function updateBidsOptions() {
        const selectedModeRadio = document.querySelector('input[name="validation_mode"]:checked');
        const selectedMode = selectedModeRadio ? selectedModeRadio.value : 'both';
        const advancedEnabled = Boolean(advancedOptionsToggle && advancedOptionsToggle.checked);
        if (bidsOptions) {
            bidsOptions.style.display = (advancedEnabled && (selectedMode === 'both' || selectedMode === 'bids')) ? 'block' : 'none';
        }
        if (bidsWarningsCheckbox) {
            const enableWarnings = advancedEnabled && (selectedMode === 'both' || selectedMode === 'bids');
            bidsWarningsCheckbox.disabled = !enableWarnings;
            if (!enableWarnings) {
                bidsWarningsCheckbox.checked = false;
            }
        }
    }

    modeRadios.forEach(radio => {
        radio.addEventListener('change', updateBidsOptions);
    });
    
    // Initial state
    updateBidsOptions();

    const uploadArea = document.getElementById('uploadArea');
    const folderInput = document.getElementById('datasetFolder');
    const folderBtn = document.getElementById('folderBtn');
    const selectedFolderPath = document.getElementById('selectedFolderPath');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadInfo = document.getElementById('uploadInfo');
    const browserWarning = document.getElementById('browserWarning');
    const browseLibraryBtn = document.getElementById('browseLibraryBtn');
    const libraryPathInput = document.getElementById('library_path');
    const schemaVersionSelect = document.getElementById('schema_version');
    const advancedOptions = document.querySelectorAll('.advanced-option');
    const uploadForm = document.querySelector('form[action*="upload"]');
    const validationProgressPanel = document.getElementById('validationProgressPanel');
    const validationProgressBar = document.getElementById('validationProgressBar');
    const validationProgressLabel = document.getElementById('validationProgressLabel');
    const validationStatusText = document.getElementById('validationStatusText');
    const validationProgressError = document.getElementById('validationProgressError');
    let validationInProgress = false;
    let activeValidationJobId = null;
    let progressDisplayState = {
        phase: 'idle',
        visualProgress: 0,
        phaseStartedAt: 0,
    };

    function hideValidationError() {
        if (!validationProgressError) {
            return;
        }
        validationProgressError.textContent = '';
        validationProgressError.classList.add('d-none');
    }

    function showValidationError(message) {
        if (!validationProgressError) {
            return;
        }
        validationProgressError.textContent = message;
        validationProgressError.classList.remove('d-none');
    }

    function setProgressPhase(phase, percent) {
        if (progressDisplayState.phase === phase) {
            return;
        }

        progressDisplayState.phase = phase;
        progressDisplayState.phaseStartedAt = Date.now();
        if (Number.isFinite(Number(percent))) {
            progressDisplayState.visualProgress = Math.max(
                progressDisplayState.visualProgress || 0,
                Number(percent) || 0
            );
        }
    }

    function setValidationProgress(percent, message, options = {}) {
        const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
        const animated = options.animated !== false;
        const barText = Object.prototype.hasOwnProperty.call(options, 'barText')
            ? String(options.barText)
            : `${Math.round(safePercent)}%`;
        const labelText = Object.prototype.hasOwnProperty.call(options, 'labelText')
            ? String(options.labelText)
            : `${Math.round(safePercent)}%`;

        if (validationProgressPanel) {
            validationProgressPanel.classList.remove('d-none');
        }

        if (validationProgressBar) {
            validationProgressBar.style.width = `${safePercent}%`;
            validationProgressBar.setAttribute('aria-valuenow', String(Math.round(safePercent)));
            validationProgressBar.textContent = barText;
            validationProgressBar.classList.toggle('progress-bar-striped', animated);
            validationProgressBar.classList.toggle('progress-bar-animated', animated);
        }

        if (validationProgressLabel) {
            validationProgressLabel.textContent = labelText;
        }

        if (validationStatusText) {
            validationStatusText.textContent = message || 'Validating dataset...';
        }
    }

    function restoreValidationButton() {
        validationInProgress = false;
        activeValidationJobId = null;
        progressDisplayState = {
            phase: 'idle',
            visualProgress: 0,
            phaseStartedAt: 0,
        };
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Start Validation';
        }
        updateTargetState();
    }

    function computeDisplayedProgress(payload, progressFloor) {
        const reportedProgress = Number.isFinite(Number(payload.progress))
            ? Number(payload.progress)
            : 0;
        const phase = payload.phase || 'validation';
        const status = payload.status || 'running';
        const baseProgress = Math.max(progressFloor, Math.round(reportedProgress));

        setProgressPhase(phase, baseProgress);

        if (status === 'complete' || status === 'error') {
            progressDisplayState.visualProgress = baseProgress;
            return {
                displayProgress: baseProgress,
                labelText: `${Math.round(baseProgress)}%`,
                barText: `${Math.round(baseProgress)}%`,
                animated: false,
            };
        }

        if (phase === 'bids') {
            const elapsedSeconds = Math.max(
                0,
                (Date.now() - progressDisplayState.phaseStartedAt) / 1000
            );
            const estimatedTarget = Math.min(
                97,
                Math.max(baseProgress, reportedProgress + Math.floor(elapsedSeconds / 4))
            );
            progressDisplayState.visualProgress = Math.max(
                baseProgress,
                progressDisplayState.visualProgress,
                estimatedTarget
            );
            const visualProgress = Math.min(97, progressDisplayState.visualProgress);
            return {
                displayProgress: visualProgress,
                labelText: visualProgress >= 95 ? 'Almost done' : 'Final stage',
                barText: '',
                animated: true,
            };
        }

        progressDisplayState.visualProgress = baseProgress;
        return {
            displayProgress: baseProgress,
            labelText: `${Math.round(baseProgress)}%`,
            barText: `${Math.round(baseProgress)}%`,
            animated: true,
        };
    }

    async function pollValidationProgress(progressUrl, progressFloor = 0) {
        const MAX_POLLS = 4500;

        for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
            await new Promise((resolve) => setTimeout(resolve, 800));

            const response = await fetch(progressUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                cache: 'no-store'
            });
            const payload = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(payload.error || 'Failed to retrieve validation progress.');
            }

            const status = payload.status || 'running';
            const progressUi = computeDisplayedProgress(payload, progressFloor);
            let statusMessage = payload.message || 'Validating dataset...';
            if (payload.phase === 'bids' && status === 'running') {
                statusMessage = 'Running BIDS validator... final phase, progress is estimated.';
            }

            setValidationProgress(progressUi.displayProgress, statusMessage, {
                animated: progressUi.animated,
                barText: progressUi.barText,
                labelText: progressUi.labelText,
            });

            if (status === 'complete') {
                if (payload.redirect_url) {
                    window.location.href = payload.redirect_url;
                    return;
                }
                if (payload.result_id) {
                    window.location.href = `/results/${encodeURIComponent(payload.result_id)}`;
                    return;
                }
                return;
            }

            if (status === 'error') {
                throw new Error(payload.error || payload.message || 'Validation failed.');
            }
        }

        throw new Error('Validation timed out. Please check the application logs and try again.');
    }

    async function startValidationRequest(requestUrl, formData, options = {}) {
        hideValidationError();
        validationInProgress = true;
        activeValidationJobId = null;

        const initialMessage = options.initialMessage || 'Starting validation...';
        const progressFloor = Number.isFinite(Number(options.progressFloor))
            ? Number(options.progressFloor)
            : 0;
        const buttonText = options.buttonText || 'Validating...';

        setValidationProgress(progressFloor, initialMessage, { animated: true });

        if (uploadBtn) {
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${buttonText}`;
        }

        const response = await fetch(requestUrl, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || 'Failed to start validation.');
        }

        if (!payload.progress_url) {
            throw new Error('Validation job did not provide a progress URL.');
        }

        activeValidationJobId = payload.job_id || null;
        await pollValidationProgress(payload.progress_url, progressFloor);
    }

    function renderValidationFailure(message) {
        restoreValidationButton();
        showValidationError(message);
        if (uploadInfo) {
            uploadInfo.textContent = '';
            const icon = document.createElement('i');
            icon.className = 'fas fa-exclamation-triangle me-1 text-danger';
            const text = document.createElement('span');
            text.textContent = message;
            uploadInfo.appendChild(icon);
            uploadInfo.appendChild(text);
        }
    }

    function normalizeProjectPath(pathValue) {
        const trimmed = typeof pathValue === 'string' ? pathValue.trim() : '';
        if (!trimmed) {
            return '';
        }

        // Accept accidental "./Users/..." style values as absolute paths on Unix.
        if (trimmed.startsWith('./Users/')) {
            return `/${trimmed.slice(2)}`;
        }

        // Accept accidental ".\\Users\\..." style values as absolute paths on Unix.
        if (trimmed.startsWith('.\\Users\\')) {
            return `/${trimmed.slice(3).replace(/\\/g, '/')}`;
        }

        // Accept accidental "./C:/..." or ".\\C:\\..." values on Windows.
        if (trimmed.startsWith('./') && /^[A-Za-z]:[\\/]/.test(trimmed.slice(2))) {
            return trimmed.slice(2);
        }
        if (trimmed.startsWith('.\\') && /^[A-Za-z]:[\\/]/.test(trimmed.slice(2))) {
            return trimmed.slice(2);
        }

        // Normalize file URI values from browser/tooling contexts.
        if (trimmed.startsWith('file://')) {
            const uriPayload = trimmed.slice('file://'.length);
            const decoded = decodeURIComponent(uriPayload);

            // file:///C:/Users/... -> C:/Users/...
            if (/^\/[A-Za-z]:\//.test(decoded)) {
                return decoded.slice(1);
            }
            // file://server/share/path (UNC) and Unix absolute forms remain as-is.
            return decoded;
        }

        // Normalize odd Windows absolute form like /C:/Users/... -> C:/Users/...
        if (/^\/[A-Za-z]:\//.test(trimmed)) {
            return trimmed.slice(1);
        }

        return trimmed;
    }

    function resolveCurrentProjectPath() {
        const fromStore = normalizeProjectPath(
            window.prismProjectStateStore
            && typeof window.prismProjectStateStore.getState === 'function'
                ? window.prismProjectStateStore.getState().path
                : ''
        );
        if (fromStore) {
            return fromStore;
        }

        const fromHiddenInput = normalizeProjectPath(currentProjectPathInput && currentProjectPathInput.value);
        if (fromHiddenInput) {
            return fromHiddenInput;
        }

        const fromTargetDataset = normalizeProjectPath(targetCurrentProject && targetCurrentProject.dataset && targetCurrentProject.dataset.projectPath);
        if (fromTargetDataset) {
            return fromTargetDataset;
        }

        const fromBadge = normalizeProjectPath(currentProjectBadge && currentProjectBadge.dataset && currentProjectBadge.dataset.path);
        if (fromBadge) {
            return fromBadge;
        }

        const fromWindow = normalizeProjectPath(window.currentProjectPath);
        if (fromWindow) {
            return fromWindow;
        }

        return '';
    }

    function getSelectedValidationTarget() {
        if (targetOtherFolder && targetOtherFolder.checked) {
            return 'folder';
        }
        if (targetCurrentProject && targetCurrentProject.checked) {
            return 'current';
        }
        return resolveCurrentProjectPath() ? 'current' : 'folder';
    }

    function syncCurrentProjectTargetDetails() {
        const currentPath = resolveCurrentProjectPath();
        const currentName = (window.prismProjectStateStore
            && typeof window.prismProjectStateStore.getState === 'function'
            && typeof window.prismProjectStateStore.getState().name === 'string'
            ? window.prismProjectStateStore.getState().name.trim()
            : (currentProjectNameInput && currentProjectNameInput.value ? currentProjectNameInput.value.trim() : ''));

        if (currentProjectPathInput) {
            currentProjectPathInput.value = currentPath;
        }
        if (currentProjectNameInput && currentName) {
            currentProjectNameInput.value = currentName;
        }
        if (targetCurrentProject) {
            targetCurrentProject.dataset.projectPath = currentPath;
        }

        if (!currentProjectTargetDetails) {
            return;
        }

        if (currentPath) {
            const labelName = currentName || 'Current project';
            currentProjectTargetDetails.textContent = `${labelName} · ${currentPath}`;
            currentProjectTargetDetails.title = currentPath;
            currentProjectTargetDetails.setAttribute('aria-label', currentPath);
            return;
        }

        currentProjectTargetDetails.textContent = 'Current project not selected';
        currentProjectTargetDetails.removeAttribute('title');
        currentProjectTargetDetails.removeAttribute('aria-label');
    }

    function updateTargetState() {
        if (!uploadBtn || !uploadInfo) {
            return;
        }

        if (validationInProgress) {
            uploadBtn.disabled = true;
            return;
        }

        const target = getSelectedValidationTarget();
        const hasFolderSelection = folderInput && folderInput.files && folderInput.files.length > 0;
        const hasCurrentProject = Boolean(resolveCurrentProjectPath());

        if (target === 'current') {
            uploadBtn.disabled = !hasCurrentProject;
            uploadBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Start Validation';

            if (selectedFolderPath) {
                selectedFolderPath.value = hasCurrentProject
                    ? `${(currentProjectNameInput && currentProjectNameInput.value) || 'Current project'} (default target)`
                    : 'No current project selected';
            }

            uploadInfo.innerHTML = hasCurrentProject
                ? '<i class="fas fa-check-circle me-1 text-success"></i>Target: current project (default)'
                : '<i class="fas fa-exclamation-triangle me-1 text-warning"></i>Select another dataset folder to continue';

            if (folderBtn) {
                folderBtn.classList.remove('btn-success');
                folderBtn.classList.add('btn-outline-success');
            }
            return;
        }

        uploadBtn.disabled = !hasFolderSelection;
        uploadBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Start Validation';

        if (!hasFolderSelection) {
            if (selectedFolderPath) {
                selectedFolderPath.value = 'No folder selected';
            }
            uploadInfo.innerHTML = '<i class="fas fa-info-circle me-1 text-muted"></i>Target: another dataset folder (select one to continue)';
            if (folderBtn) {
                folderBtn.classList.remove('btn-success');
                folderBtn.classList.add('btn-outline-success');
            }
        }
    }

    if (targetCurrentProject) {
        targetCurrentProject.addEventListener('change', updateTargetState);
    }
    if (targetOtherFolder) {
        targetOtherFolder.addEventListener('change', updateTargetState);
    }

    // Keep validation target controls in sync when project changes globally.
    window.addEventListener('prism-project-changed', function() {
        syncCurrentProjectTargetDetails();
        updateTargetState();
    });

    syncCurrentProjectTargetDetails();

    function applyAdvancedOptionsState() {
        const enabled = Boolean(advancedOptionsToggle && advancedOptionsToggle.checked);

        advancedOptions.forEach((element) => {
            element.disabled = !enabled;
        });

        if (!enabled) {
            const modeBoth = document.getElementById('mode_both');
            if (modeBoth) {
                modeBoth.checked = true;
            }
        }

        if (schemaVersionSelect) {
            if (!enabled) {
                schemaVersionSelect.value = 'stable';
            }
        }

        if (libraryPathInput) {
            if (!enabled) {
                libraryPathInput.value = '';
            }
        }

        updateBidsOptions();
    }

    if (advancedOptionsToggle) {
        advancedOptionsToggle.addEventListener('change', applyAdvancedOptionsState);
    }
    applyAdvancedOptionsState();

    if (browseLibraryBtn && libraryPathInput) {
        browseLibraryBtn.addEventListener('click', function() {
            fetch('/api/browse-folder')
                .then(r => r.json())
                .then(data => {
                    if (data.path) {
                        libraryPathInput.value = data.path;
                    }
                })
                .catch(err => {
                    console.error('Failed to browse for library folder:', err);
                    alert('Could not open folder browser. Please type the path manually.');
                });
        });
    }

    // Check for webkitdirectory support
    const supportsFolderUpload = 'webkitdirectory' in document.createElement('input');
    
    if (!supportsFolderUpload && browserWarning && folderBtn) {
        browserWarning.style.display = 'block';
        folderBtn.disabled = true;
        folderBtn.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Folder Upload Not Supported';
        folderBtn.classList.add('btn-warning');
        folderBtn.classList.remove('btn-success', 'btn-outline-success');
    }

    if (!folderInput || !folderBtn || !uploadBtn || !uploadInfo || !uploadForm) {
        return;
    }

    // Folder button click
    folderBtn.addEventListener('click', function() {
        if (supportsFolderUpload) {
            if (targetOtherFolder) {
                targetOtherFolder.checked = true;
            }
            updateTargetState();
            folderInput.click();
        } else {
            alert('Folder upload is not supported in this browser. Please use the local folder path option below or try a modern browser like Chrome, Firefox, or Edge.');
        }
    });

    // Drag and drop handling
    if (uploadArea) {
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                if (supportsFolderUpload && files.length > 1) {
                    updateUploadButton('folder', null, files.length);
                } else {
                    uploadInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-1 text-warning"></i>Please use the browse button to select a folder';
                }
            }
        });
    }

    // Folder selection handling
    folderInput.addEventListener('change', function() {
        if (folderInput.files.length > 0) {
            // Filter to metadata files only
            const metadataExtensions = ['.json', '.tsv', '.csv', '.txt'];
            const skipExtensions = ['.nii', '.gz', '.mp4', '.avi', '.mov', '.png', '.jpg', '.jpeg', '.tiff', '.mat', '.eeg', '.dat', '.fif', '.edf', '.bdf', '.set', '.fdt', '.vhdr', '.vmrk', '.bvec', '.bval'];
            
            let metadataCount = 0;
            let skippedCount = 0;
            
            for (let file of folderInput.files) {
                const fileName = file.name;
                const fileNameLower = fileName.toLowerCase();
                
                // Skip system files
                if (fileName === '.bidsignore') {
                    // Include .bidsignore
                } else if (fileName.startsWith('.') || fileName.startsWith('._') || fileName === 'Thumbs.db') {
                    continue;
                }

                const isSkipped = skipExtensions.some(ext => fileNameLower.endsWith(ext));
                const isMetadata = metadataExtensions.some(ext => fileNameLower.endsWith(ext)) || fileName === '.bidsignore';
                
                if (isMetadata) {
                    metadataCount++;
                } else if (isSkipped || fileNameLower.endsWith('.nii.gz')) {
                    skippedCount++;
                }
            }
            
            updateUploadButton('folder', null, metadataCount, skippedCount);
        }
    });

    function updateUploadButton(type, file, fileCount, skippedCount) {
        uploadBtn.disabled = false;
        
        if (type === 'folder') {
            const actualFileCount = fileCount || folderInput.files.length;
            let folderName = 'Selected folder';
            
            if (folderInput.files.length > 0 && folderInput.files[0].webkitRelativePath) {
                folderName = folderInput.files[0].webkitRelativePath.split('/')[0];
            }

            if (selectedFolderPath) {
                selectedFolderPath.value = folderName;
            }

            if (targetOtherFolder) {
                targetOtherFolder.checked = true;
            }
            
            uploadBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Start Validation';
            
            let infoText = `<i class="fas fa-folder me-1 text-success"></i>${actualFileCount} metadata files selected`;
            if (skippedCount > 0) {
                infoText += ` <span class="text-muted">(${skippedCount} data files will be skipped)</span>`;
            }
            uploadInfo.innerHTML = `${infoText} <span class="text-muted">Target: another dataset folder</span>`;
            
            // Highlight folder button
            folderBtn.classList.add('btn-success');
            folderBtn.classList.remove('btn-outline-success');

            updateTargetState();
        }
    }

    // Show loading state on form submission
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault(); // Prevent default submission
        const submitForm = (e.currentTarget && e.currentTarget.tagName === 'FORM')
            ? e.currentTarget
            : uploadForm;
        
        const target = getSelectedValidationTarget();

        // Current project path: submit directly without folder upload
        if (target === 'current') {
            const currentProjectPath = resolveCurrentProjectPath();
            if (currentProjectPath) {
                const validateFolderUrl = (submitForm && submitForm.dataset && submitForm.dataset.validateFolderUrl)
                    ? submitForm.dataset.validateFolderUrl
                    : '/validate_folder';

                const selectedModeRadio = document.querySelector('input[name="validation_mode"]:checked');
                const selectedMode = selectedModeRadio ? selectedModeRadio.value : 'both';

                const schemaVersion = schemaVersionSelect ? schemaVersionSelect.value : 'stable';
                const libraryPath = libraryPathInput ? libraryPathInput.value : '';

                const validationData = new FormData();
                validationData.append('folder_path', currentProjectPath);
                validationData.append('validation_mode', selectedMode);
                validationData.append('schema_version', schemaVersion);
                if (bidsWarningsCheckbox && bidsWarningsCheckbox.checked) {
                    validationData.append('bids_warnings', 'true');
                }
                if (libraryPath) {
                    validationData.append('library_path', libraryPath);
                }

                try {
                    await startValidationRequest(validateFolderUrl, validationData, {
                        initialMessage: 'Starting current project validation...',
                        buttonText: 'Validating current project...'
                    });
                } catch (error) {
                    console.error('Validation error:', error);
                    renderValidationFailure(error.message || 'Current project validation failed.');
                }
                return false;
            }

            alert('No current project is selected. Choose "Validate another dataset folder" and select a folder.');
            return false;
        }

        // Folder target requires folder selection
        if (folderInput.files.length === 0) {
            alert('Please select a folder before validating.');
            return false;
        }

        const form = submitForm;
        const formData = new FormData();
        
        // Add Validation Mode
        const selectedModeRadio = document.querySelector('input[name="validation_mode"]:checked');
        const selectedMode = selectedModeRadio ? selectedModeRadio.value : 'both';
        formData.append('validation_mode', selectedMode);
        
        // Add BIDS options
        if (bidsWarningsCheckbox && bidsWarningsCheckbox.checked) {
            formData.append('bids_warnings', 'true');
        }
        
        // Add Schema Version
        const schemaVersion = schemaVersionSelect ? schemaVersionSelect.value : 'stable';
        formData.append('schema_version', schemaVersion);

        // Show progress
        hideValidationError();
        validationInProgress = true;
        activeValidationJobId = null;
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Preparing upload...';
        setValidationProgress(1, 'Preparing validation package...', { animated: true });
        
        try {
            // Folder upload: Zip client-side
            // This avoids "too many files" errors and reduces upload size
            const zip = new JSZip();
            // ONLY upload content for these files (the actual metadata)
            const metadataExtensions = ['.json', '.tsv', '.csv', '.txt', '.bvec', '.bval', '.vhdr', '.vmrk'];
            // For everything else, we only send the filename (empty content) to validate structure
            const skipExtensions = ['.nii', '.gz', '.mp4', '.avi', '.mov', '.png', '.jpg', '.jpeg', '.tiff', '.mat', '.eeg', '.dat', '.fif', '.edf', '.bdf', '.set', '.fdt'];
            
            let includedCount = 0;
            let skippedCount = 0;
            let totalSize = 0;
            
            uploadInfo.innerHTML = '<i class="fas fa-cog fa-spin me-1"></i>Compressing metadata...';
            
            // Process files in chunks to avoid blocking UI too much
            const files = folderInput.files;
            const totalFiles = files.length;
            
            for (let i = 0; i < totalFiles; i++) {
                // Update progress every 100 files
                if (i % 100 === 0) {
                    uploadInfo.innerHTML = `<i class="fas fa-cog fa-spin me-1"></i>Preparing files (${i}/${totalFiles})...`;
                    const preparationPct = Math.max(1, Math.min(10, Math.round((i / Math.max(totalFiles, 1)) * 10)));
                    setValidationProgress(preparationPct, `Preparing files (${i}/${totalFiles})...`, { animated: true });
                    await new Promise(resolve => setTimeout(resolve, 0));
                }

                const file = files[i];
                const fileName = file.name;
                const fileNameLower = fileName.toLowerCase();
                const filePath = file.webkitRelativePath || fileName;
                
                // Keep .bidsignore as it's critical for validation
                // Skip other system files (macOS .DS_Store, ._ files, etc.)
                if (fileName === '.bidsignore') {
                    // Continue to process as metadata below
                } else if (fileName.startsWith('.') || fileName.startsWith('._') || fileName === 'Thumbs.db') {
                    continue;
                }

                const isMetadata = metadataExtensions.some(ext => fileNameLower.endsWith(ext)) || fileName === '.bidsignore';
                const isSkipped = skipExtensions.some(ext => fileNameLower.endsWith(ext)) || fileNameLower.endsWith('.nii.gz');
                
                if (isMetadata && !isSkipped) {
                    try {
                        // Read file content to ensure it's readable and avoid lazy read errors in generateAsync
                        // This also helps identify exactly which file is failing
                        const content = await file.arrayBuffer();
                        zip.file(filePath, content);
                        includedCount++;
                        totalSize += file.size;
                    } catch (readError) {
                        console.warn(`Could not read file ${filePath}:`, readError);
                        // Add a placeholder instead of failing the whole upload
                        zip.file(filePath, `# ERROR: Could not read file content during upload\n# Original size: ${file.size}\n# Error: ${readError.message}`);
                        includedCount++;
                    }
                } else if (isSkipped) {
                    // Add empty placeholder for skipped files
                    zip.file(filePath, "");
                    skippedCount++;
                }
            }
            
            if (includedCount === 0 && skippedCount === 0) {
                throw new Error('No valid files found in the selected folder.');
            }
            
            uploadInfo.innerHTML = `<i class="fas fa-cog fa-spin me-1"></i>Uploading ${includedCount} metadata files (zipped)...`;
            setValidationProgress(12, `Uploading ${includedCount} metadata files...`, { animated: true });
            
            const zipBlob = await zip.generateAsync({type: "blob"});
            formData.append('dataset', zipBlob, "dataset.zip");

            await startValidationRequest(form.action, formData, {
                initialMessage: `Uploading ${includedCount} metadata files...`,
                buttonText: 'Validating uploaded dataset...',
                progressFloor: 12
            });
            
        } catch (error) {
            console.error('Upload error:', error);
            renderValidationFailure(`Upload failed: ${error.message}`);
        }
        
        return false;
    });

    updateTargetState();

    // Show browser compatibility info
    if (!supportsFolderUpload) {
        console.log('Browser does not support folder upload. webkitdirectory not available.');
    }
});
