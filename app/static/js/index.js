// File upload handling
document.addEventListener('DOMContentLoaded', function() {
    // Validation Mode Toggles
    const modeRadios = document.querySelectorAll('input[name="validation_mode"]');
    const bidsOptions = document.getElementById('bids_options');
    const bidsWarningsCheckbox = document.getElementById('bids_warnings');
    const advancedOptionsToggle = document.getElementById('advancedOptionsToggle');
    const currentProjectPathInput = document.getElementById('currentProjectPath');
    
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
    const validateFolderForm = document.querySelector('form[action*="validate_folder"]');

    if (currentProjectPathInput && currentProjectPathInput.value && currentProjectPathInput.value.trim()) {
        if (selectedFolderPath && selectedFolderPath.value === 'No folder selected') {
            selectedFolderPath.value = currentProjectPathInput.value.trim();
        }
        if (uploadBtn) {
            uploadBtn.disabled = false;
        }
        if (uploadInfo && !uploadInfo.textContent.trim()) {
            uploadInfo.innerHTML = '<i class="fas fa-check-circle me-1 text-success"></i>Current project selected by default';
        }
    }

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
            
            uploadBtn.innerHTML = `<i class="fas fa-check-circle me-2"></i>Validate Folder "${folderName}"`;
            
            let infoText = `<i class="fas fa-folder me-1 text-success"></i>${actualFileCount} metadata files selected`;
            if (skippedCount > 0) {
                infoText += ` <span class="text-muted">(${skippedCount} data files will be skipped)</span>`;
            }
            uploadInfo.innerHTML = infoText;
            
            // Highlight folder button
            folderBtn.classList.add('btn-success');
            folderBtn.classList.remove('btn-outline-success');
        }
    }

    // Show loading state on form submission
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault(); // Prevent default submission
        
        // Validate that something is selected
        if (folderInput.files.length === 0) {
            const currentProjectPath = currentProjectPathInput && currentProjectPathInput.value
                ? currentProjectPathInput.value.trim()
                : '';
            if (currentProjectPath) {
                const validateFolderUrl = e.target.dataset.validateFolderUrl;
                if (validateFolderUrl) {
                    const selectedModeRadio = document.querySelector('input[name="validation_mode"]:checked');
                    const selectedMode = selectedModeRadio ? selectedModeRadio.value : 'both';

                    const schemaVersion = schemaVersionSelect ? schemaVersionSelect.value : 'stable';
                    const libraryPath = libraryPathInput ? libraryPathInput.value : '';

                    const quickForm = document.createElement('form');
                    quickForm.method = 'POST';
                    quickForm.action = validateFolderUrl;

                    const appendHidden = (name, value) => {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = name;
                        input.value = value;
                        quickForm.appendChild(input);
                    };

                    appendHidden('folder_path', currentProjectPath);
                    appendHidden('validation_mode', selectedMode);
                    appendHidden('schema_version', schemaVersion);
                    if (bidsWarningsCheckbox && bidsWarningsCheckbox.checked) {
                        appendHidden('bids_warnings', 'true');
                    }
                    if (libraryPath) {
                        appendHidden('library_path', libraryPath);
                    }

                    if (uploadBtn) {
                        uploadBtn.disabled = true;
                        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Validating current project...';
                    }

                    document.body.appendChild(quickForm);
                    quickForm.submit();
                    return false;
                }
            }

            alert('Please select a folder before validating.');
            return false;
        }
        
        const form = e.target;
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
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Preparing upload...';
        
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
            
            console.log(`Zipping ${includedCount} metadata files, skipping ${skippedCount} data files`);
            uploadInfo.innerHTML = `<i class="fas fa-cog fa-spin me-1"></i>Uploading ${includedCount} metadata files (zipped)...`;
            
            const zipBlob = await zip.generateAsync({type: "blob"});
            formData.append('dataset', zipBlob, "dataset.zip");
            
            // Submit via fetch
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData
            });
            
            if (response.redirected) {
                window.location.href = response.url;
            } else {
                const text = await response.text();
                throw new Error(text);
            }
            
        } catch (error) {
            console.error('Upload error:', error);
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-check-circle me-2"></i>Validate Dataset';
            uploadInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-1 text-danger"></i>Upload failed: ' + error.message;
            alert('Upload failed: ' + error.message);
        }
        
        return false;
    });

    if (validateFolderForm) {
        validateFolderForm.addEventListener('submit', function(e) {
            const submitBtn = e.target.querySelector('button[type="submit"]');
            if (!submitBtn) return;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Validating...';
        });
    }

    // Show browser compatibility info
    if (!supportsFolderUpload) {
        console.log('Browser does not support folder upload. webkitdirectory not available.');
    }
});
