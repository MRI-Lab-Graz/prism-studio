// File upload handling
document.addEventListener('DOMContentLoaded', function() {
    // Validation Mode Toggles
    const modeRadios = document.querySelectorAll('input[name="validation_mode"]');
    const bidsOptions = document.getElementById('bids_options');
    
    function updateBidsOptions() {
        const selectedMode = document.querySelector('input[name="validation_mode"]:checked').value;
        if (bidsOptions) {
            bidsOptions.style.display = (selectedMode === 'both' || selectedMode === 'bids') ? 'block' : 'none';
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
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadInfo = document.getElementById('uploadInfo');
    const browserWarning = document.getElementById('browserWarning');
    const browseLibraryBtn = document.getElementById('browseLibraryBtn');
    const libraryPathInput = document.getElementById('library_path');

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
    
    if (!supportsFolderUpload) {
        browserWarning.style.display = 'block';
        folderBtn.disabled = true;
        folderBtn.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Folder Upload Not Supported';
        folderBtn.classList.add('btn-warning');
        folderBtn.classList.remove('btn-success');
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
            // For folder drops, we need to simulate the file input
            if (supportsFolderUpload && files.length > 1) {
                // Multiple files dropped - treat as folder
                updateUploadButton('folder', null, files.length);
            } else {
                uploadInfo.innerHTML = '<i class="fas fa-exclamation-triangle me-1 text-warning"></i>Please use the browse button to select a folder';
            }
        }
    });

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
    document.querySelector('form[action*="upload"]').addEventListener('submit', async function(e) {
        e.preventDefault(); // Prevent default submission
        
        // Validate that something is selected
        if (folderInput.files.length === 0) {
            alert('Please select a folder before validating.');
            return false;
        }
        
        const form = e.target;
        const formData = new FormData();
        
        // Add Validation Mode
        const selectedMode = document.querySelector('input[name="validation_mode"]:checked').value;
        formData.append('validation_mode', selectedMode);
        
        // Add BIDS options
        const bidsWarningsCheckbox = document.getElementById('bids_warnings');
        if (bidsWarningsCheckbox && bidsWarningsCheckbox.checked) {
            formData.append('bids_warnings', 'true');
        }
        
        // Add Schema Version
        const schemaVersion = document.getElementById('schema_version').value;
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

    document.querySelector('form[action*="validate_folder"]').addEventListener('submit', function(e) {
        const submitBtn = e.target.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Validating...';
    });

    // Show browser compatibility info
    if (!supportsFolderUpload) {
        console.log('Browser does not support folder upload. webkitdirectory not available.');
    }
});
