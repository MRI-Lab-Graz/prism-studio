/**
 * Projects Module - Export
 * Project export and AND (Austrian NeuroCloud) export functionality
 */

import { setButtonLoading } from './helpers.js';
import { getById, setHtml, hide, show } from '../../shared/dom.js';

/**
 * Show/hide export card based on current project
 * Uses global window.currentProjectPath
 */
export function showExportCard() {
    const card = getById('exportProjectCard');
    if (!card) return;

    if (window.currentProjectPath) {
        show(card);
    } else {
        hide(card);
    }
}

/**
 * Initialize export form
 */
export function initExportForm() {
    const exportProjectForm = getById('exportProjectForm');
    if (exportProjectForm) {
        exportProjectForm.addEventListener('submit', handleExportSubmit);
    }
}

/**
 * Handle export form submission
 */
async function handleExportSubmit(e) {
    e.preventDefault();

    if (!window.currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this.querySelector('button[type="submit"]');
    const originalText = setButtonLoading(btn, true, 'Preparing Export...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);

    const data = {
        project_path: window.currentProjectPath,
        anonymize: getById('exportAnonymize')?.checked || false,
        mask_questions: getById('exportMaskQuestions')?.checked || false,
        id_length: parseInt(getById('exportIdLength')?.value || '0'),
        deterministic: getById('exportDeterministic')?.checked || false,
        include_derivatives: getById('exportDerivatives')?.checked || false,
        include_code: getById('exportCode')?.checked || false,
        include_analysis: getById('exportAnalysis')?.checked || false
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

        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>Export Successful!</h5>
                    <p class="mb-2">Your project has been exported to: <strong>${filename}</strong></p>
                </div>
            `;
        }
    } catch (error) {
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Export Failed</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

/**
 * Initialize AND export
 */
export function initAndExport() {
    const ancEnableExport = getById('ancEnableExport');
    if (ancEnableExport) {
        ancEnableExport.addEventListener('change', function() {
            const isEnabled = this.checked;
            const optionsGroup = getById('ancOptionsGroup');
            const optionsGroup2 = getById('ancOptionsGroup2');
            const metadataSection = getById('ancMetadataSection');
            const exportButton = getById('ancExportButton');

            if (optionsGroup) optionsGroup.style.display = isEnabled ? 'block' : 'none';
            if (optionsGroup2) optionsGroup2.style.display = isEnabled ? 'block' : 'none';
            if (metadataSection) metadataSection.style.display = isEnabled ? 'block' : 'none';
            if (exportButton) exportButton.style.display = isEnabled ? 'inline-block' : 'none';
        });
    }

    const ancExportButton = getById('ancExportButton');
    if (ancExportButton) {
        ancExportButton.addEventListener('click', handleAndExport);
    }
}

/**
 * Handle AND export
 */
async function handleAndExport(e) {
    e.preventDefault();

    if (!window.currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this;
    const originalText = setButtonLoading(btn, true, 'Exporting for AND...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (statusText) statusText.textContent = 'Preparing AND export...';

    const metadata = {};
    const title = getById('ancDatasetTitle')?.value.trim() || '';
    const email = getById('ancContactEmail')?.value.trim() || '';
    const givenName = getById('ancAuthorGiven')?.value.trim() || '';
    const familyName = getById('ancAuthorFamily')?.value.trim() || '';
    const description = getById('ancDatasetDescription')?.value.trim() || '';

    if (title) metadata.DATASET_NAME = title;
    if (email) metadata.CONTACT_EMAIL = email;
    if (givenName) metadata.AUTHOR_GIVEN_NAME = givenName;
    if (familyName) metadata.AUTHOR_FAMILY_NAME = familyName;
    if (description) metadata.DATASET_ABSTRACT = description;

    const data = {
        project_path: window.currentProjectPath,
        convert_to_git_lfs: getById('ancConvertGitLfs')?.checked || false,
        include_ci_examples: getById('ancIncludeCiExamples')?.checked || false,
        metadata
    };

    try {
        const response = await fetch('/api/projects/anc-export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (progressDiv) hide(progressDiv);
        if (resultDiv) show(resultDiv);

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

            if (resultDiv) {
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
            }
        } else {
            if (resultDiv) {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>AND Export Failed</h5>
                        <p class="mb-0">${result.error || 'Unknown error occurred'}</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>AND Export Failed</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    initExportForm();
    initAndExport();
});
