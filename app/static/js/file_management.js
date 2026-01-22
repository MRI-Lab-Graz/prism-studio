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
    const organizeBtn = document.getElementById('organizeBtn');
    const organizeCopyBtn = document.getElementById('organizeCopyBtn');
    const organizeError = document.getElementById('organizeError');
    const organizeInfo = document.getElementById('organizeInfo');
    const organizeProgress = document.getElementById('organizeProgress');
    const organizeLogContainer = document.getElementById('organizeLogContainer');
    const organizeLog = document.getElementById('organizeLog');
    const organizeLogClearBtn = document.getElementById('organizeLogClearBtn');
    const organizeTargetRoot = () => {
        const checked = document.querySelector('input[name="organizeTargetRoot"]:checked');
        return checked ? checked.value : 'rawdata';
    };

    function updateOrganizeBtn() {
        const hasFiles = organizeFiles && organizeFiles.files && organizeFiles.files.length > 0;
        if (organizeBtn) organizeBtn.disabled = !hasFiles;
        if (organizeCopyBtn) organizeCopyBtn.disabled = !hasFiles;
    }

    if (organizeFiles) {
        organizeFiles.addEventListener('change', updateOrganizeBtn);
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
        if (!organizeFiles) return;
        if (organizeError) organizeError.classList.add('d-none');
        if (organizeInfo) organizeInfo.classList.add('d-none');
        if (organizeProgress) organizeProgress.classList.remove('d-none');
        if (organizeLogContainer) organizeLogContainer.classList.remove('d-none');
        if (organizeLog) organizeLog.textContent = '';
        if (organizeBtn) organizeBtn.disabled = true;
        if (organizeCopyBtn) organizeCopyBtn.disabled = true;

        const files = Array.from(organizeFiles.files);
        const modality = organizeModality ? organizeModality.value : 'anat';
        const destRoot = organizeTargetRoot();
        const datasetName = 'Organized Dataset';

        const formData = new FormData();
        files.forEach(f => formData.append('files', f));
        formData.append('dataset_name', datasetName);
        formData.append('modality', modality);
        formData.append('save_to_project', saveToProject);
        formData.append('dest_root', destRoot);

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

            if (result.log && organizeLog) {
                organizeLog.textContent = result.log;
            }

            if (!skipDownload && result.zip) {
                downloadBase64Zip(result.zip, `${datasetName}_prism.zip`);
            }

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

    if (organizeBtn) {
        organizeBtn.addEventListener('click', () => runOrganizer({ saveToProject: false, skipDownload: false }));
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
        if (renamerNewExample) renamerNewExample.placeholder = `e.g. ${hint}`;
    }

    function updateRenamerBtn() {
        const hasFiles = renamerFiles && renamerFiles.files && renamerFiles.files.length > 0;
        const hasNewName = renamerNewExample && renamerNewExample.value.trim().length > 0;
        const disabled = !hasFiles || !hasNewName;
        if (renamerDownloadBtn) renamerDownloadBtn.disabled = disabled;
        if (renamerCopyBtn) renamerCopyBtn.disabled = disabled;
        if (renamerDryRunBtn) renamerDryRunBtn.disabled = disabled;
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
                            const stem = res.new.split('.')[0];
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
    }

    if (renamerModality) {
        renamerModality.addEventListener('change', () => {
            updateHintFromModality();
            updateRecordingVisibility();
            inferPattern();
        });
    }

    if (renamerRecording) {
        renamerRecording.addEventListener('change', () => {
            updateHintFromModality();
            inferPattern();
        });
    }

    if (renamerOrganize) {
        renamerOrganize.addEventListener('change', () => runRenamer(true));
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
    updateRenamerBtn();
});
