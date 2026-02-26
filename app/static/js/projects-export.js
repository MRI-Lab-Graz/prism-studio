function showExportCard() {
    const card = document.getElementById('exportProjectCard');
    if (!card) return;

    if (currentProjectPath) {
        card.style.display = 'block';
    } else {
        card.style.display = 'none';
    }
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
        const originalText = setButtonLoading(btn, true, 'Preparing Export...');

        const progressDiv = document.getElementById('exportProgress');
        const resultDiv = document.getElementById('exportResult');
        progressDiv.style.display = 'block';
        resultDiv.style.display = 'none';

        const data = {
            project_path: currentProjectPath,
            anonymize: document.getElementById('exportAnonymize').checked,
            mask_questions: document.getElementById('exportMaskQuestions').checked,
            id_length: parseInt(document.getElementById('exportIdLength').value),
            deterministic: document.getElementById('exportDeterministic').checked,
            include_derivatives: document.getElementById('exportDerivatives').checked,
            include_code: document.getElementById('exportCode').checked,
            include_analysis: document.getElementById('exportAnalysis').checked
        };

        try {
            const response = await fetch('/api/projects/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Export failed');
            }

            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'project-export.zip';
            if (contentDisposition) {
                const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
                if (matches && matches[1]) {
                    filename = matches[1].replace(/['"]/g, '');
                }
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>Export Successful!</h5>
                    <p class="mb-2">Your project has been exported to: <strong>${filename}</strong></p>
                    ${data.anonymize ? `
                        <div class="alert alert-warning py-2 mt-2 mb-0">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            <strong>Security Notice:</strong> The export includes a <code>participants_mapping.json</code> file 
                            that can be used to re-identify participants. Keep this file secure!
                        </div>
                    ` : ''}
                </div>
            `;
        } catch (error) {
            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Export Failed</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    });
}

// ===== AND EXPORT =====
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
        const originalText = setButtonLoading(btn, true, 'Exporting for AND...');

        const progressDiv = document.getElementById('exportProgress');
        const resultDiv = document.getElementById('exportResult');
        const statusText = document.getElementById('exportStatusText');
        progressDiv.style.display = 'block';
        resultDiv.style.display = 'none';
        statusText.textContent = 'Preparing AND export...';

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
                        <h5><i class="fas fa-check-circle me-2"></i>AND Export Successful!</h5>
                        <p class="mb-2">Dataset exported to: <strong><code>${result.output_path}</code></strong></p>
                        ${filesList ? `
                            <div class="mt-2">
                                <strong>Generated files:</strong>
                                <ul class="mb-0 mt-1">${filesList}</ul>
                            </div>
                        ` : ''}
                        ${infoHtml}
                        <div class="mt-3">
                            <strong>Next steps:</strong>
                            <ol class="mb-0 mt-1">
                                <li>Review and edit <code>README.md</code> and <code>CITATION.cff</code> in the export folder</li>
                                <li>Run BIDS validator to verify compliance</li>
                                <li>Submit to AND</li>
                            </ol>
                        </div>
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>AND Export Failed</h5>
                        <p class="mb-0">${result.error || 'Unknown error occurred'}</p>
                    </div>
                `;
            }
        } catch (error) {
            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>AND Export Failed</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    });
}
