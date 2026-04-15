function showExportCard() {
    const card = document.getElementById('exportProjectCard');
    if (!card) return;

    if (currentProjectPath) {
        card.style.display = 'block';
    } else {
        card.style.display = 'none';
    }
}

function loadExportPreferences() {
    fetch('/api/projects/preferences/export')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.preferences) {
                const input = document.getElementById('exportOutputFolder');
                if (input) input.value = data.preferences.output_folder || '';
            }
        })
        .catch(() => {});
}

loadExportPreferences();

window.addEventListener('prism-project-changed', function() {
    loadExportPreferences();
});

// Browse for export folder
const exportBrowseFolder = document.getElementById('exportBrowseFolder');
if (exportBrowseFolder) {
    exportBrowseFolder.addEventListener('click', async () => {
        try {
            const resp = await fetch('/api/projects/export/browse-folder', { method: 'POST' });
            const data = await resp.json();
            if (data.folder) {
                const input = document.getElementById('exportOutputFolder');
                if (input) input.value = data.folder;
                if (currentProjectPath) {
                    fetch('/api/projects/preferences/export', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ project_path: currentProjectPath, output_folder: data.folder })
                    }).catch(() => {});
                }
            }
        } catch { /* ignore */ }
    });
}

const exportOutputFolderInput = document.getElementById('exportOutputFolder');
if (exportOutputFolderInput) {
    exportOutputFolderInput.addEventListener('change', () => {
        if (currentProjectPath) {
            fetch('/api/projects/preferences/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: currentProjectPath, output_folder: exportOutputFolderInput.value.trim() })
            }).catch(() => {});
        }
    });
}

// Handle Export Form Submission
const exportProjectForm = document.getElementById('exportProjectForm');
if (exportProjectForm) {
    exportProjectForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        if (!currentProjectPath) {
            alert('No project is currently loaded');
            return;
        }

        const btn = this.querySelector('button[type="submit"]');
        const originalText = setButtonLoading(btn, true, 'Starting Export...');

        const progressDiv = document.getElementById('exportProgress');
        const progressBar = document.getElementById('exportProgressBar');
        const progressText = document.getElementById('exportProgressText');
        const statusText = document.getElementById('exportStatusText');
        const cancelBtn = document.getElementById('exportCancelBtn');
        const resultDiv = document.getElementById('exportResult');

        if (progressBar) progressBar.style.width = '0%';
        if (progressText) progressText.textContent = '0%';
        if (statusText) statusText.textContent = 'Starting export...';
        if (progressDiv) progressDiv.style.display = 'block';
        if (resultDiv) resultDiv.style.display = 'none';

        const data = {
            project_path: currentProjectPath,
            anonymize: document.getElementById('exportAnonymize')?.checked || false,
            mask_questions: document.getElementById('exportMaskQuestions')?.checked || false,
            include_derivatives: document.getElementById('exportDerivatives')?.checked || false,
            include_code: document.getElementById('exportCode')?.checked || false,
            include_analysis: document.getElementById('exportAnalysis')?.checked || false,
            output_folder: (document.getElementById('exportOutputFolder')?.value || '').trim() || null,
        };

        let jobId = null;
        let cancelled = false;

        function onCancelClick() {
            cancelled = true;
            if (jobId) {
                fetch(`/api/projects/export/${encodeURIComponent(jobId)}/cancel`, { method: 'DELETE' })
                    .catch(() => {});
            }
            if (progressDiv) progressDiv.style.display = 'none';
            if (resultDiv) {
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Export cancelled.</div>`;
            }
            setButtonLoading(btn, false, null, originalText);
        }

        if (cancelBtn) cancelBtn.onclick = onCancelClick;

        try {
            const startResp = await fetch('/api/projects/export/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (!startResp.ok) {
                const err = await startResp.json();
                throw new Error(err.error || 'Failed to start export');
            }
            const startData = await startResp.json();
            jobId = startData.job_id;

            const MAX_POLLS = 2250;
            for (let i = 0; i < MAX_POLLS; i++) {
                if (cancelled) break;
                await new Promise(r => setTimeout(r, 800));
                if (cancelled) break;

                const statusResp = await fetch(
                    `/api/projects/export/${encodeURIComponent(jobId)}/status`
                );
                if (!statusResp.ok) break;
                const status = await statusResp.json();

                const pct = status.percent || 0;
                if (progressBar) progressBar.style.width = `${pct}%`;
                if (progressText) progressText.textContent = `${pct}%`;
                if (statusText) statusText.textContent = status.message || '';

                if (status.status === 'complete') {
                    if (progressDiv) progressDiv.style.display = 'none';
                    if (resultDiv) {
                        resultDiv.style.display = 'block';
                        const savedPath = status.zip_path || 'unknown location';
                        resultDiv.innerHTML = `
                            <div class="alert alert-success">
                                <h5><i class="fas fa-check-circle me-2"></i>Export Successful!</h5>
                                <p class="mb-0">ZIP saved to:<br>
                                <code class="user-select-all">${escapeHtml ? escapeHtml(savedPath) : savedPath}</code></p>
                            </div>
                        `;
                    }
                    return;
                }

                if (status.status === 'error') {
                    throw new Error(status.error || 'Export failed');
                }

                if (status.status === 'cancelled') {
                    cancelled = true;
                    break;
                }
            }

            if (!cancelled) {
                throw new Error('Export timed out after 30 minutes. Please check server logs.');
            }

        } catch (error) {
            if (cancelled) return;
            if (progressDiv) progressDiv.style.display = 'none';
            if (resultDiv) {
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Export Failed</h5>
                        <p class="mb-0">${escapeHtml ? escapeHtml(error.message) : error.message}</p>
                    </div>
                `;
            }
        } finally {
            if (!cancelled) setButtonLoading(btn, false, null, originalText);
        }
    });
}

// ===== ANC EXPORT =====
const ancEnableExport = document.getElementById('ancEnableExport');
if (ancEnableExport) {
    ancEnableExport.addEventListener('change', function() {
        const isEnabled = this.checked;
        document.getElementById('ancOptionsGroup').style.display = isEnabled ? 'block' : 'none';
        document.getElementById('ancOptionsGroup2').style.display = isEnabled ? 'block' : 'none';
        document.getElementById('ancMetadataSection').style.display = isEnabled ? 'block' : 'none';
        document.getElementById('ancExportButton').style.display = isEnabled ? 'inline-block' : 'none';
    });
}

const ancExportButton = document.getElementById('ancExportButton');
if (ancExportButton) {
    ancExportButton.addEventListener('click', async function(e) {
        e.preventDefault();

        if (!currentProjectPath) {
            alert('No project is currently loaded');
            return;
        }

        const btn = this;
        const originalText = setButtonLoading(btn, true, 'Exporting for ANC...');

        const progressDiv = document.getElementById('exportProgress');
        const resultDiv = document.getElementById('exportResult');
        const statusText = document.getElementById('exportStatusText');
        progressDiv.style.display = 'block';
        resultDiv.style.display = 'none';
        statusText.textContent = 'Preparing ANC export...';

        const metadata = {};
        const title = document.getElementById('ancDatasetTitle').value.trim();
        const email = document.getElementById('ancContactEmail').value.trim();
        const givenName = document.getElementById('ancAuthorGiven').value.trim();
        const familyName = document.getElementById('ancAuthorFamily').value.trim();
        const description = document.getElementById('ancDatasetDescription').value.trim();

        if (title) metadata.DATASET_NAME = title;
        if (email) metadata.CONTACT_EMAIL = email;
        if (givenName) metadata.AUTHOR_GIVEN_NAME = givenName;
        if (familyName) metadata.AUTHOR_FAMILY_NAME = familyName;
        if (description) metadata.DATASET_ABSTRACT = description;

        const data = {
            project_path: currentProjectPath,
            convert_to_git_lfs: document.getElementById('ancConvertGitLfs').checked,
            include_ci_examples: document.getElementById('ancIncludeCiExamples').checked,
            metadata
        };

        try {
            const response = await fetch('/api/projects/anc-export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';

            if (result.success) {
                let infoHtml = '';
                if (data.convert_to_git_lfs) {
                    infoHtml += `
                        <div class="alert alert-info py-2 mt-2 mb-2">
                            <i class="fas fa-info-circle me-2"></i>
                            Git LFS configuration added. See <code>GIT_LFS_SETUP.md</code> in the export folder for setup instructions.
                        </div>
                    `;
                } else {
                    infoHtml += `
                        <div class="alert alert-info py-2 mt-2 mb-2">
                            <i class="fas fa-info-circle me-2"></i>
                            Export is DataLad-compatible. See <code>DATALAD_NOTE.md</code> for more information.
                        </div>
                    `;
                }

                if (data.include_ci_examples) {
                    infoHtml += `
                        <div class="alert alert-info py-2 mt-2 mb-2">
                            <i class="fas fa-info-circle me-2"></i>
                            CI/CD example files included. See <code>CI_SETUP.md</code> for instructions.
                        </div>
                    `;
                }

                const filesList = result.generated_files ?
                    Object.entries(result.generated_files).map(([key, path]) =>
                        `<li><code>${path.split('/').pop()}</code></li>`
                    ).join('') : '';

                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>ANC Export Successful!</h5>
                        <p class="mb-2">Dataset exported to: <strong><code>${result.output_path}</code></strong></p>
                        ${infoHtml}
                        <div class="mt-3">
                            <strong>Next steps:</strong>
                            <ol class="mb-0 mt-1">
                                <li>Review and edit <code>README.md</code> and <code>CITATION.cff</code> in the export folder</li>
                                <li>Run BIDS validator to verify compliance</li>
                                <li>Submit to ANC</li>
                            </ol>
                        </div>
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>ANC Export Failed</h5>
                        <p class="mb-0">${result.error || 'Unknown error occurred'}</p>
                    </div>
                `;
            }
        } catch (error) {
            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>ANC Export Failed</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    });
}
