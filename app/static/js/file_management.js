document.addEventListener('DOMContentLoaded', () => {
    // Shared helpers
    function downloadBase64Zip(base64Data, filename) {
        const binaryString = window.atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: 'application/zip' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    }

    // --------------------
    // Batch Organizer
    // --------------------
    const organizeFiles = document.getElementById('organizeFiles');
    const organizeModality = document.getElementById('organizeModality');
    const organizeDryRunBtn = document.getElementById('organizeDryRunBtn');
    const organizeCopyBtn = document.getElementById('organizeCopyBtn');
    const organizeError = document.getElementById('organizeError');
    const organizeInfo = document.getElementById('organizeInfo');
    const organizeProgress = document.getElementById('organizeProgress');
    const organizeLogContainer = document.getElementById('organizeLogContainer');
    const organizeLog = document.getElementById('organizeLog');
    const organizeLogClearBtn = document.getElementById('organizeLogClearBtn');
    const organizeFolder = document.getElementById('organizeFolder');
    const organizeFlatStructure = document.getElementById('organizeFlatStructure');
    const organizeTargetRaw = document.getElementById('organizeTargetRaw');
    const organizeTargetSource = document.getElementById('organizeTargetSource');
    const flatStructureHint = document.getElementById('flatStructureHint');
    
    const organizeTargetRoot = () => {
        const checked = document.querySelector('input[name="organizeTargetRoot"]:checked');
        return checked ? checked.value : 'rawdata';
    };

    // Update flat structure hint and auto-suggest based on destination
    function updateFlatStructureHint() {
        const isSourcedata = organizeTargetRoot() === 'sourcedata';
        if (flatStructureHint) {
            flatStructureHint.textContent = isSourcedata 
                ? 'Recommended for sourcedata' 
                : 'Use PRISM structure for rawdata';
            flatStructureHint.className = isSourcedata ? 'text-success' : 'text-muted';
        }
        // Auto-enable flat for sourcedata (but allow user to override)
        if (organizeFlatStructure && isSourcedata && !organizeFlatStructure.checked) {
            organizeFlatStructure.checked = true;
        }
    }

    if (organizeTargetRaw) {
        organizeTargetRaw.addEventListener('change', updateFlatStructureHint);
    }
    if (organizeTargetSource) {
        organizeTargetSource.addEventListener('change', updateFlatStructureHint);
    }
    updateFlatStructureHint();

    function getOrganizeFiles() {
        const fileList = [];
        if (organizeFiles && organizeFiles.files) {
            fileList.push(...Array.from(organizeFiles.files));
        }
        if (organizeFolder && organizeFolder.files) {
            fileList.push(...Array.from(organizeFolder.files));
        }
        return fileList;
    }

    function updateOrganizeBtn() {
        const hasFiles = getOrganizeFiles().length > 0;
        if (organizeDryRunBtn) organizeDryRunBtn.disabled = !hasFiles;
        if (organizeCopyBtn) organizeCopyBtn.disabled = !hasFiles;
    }

    if (organizeFiles) {
        organizeFiles.addEventListener('change', updateOrganizeBtn);
        updateOrganizeBtn();
    }

    if (organizeFolder) {
        organizeFolder.addEventListener('change', updateOrganizeBtn);
        updateOrganizeBtn();
    }

    if (organizeLogClearBtn) {
        organizeLogClearBtn.addEventListener('click', () => {
            if (organizeLog) organizeLog.textContent = '';
        });
    }

    async function runOrganizer(opts = {}) {
        const saveToProject = opts.saveToProject === true;
        const skipDownload = opts.skipDownload === true;
        const dryRun = opts.dryRun === true;
        if (!organizeFiles) return;
        if (organizeError) organizeError.classList.add('d-none');
        if (organizeInfo) organizeInfo.classList.add('d-none');
        if (organizeProgress) organizeProgress.classList.remove('d-none');
        if (organizeLogContainer) organizeLogContainer.classList.remove('d-none');
        if (organizeLog) organizeLog.textContent = '';
        if (organizeDryRunBtn) organizeDryRunBtn.disabled = true;
        if (organizeCopyBtn) organizeCopyBtn.disabled = true;

        const files = getOrganizeFiles();
        const modality = organizeModality ? organizeModality.value : 'anat';
        const destRoot = organizeTargetRoot();
        const flatStructure = document.getElementById('organizeFlatStructure')?.checked || false;
        const datasetName = 'Organized Dataset';

        const formData = new FormData();
        files.forEach(f => formData.append('files', f));
        formData.append('dataset_name', datasetName);
        formData.append('modality', modality);
        formData.append('save_to_project', saveToProject);
        formData.append('dest_root', destRoot);
        formData.append('flat_structure', flatStructure);
        formData.append('dry_run', dryRun);

        try {
            const response = await fetch('/api/batch-convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const data = await response.json().catch(() => null);
                throw new Error(data && data.error ? data.error : 'Organization failed');
            }

            const result = await response.json();

            // Display logs
            if (result.logs && organizeLog) {
                const logText = result.logs.map(l => l.message).join('\n');
                organizeLog.textContent = logText;
            }

            if (result.dry_run) {
                if (organizeInfo) {
                    const newCount = result.new_files || 0;
                    const existingCount = result.existing_files || 0;
                    organizeInfo.innerHTML = `<i class="fas fa-check-circle me-2 text-success"></i>Dry run complete: ${result.converted || 0} files would be organized.<br>📄 <strong>New:</strong> ${newCount} · 📋 <strong>Existing (will overwrite):</strong> ${existingCount}<br>Review the log above, then click "Copy to Project" to execute.`;
                    organizeInfo.classList.remove('d-none');
                }
            } else {
                const warnings = result.warnings || [];
                if (warnings.length && organizeError) {
                    organizeError.innerHTML = warnings.map(w => `<div><i class="fas fa-exclamation-triangle me-2"></i>${w}</div>`).join('');
                    organizeError.classList.remove('d-none');
                }

                if (organizeInfo) {
                    const savedText = result.project_saved ? ' Copied to project.' : '';
                    const zipText = skipDownload ? '' : ' ZIP download started.';
                    organizeInfo.textContent = `Organized ${result.converted || 0} files. ${result.errors || 0} errors.${savedText}${zipText}`.trim();
                    organizeInfo.classList.remove('d-none');
                }
            }
        } catch (err) {
            if (organizeError) {
                organizeError.textContent = err.message;
                organizeError.classList.remove('d-none');
            }
        } finally {
            if (organizeProgress) organizeProgress.classList.add('d-none');
            updateOrganizeBtn();
        }
    }

    if (organizeDryRunBtn) {
        organizeDryRunBtn.addEventListener('click', () => runOrganizer({ dryRun: true }));
    }

    if (organizeCopyBtn) {
        organizeCopyBtn.addEventListener('click', () => runOrganizer({ saveToProject: true, skipDownload: true }));
    }

    // --------------------
    // Renamer Helper
    // --------------------
    const renamerFiles = document.getElementById('renamerFiles');
    const renamerPattern = document.getElementById('renamerPattern');
    const renamerReplacement = document.getElementById('renamerReplacement');
    const renamerNewExample = document.getElementById('renamerNewExample');
    const renamerModality = document.getElementById('renamerModality');
    const renamerRecording = document.getElementById('renamerRecording');
    const renamerRecordingContainer = document.getElementById('renamerRecordingContainer');
    const renamerExampleHint = document.getElementById('renamerExampleHint');
    const renamerExampleContainer = document.getElementById('renamerExampleContainer');
    const renamerOriginalExample = document.getElementById('renamerOriginalExample');
    const renamerPreview = document.getElementById('renamerPreview');
    const renamerPreviewBody = document.getElementById('renamerPreviewBody');
    const renamerFilterAll = document.getElementById('renamerFilterAll');
    const renamerFilterUnmatched = document.getElementById('renamerFilterUnmatched');
    const renamerError = document.getElementById('renamerError');
    const renamerInfo = document.getElementById('renamerInfo');
    const renamerOrganize = document.getElementById('renamerOrganize');
    const renamerResetBtn = document.getElementById('renamerResetBtn');
    const renamerDryRunBtn = document.getElementById('renamerDryRunBtn');
    const renamerDownloadBtn = document.getElementById('renamerDownloadBtn');
    const renamerCopyBtn = document.getElementById('renamerCopyBtn');
    const renamerUseMapping = document.getElementById('renamerUseMapping');
    const renamerMappingFields = document.getElementById('renamerMappingFields');
    const renamerSubjectValue = document.getElementById('renamerSubjectValue');
    const renamerSessionValue = document.getElementById('renamerSessionValue');
    const renamerMappingPreview = document.getElementById('renamerMappingPreview');
    const renamerTargetRaw = document.getElementById('renamerTargetRaw');
    const renamerTargetSource = document.getElementById('renamerTargetSource');
    const renamerStructureHint = document.getElementById('renamerStructureHint');

    const renamerTargetRoot = () => {
        const checked = document.querySelector('input[name="renamerTargetRoot"]:checked');
        return checked ? checked.value : 'rawdata';
    };

    // Update structure hint based on destination
    function updateRenamerStructureHint() {
        const isSourcedata = renamerTargetRoot() === 'sourcedata';
        if (renamerStructureHint) {
            if (renamerOrganize && !renamerOrganize.checked) {
                renamerStructureHint.textContent = isSourcedata 
                    ? 'Flat structure (recommended for sourcedata)' 
                    : 'Flat structure';
                renamerStructureHint.className = isSourcedata ? 'text-success' : 'text-muted';
            } else {
                renamerStructureHint.textContent = 'Creates sub-XX/ses-YY/modality/ folders';
                renamerStructureHint.className = 'text-muted';
            }
        }
    }

    let currentExampleFile = null;

    const modalityHints = {
        physio: 'sub-001_task-rest_physio.edf',
        biometrics: 'sub-001_biometrics-height_biometrics.tsv',
        events: 'sub-001_task-rest_events.tsv',
        survey: 'sub-001_survey-phq9_survey.tsv'
    };

    function updateRecordingVisibility() {
        if (!renamerModality || !renamerRecordingContainer) return;
        const showRecording = renamerModality.value === 'physio';
        renamerRecordingContainer.style.display = showRecording ? 'block' : 'none';
    }

    function updateHintFromModality() {
        if (!renamerModality) return;
        const mod = renamerModality.value;
        let hint = modalityHints[mod] || modalityHints.physio;
        if (mod === 'physio' && renamerRecording && renamerRecording.value) {
            hint = `sub-001_task-rest_recording-${renamerRecording.value}_physio.edf`;
        }
        if (renamerExampleHint) renamerExampleHint.innerHTML = `Example: <code>${hint}</code>`;
        if (renamerNewExample) {
            renamerNewExample.placeholder = `e.g. ${hint}`;
            // Auto-update the filename with correct suffix if user already has input
            if (renamerNewExample.value.trim()) {
                autoAppendModalitySuffix();
            }
        }
    }

    function autoAppendModalitySuffix() {
        if (!renamerNewExample || !renamerModality) return;
        
        const currentValue = renamerNewExample.value.trim();
        if (!currentValue) return;

        const mod = renamerModality.value;
        const rec = (mod === 'physio' && renamerRecording && renamerRecording.value) ? renamerRecording.value : '';
        
        // Build the required suffix
        let requiredSuffix = '';
        if (mod === 'physio' && rec) {
            requiredSuffix = `recording-${rec}_physio`;
        } else {
            requiredSuffix = mod;
        }

        // Extract the extension
        const lastDot = currentValue.lastIndexOf('.');
        let baseName = currentValue;
        let ext = '';
        if (lastDot > -1) {
            baseName = currentValue.substring(0, lastDot);
            ext = currentValue.substring(lastDot);
        }

        // Remove any existing modality suffix or recording label
        const suffixPattern = /_(recording-[a-z0-9]+_)?(physio|biometrics|events|survey)$/i;
        baseName = baseName.replace(suffixPattern, '');

        // Append the new suffix
        const newValue = `${baseName}_${requiredSuffix}${ext}`;
        renamerNewExample.value = newValue;
    }

    function updateRenamerBtn() {
        const hasFiles = renamerFiles && renamerFiles.files && renamerFiles.files.length > 0;
        const hasNewName = renamerNewExample && renamerNewExample.value.trim().length > 0;
        const disabled = !hasFiles || !hasNewName;
        if (renamerDownloadBtn) renamerDownloadBtn.disabled = disabled;
        if (renamerCopyBtn) renamerCopyBtn.disabled = disabled;
        if (renamerDryRunBtn) renamerDryRunBtn.disabled = disabled;
    }

    function updateMappingVisibility() {
        if (!renamerMappingFields || !renamerUseMapping) return;
        renamerMappingFields.style.display = renamerUseMapping.checked ? '' : 'none';
        if (renamerMappingPreview && !renamerUseMapping.checked) {
            renamerMappingPreview.textContent = '';
            renamerMappingPreview.classList.remove('text-danger');
            renamerMappingPreview.classList.add('text-muted');
        }
    }

    function sanitizeLiteral(value) {
        if (!value) return '';
        let cleaned = value.trim();
        // Remove wrapper brackets/parentheses
        if ((cleaned.startsWith('{') && cleaned.endsWith('}')) || (cleaned.startsWith('(') && cleaned.endsWith(')'))) {
            cleaned = cleaned.slice(1, -1).trim();
        }
        // Remove zero-width characters, non-breaking spaces, and other invisible Unicode characters
        cleaned = cleaned
            .replace(/[\u200B\u200C\u200D\uFEFF]/g, '') // Zero-width characters
            .replace(/[\u00A0]/g, ' ') // Non-breaking space to regular space
            .replace(/[\u200E\u200F]/g, '') // Directional marks
            .replace(/[\u202A-\u202E]/g, '') // Bidirectional formatting
            .trim();
        return cleaned;
    }

    function pickExampleFile() {
        if (!renamerFiles || !renamerFiles.files || renamerFiles.files.length === 0) return;
        const files = Array.from(renamerFiles.files);
        currentExampleFile = files[Math.floor(Math.random() * files.length)];
        if (renamerOriginalExample) renamerOriginalExample.textContent = currentExampleFile.name;
        if (renamerExampleContainer) renamerExampleContainer.classList.remove('d-none');
        if (renamerNewExample) {
            renamerNewExample.value = '';
            renamerNewExample.focus();
        }
        updateRenamerBtn();
        if (renamerPreview) renamerPreview.classList.add('d-none');
    }

    function filterRenamerTable(showOnlyUnmatched) {
        if (!renamerPreviewBody) return;
        const rows = renamerPreviewBody.querySelectorAll('tr');
        rows.forEach(row => {
            const isMatch = row.getAttribute('data-match') === 'true';
            if (showOnlyUnmatched) {
                row.classList.toggle('d-none', isMatch);
            } else {
                row.classList.remove('d-none');
            }
        });
        if (renamerFilterAll) renamerFilterAll.classList.toggle('active', !showOnlyUnmatched);
        if (renamerFilterUnmatched) renamerFilterUnmatched.classList.toggle('active', showOnlyUnmatched);
    }

    function inferPattern() {
        if (!currentExampleFile || !renamerNewExample) return;
        const oldName = currentExampleFile.name;
        const newName = renamerNewExample.value.trim();
        if (!newName) {
            if (renamerPreview) renamerPreview.classList.add('d-none');
            return;
        }

        if (renamerUseMapping && renamerUseMapping.checked) {
            if (renamerError) renamerError.classList.add('d-none');
            const subjectValue = sanitizeLiteral(renamerSubjectValue && renamerSubjectValue.value || '');
            const sessionValue = sanitizeLiteral(renamerSessionValue && renamerSessionValue.value || '');

            if (!subjectValue) {
                if (renamerError) {
                    renamerError.textContent = 'Subject string is required when subject/session mapping is enabled.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Enter the subject string from the example filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            if (!newName.includes('{subject}')) {
                if (renamerError) {
                    renamerError.textContent = 'Use {subject} in the New PRISM Filename when subject/session mapping is enabled.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Add {subject} to the New PRISM Filename to insert the subject string.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            if (!sessionValue && newName.includes('{session}')) {
                if (renamerError) {
                    renamerError.textContent = 'Remove {session} from the New PRISM Filename or provide a session string.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Either enter a session string or remove {session} from the new filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const subjectIdx = oldName.indexOf(subjectValue);
            const sessionIdx = sessionValue ? oldName.indexOf(sessionValue) : -1;

            if (subjectIdx < 0) {
                // Try to be helpful - maybe there's a copy-paste issue
                const debugMsg = `"${subjectValue}" (${[...subjectValue].map(c => c.charCodeAt(0)).join(',')}) not in "${oldName}"`;
                if (renamerError) {
                    renamerError.textContent = `Subject string not found. Try manually selecting it from the filename, or clear and retype it.`;
                    renamerError.classList.remove('d-none');
                    renamerError.title = debugMsg; // Hover shows debug info
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = `Subject string not found in the example filename.`;
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                    renamerMappingPreview.title = debugMsg;
                }
                return;
            }

            if (sessionValue && sessionIdx < 0) {
                if (renamerError) {
                    renamerError.textContent = 'Session string was not found in the example filename.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Session string not found in the example filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            if (sessionValue && sessionIdx === subjectIdx) {
                if (renamerError) {
                    renamerError.textContent = 'Subject and session strings overlap in the example filename.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Subject and session strings overlap in the example filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            // Build markers with positions
            const markers = [];
            if (sessionValue) markers.push({ key: 'session', value: sessionValue, index: sessionIdx });
            markers.push({ key: 'subject', value: subjectValue, index: subjectIdx });
            markers.sort((a, b) => a.index - b.index);

            // Create pattern by replacing each marker with capture groups
            // Use lookahead to constrain non-greedy matches when followed by another known marker
            let pattern = '^';
            let cursor = 0;
            markers.forEach((marker, idx) => {
                // Add literal text before this marker
                pattern += escapeRegex(oldName.slice(cursor, marker.index));
                
                // For the capture group: if there's another marker after this one,
                // use lookahead to stop before it. Otherwise use greedy match.
                if (idx < markers.length - 1) {
                    const nextMarker = markers[idx + 1];
                    const nextMarkerEscaped = escapeRegex(nextMarker.value);
                    // Match anything up to (but not including) the next marker
                    pattern += `(.+?)(?=${nextMarkerEscaped})`;
                } else {
                    // Last marker - match to end of meaningful content
                    pattern += '(.+)';
                }
                cursor = marker.index + marker.value.length;
            });
            // Add literal text after last marker (usually file extension)
            const remaining = oldName.slice(cursor);
            if (remaining) {
                pattern += escapeRegex(remaining);
            }
            pattern += '$';

            // Map marker keys to their capture group indices (1-based)
            const subjectGroupIndex = markers.findIndex(m => m.key === 'subject') + 1;
            const sessionGroupIndex = sessionValue ? markers.findIndex(m => m.key === 'session') + 1 : 0;

            let replacement = newName.replace(/\{subject\}/g, `\\${subjectGroupIndex}`);
            if (sessionValue) {
                replacement = replacement.replace(/\{session\}/g, `\\${sessionGroupIndex}`);
            }

            if (renamerPattern) renamerPattern.value = pattern;
            if (renamerReplacement) renamerReplacement.value = replacement;
            if (renamerMappingPreview) {
                try {
                    const re = new RegExp(pattern);
                    const previewName = oldName.replace(re, replacement);
                    renamerMappingPreview.textContent = `Preview: ${oldName} → ${previewName}`;
                    renamerMappingPreview.classList.remove('text-danger');
                    renamerMappingPreview.classList.add('text-muted');
                } catch {
                    renamerMappingPreview.textContent = 'Mapping pattern could not be created for this example.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
            }
            runRenamer(true);
            return;
        }

        const digitRegex = /\d+/g;
        const matches = [];
        let match;
        while ((match = digitRegex.exec(oldName)) !== null) {
            matches.push({ value: match[0], index: match.index });
        }

        let finalPattern = '';
        let lastIndex = 0;
        matches.forEach(m => {
            finalPattern += oldName.substring(lastIndex, m.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            finalPattern += '(\\d+)';
            lastIndex = m.index + m.value.length;
        });
        finalPattern += oldName.substring(lastIndex).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

        let replacement = newName;
        if (matches.length > 0) {
            const uniqueValues = [...new Set(matches.map(m => m.value))].sort((a, b) => b.length - a.length);
            const valueToGroup = {};
            matches.forEach((m, i) => {
                if (!(m.value in valueToGroup)) {
                    valueToGroup[m.value] = i + 1;
                }
            });
            const combinedRegex = new RegExp(uniqueValues.map(v => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
            replacement = replacement.replace(combinedRegex, matched => `\\${valueToGroup[matched]}`);
        }

        if (renamerPattern) renamerPattern.value = finalPattern;
        if (renamerReplacement) renamerReplacement.value = replacement;
        runRenamer(true);
    }

    async function runRenamer(isDryRun, opts = {}) {
        const saveToProject = opts.saveToProject === true;
        const skipDownload = opts.skipDownload === true;
        if (!renamerPattern || !renamerReplacement || !renamerPattern.value) return;
        if (!renamerFiles || !renamerFiles.files) return;

        if (renamerError) renamerError.classList.add('d-none');
        if (renamerInfo) renamerInfo.classList.add('d-none');

        const formData = new FormData();
        formData.append('pattern', renamerPattern.value);
        formData.append('replacement', renamerReplacement.value);
        formData.append('dry_run', isDryRun);
        if (renamerOrganize) formData.append('organize', renamerOrganize.checked);
        formData.append('save_to_project', saveToProject);
        if (renamerModality) formData.append('modality', renamerModality.value);
        formData.append('dest_root', renamerTargetRoot());
        formData.append('flat_structure', renamerOrganize ? !renamerOrganize.checked : false);

        const files = Array.from(renamerFiles.files);
        if (files.length === 0 && !isDryRun) return;

        if (isDryRun) {
            files.forEach(f => formData.append('filenames', f.name));
        } else {
            files.forEach(f => formData.append('files', f));
        }

        try {
            const response = await fetch('/api/physio-rename', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                throw new Error(data && data.error ? data.error : 'Renaming failed');
            }
            const result = await response.json();

            if (isDryRun) {
                if (!renamerPreviewBody) return;
                renamerPreviewBody.innerHTML = '';
                let matchCount = 0;
                const selectedModality = renamerModality ? renamerModality.value : 'physio';

                result.results.forEach(res => {
                    const isMatch = res.old !== res.new;
                    let isValidBids = true;
                    let bidsError = '';

                    if (isMatch) {
                        if (!res.new.startsWith('sub-')) {
                            isValidBids = false;
                            bidsError = 'Missing sub- prefix';
                        } else if (!res.new.includes('_')) {
                            isValidBids = false;
                            bidsError = 'Missing entities/suffix';
                        } else {
                            const lastDot = res.new.lastIndexOf('.');
                            const stem = lastDot > -1 ? res.new.slice(0, lastDot) : res.new;
                            const suffix = stem.split('_').pop();
                            const expectedSuffixes = {
                                physio: 'physio',
                                biometrics: 'biometrics',
                                events: 'events',
                                survey: 'survey'
                            };
                            if (expectedSuffixes[selectedModality] && suffix !== expectedSuffixes[selectedModality]) {
                                isValidBids = false;
                                bidsError = `Expected _${expectedSuffixes[selectedModality]} suffix`;
                            }
                        }
                    }

                    if (isMatch && isValidBids) {
                        matchCount++;
                    }

                    const tr = document.createElement('tr');
                    tr.setAttribute('data-match', isMatch && isValidBids);

                    let displayNew = res.new;
                    if (res.path && res.path !== res.new) {
                        displayNew = `<span class="text-muted">${res.path.substring(0, res.path.lastIndexOf('/') + 1)}</span>${res.new}`;
                    }

                    tr.innerHTML = `
                        <td class="font-monospace small">${res.old}</td>
                        <td><i class="fas fa-arrow-right text-muted"></i></td>
                        <td class="font-monospace small ${isMatch ? (isValidBids ? 'text-success' : 'text-danger') : 'text-muted'}">
                            ${displayNew}
                            ${!isValidBids && isMatch ? `<br><small class="text-danger"><i class="fas fa-times-circle me-1"></i>${bidsError}</small>` : ''}
                        </td>
                        <td class="text-center">
                            ${(isMatch && isValidBids) ? '<i class="fas fa-check-circle text-success"></i>' : (!isMatch ? '<i class="fas fa-exclamation-triangle text-warning" title="No match found - file will not be renamed"></i>' : '<i class="fas fa-times-circle text-danger" title="Invalid BIDS/PRISM format"></i>')}
                        </td>
                    `;
                    renamerPreviewBody.appendChild(tr);
                });
                if (renamerPreview) renamerPreview.classList.remove('d-none');

                if (result.results && matchCount < result.results.length && result.results.length > 0 && renamerError) {
                    const unmatchedCount = result.results.length - matchCount;
                    renamerError.innerHTML = `
                        <div class="d-flex align-items-center">
                            <i class="fas fa-exclamation-triangle me-3 fa-2x"></i>
                            <div>
                                <strong>Warning: ${unmatchedCount} files are either unmatched or invalid.</strong><br>
                                Only files with a green checkmark will be renamed correctly. Check the "New PRISM Filename" column for errors.
                                <div class="mt-2">
                                    <button type="button" class="btn btn-sm btn-outline-danger" id="renamerShowIssues">
                                        <i class="fas fa-search me-1"></i>Show Incompatible Files
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    renamerError.classList.remove('d-none');
                    const showIssuesBtn = document.getElementById('renamerShowIssues');
                    if (showIssuesBtn && renamerFilterUnmatched) {
                        showIssuesBtn.addEventListener('click', () => renamerFilterUnmatched.click());
                    }
                }
                filterRenamerTable(false);
            } else {
                const warnings = result.warnings || [];
                const saved = result.project_saved === true;

                if (!skipDownload && result.zip) {
                    downloadBase64Zip(result.zip, 'renamed_files.zip');
                }

                if (renamerInfo) {
                    const warnText = warnings.length ? ` Warnings: ${warnings.join(' ')}` : '';
                    const savedText = saved ? ' Copied to project.' : '';
                    const zipText = skipDownload ? '' : ' ZIP download started.';
                    renamerInfo.textContent = `Successfully renamed ${result.results.length} files.${savedText}${zipText}${warnText}`.trim();
                    renamerInfo.classList.remove('d-none');
                }

                if (warnings.length && renamerError) {
                    renamerError.innerHTML = warnings.map(w => `<div><i class="fas fa-exclamation-triangle me-2"></i>${w}</div>`).join('');
                    renamerError.classList.remove('d-none');
                }
            }
        } catch (err) {
            if (!isDryRun && renamerError) {
                renamerError.textContent = err.message;
                renamerError.classList.remove('d-none');
            }
        }
    }

    // Event wiring
    if (renamerFiles) {
        renamerFiles.addEventListener('change', () => {
            pickExampleFile();
            updateRenamerBtn();
        });
    }

    if (renamerResetBtn) {
        renamerResetBtn.addEventListener('click', pickExampleFile);
    }

    if (renamerNewExample) {
        renamerNewExample.addEventListener('input', () => {
            inferPattern();
            updateRenamerBtn();
        });
        
        // Auto-append suffix when user finishes typing (on blur)
        renamerNewExample.addEventListener('blur', () => {
            autoAppendModalitySuffix();
            inferPattern();
        });
    }

    if (renamerUseMapping) {
        renamerUseMapping.addEventListener('change', () => {
            updateMappingVisibility();
            inferPattern();
        });
    }

    if (renamerSubjectValue) {
        renamerSubjectValue.addEventListener('input', inferPattern);
    }

    if (renamerSessionValue) {
        renamerSessionValue.addEventListener('input', inferPattern);
    }

    if (renamerModality) {
        renamerModality.addEventListener('change', () => {
            updateRecordingVisibility();
            updateHintFromModality();
            autoAppendModalitySuffix();  // Auto-append when modality changes
            inferPattern();
        });
    }

    if (renamerRecording) {
        renamerRecording.addEventListener('change', () => {
            updateHintFromModality();
            autoAppendModalitySuffix();  // Auto-append when recording changes
            inferPattern();
        });
    }

    if (renamerOrganize) {
        renamerOrganize.addEventListener('change', () => {
            updateRenamerStructureHint();
            runRenamer(true);
        });
    }

    if (renamerTargetRaw) {
        renamerTargetRaw.addEventListener('change', updateRenamerStructureHint);
    }
    if (renamerTargetSource) {
        renamerTargetSource.addEventListener('change', updateRenamerStructureHint);
    }

    if (renamerFilterAll) {
        renamerFilterAll.addEventListener('click', () => filterRenamerTable(false));
    }

    if (renamerFilterUnmatched) {
        renamerFilterUnmatched.addEventListener('click', () => filterRenamerTable(true));
    }

    if (renamerDryRunBtn) {
        renamerDryRunBtn.addEventListener('click', () => runRenamer(true));
    }

    if (renamerDownloadBtn) {
        renamerDownloadBtn.addEventListener('click', () => runRenamer(false));
    }

    if (renamerCopyBtn) {
        renamerCopyBtn.addEventListener('click', () => runRenamer(false, { saveToProject: true, skipDownload: true }));
    }

    // Initial state
    updateRecordingVisibility();
    updateHintFromModality();
    updateMappingVisibility();
    updateRenamerBtn();
    updateRenamerStructureHint();
});
