/**
 * Projects Module - Export
 * Project export and ANC (Austrian NeuroCloud) export functionality
 */

import { setButtonLoading } from './helpers.js';
import { getById, setHtml, hide, show, escapeHtml } from '../../shared/dom.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

/**
 * Show/hide export card based on current project
 * Uses centralized project state (with global fallback)
 */
export function showExportCard() {
    const card = getById('exportProjectCard');
    if (!card) return;

    if (resolveCurrentProjectPath()) {
        show(card);
        loadProjectStructure();
    } else {
        hide(card);
    }
}

/**
 * Load available sessions and modalities for the current project and render checkboxes.
 */
export async function loadProjectStructure() {
    const projectPath = resolveCurrentProjectPath();
    if (!projectPath) return;

    try {
        const resp = await fetch('/api/projects/export/structure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_path: projectPath }),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.success) return;

        _renderCheckboxList('exportSessionList', data.sessions || [], 'session');
        _renderCheckboxListWithAcq('exportModalityList', data.modalities || [], data.acq_labels || {});
    } catch { /* ignore */ }
}

/**
 * Render modality checkboxes with optional acq- sub-checkboxes.
 */
function _renderCheckboxListWithAcq(containerId, items, acqLabels) {
    const container = getById(containerId);
    if (!container) return;
    if (!items.length) {
        setHtml(container, '<span class="text-muted small">None detected.</span>');
        return;
    }
    const html = items.map(item => {
        const id = `export_modality_${item.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const acqs = acqLabels[item] || [];
        const acqHtml = acqs.length ? `
        <div class="ms-4 mt-1" id="acq_group_${item}">
            ${acqs.map(acq => {
                const acqId = `export_acq_${item}_${acq.replace(/[^a-zA-Z0-9]/g, '_')}`;
                return `<div class="form-check form-check-sm">
                    <input class="form-check-input export-acq-filter" type="checkbox"
                           id="${acqId}" value="${escapeHtml(acq)}" data-modality="${escapeHtml(item)}" checked>
                    <label class="form-check-label small text-muted" for="${acqId}">
                        <code>${escapeHtml(acq)}</code>
                    </label>
                </div>`;
            }).join('')}
        </div>` : '';
        return `
        <div class="form-check">
            <input class="form-check-input export-modality-filter" type="checkbox"
                   id="${id}" value="${escapeHtml(item)}" checked
                   onchange="document.querySelectorAll('#acq_group_${item} .export-acq-filter').forEach(cb => { cb.disabled = !this.checked; cb.checked = this.checked ? cb.checked : false; })">
            <label class="form-check-label" for="${id}">
                <code>${escapeHtml(item)}</code>
            </label>
        </div>${acqHtml}`;
    }).join('');
    setHtml(container, html);
}

/**
 * Render a list of labeled checkboxes (all checked by default) into containerId.
 */
function _renderCheckboxList(containerId, items, prefix) {
    const container = getById(containerId);
    if (!container) return;
    if (!items.length) {
        setHtml(container, '<span class="text-muted small">None detected.</span>');
        return;
    }
    const html = items.map(item => {
        const id = `export_${prefix}_${item.replace(/[^a-zA-Z0-9]/g, '_')}`;
        return `
        <div class="form-check">
            <input class="form-check-input export-${prefix}-filter" type="checkbox"
                   id="${id}" value="${escapeHtml(item)}" checked>
            <label class="form-check-label" for="${id}">
                <code>${escapeHtml(item)}</code>
            </label>
        </div>`;
    }).join('');
    setHtml(container, html);
}

/**
 * Load saved export preferences (output_folder) for the current project.
 */
export async function loadExportPreferences() {
    try {
        const resp = await fetch('/api/projects/preferences/export');
        const data = await resp.json();
        if (data.success && data.preferences) {
            const folder = data.preferences.output_folder || '';
            const input = getById('exportOutputFolder');
            if (input) input.value = folder;
        }
    } catch { /* ignore */ }
}

/**
 * Initialize export form
 */
export function initExportForm() {
    const exportProjectForm = getById('exportProjectForm');
    if (exportProjectForm) {
        exportProjectForm.addEventListener('submit', handleExportSubmit);
    }

    const browseBtn = getById('exportBrowseFolder');
    if (browseBtn) {
        browseBtn.addEventListener('click', async () => {
            try {
                const resp = await fetch('/api/projects/export/browse-folder', { method: 'POST' });
                const data = await resp.json();
                if (data.folder) {
                    const input = getById('exportOutputFolder');
                    if (input) input.value = data.folder;
                    // Persist preference
                    const projectPath = resolveCurrentProjectPath();
                    if (projectPath) {
                        fetch('/api/projects/preferences/export', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ project_path: projectPath, output_folder: data.folder })
                        }).catch(() => {});
                    }
                }
            } catch { /* ignore */ }
        });
    }

    // Persist folder preference on manual input change
    const folderInput = getById('exportOutputFolder');
    if (folderInput) {
        folderInput.addEventListener('change', () => {
            const projectPath = resolveCurrentProjectPath();
            if (projectPath) {
                fetch('/api/projects/preferences/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: projectPath, output_folder: folderInput.value.trim() })
                }).catch(() => {});
            }
        });
    }

    // Defacing status check
    const checkDefacingBtn = getById('exportCheckDefacing');
    if (checkDefacingBtn) {
        checkDefacingBtn.addEventListener('click', async () => {
            const projectPath = resolveCurrentProjectPath();
            if (!projectPath) { alert('No project is currently loaded'); return; }
            const reportDiv = getById('exportDefacingReport');
            checkDefacingBtn.disabled = true;
            checkDefacingBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Checking…';
            try {
                const resp = await fetch('/api/projects/export/defacing-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: projectPath })
                });
                const result = await resp.json();
                if (!resp.ok || result.error) {
                    if (reportDiv) { reportDiv.style.display = 'block'; reportDiv.innerHTML = `<div class="alert alert-danger py-1 mb-0">${result.error || 'Error fetching report'}</div>`; }
                    return;
                }
                if (!reportDiv) return;
                const { counts, report } = result;
                if (!report || report.length === 0) {
                    reportDiv.innerHTML = '<span class="text-muted small">No anatomical JSON sidecars found.</span>';
                } else {
                    const rows = report.map(r => {
                        const icon = r.status === 'defaced' ? '✅' : r.status === 'not_defaced' ? '⚠️' : '❓';
                        return `<tr><td class="small text-break">${r.file}</td><td>${icon} ${r.status.replace('_', ' ')}</td><td class="small text-muted">${r.reason}</td></tr>`;
                    }).join('');
                    reportDiv.innerHTML = `
                        <div class="small mb-1">
                            <span class="badge bg-success me-1">${counts.defaced} defaced</span>
                            <span class="badge bg-warning text-dark me-1">${counts.not_defaced} not defaced</span>
                            <span class="badge bg-secondary">${counts.unknown} unknown</span>
                        </div>
                        <div style="max-height:200px;overflow-y:auto;">
                          <table class="table table-sm table-bordered mb-0" style="font-size:0.8em;">
                            <thead><tr><th>File</th><th>Status</th><th>Reason</th></tr></thead>
                            <tbody>${rows}</tbody>
                          </table>
                        </div>`;
                }
                reportDiv.style.display = 'block';
            } catch (err) {
                if (reportDiv) { reportDiv.style.display = 'block'; reportDiv.innerHTML = `<div class="alert alert-danger py-1 mb-0">${err.message}</div>`; }
            } finally {
                checkDefacingBtn.disabled = false;
                checkDefacingBtn.innerHTML = '<i class="fas fa-search me-1"></i>Check defacing status of anatomical scans';
            }
        });
    }
}

/**
 * Handle export form submission (async job with progress + cancel)
 */
async function handleExportSubmit(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this.querySelector('button[type="submit"]');
    const originalText = setButtonLoading(btn, true, 'Starting Export...');

    const progressDiv = getById('exportProgress');
    const progressBar = getById('exportProgressBar');
    const progressText = getById('exportProgressText');
    const statusText = getById('exportStatusText');
    const cancelBtn = getById('exportCancelBtn');
    const resultDiv = getById('exportResult');

    // Reset and show progress
    if (progressBar) { progressBar.style.width = '0%'; }
    if (progressText) progressText.textContent = '0%';
    if (statusText) statusText.textContent = 'Starting export...';
    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);

    const data = {
        project_path: currentProjectPath,
        anonymize: getById('exportAnonymize')?.checked || false,
        mask_questions: getById('exportMaskQuestions')?.checked || false,
        scrub_mri_json: getById('exportScrubMriJson')?.checked || false,
        include_derivatives: getById('exportDerivatives')?.checked || false,
        include_code: getById('exportCode')?.checked || false,
        include_analysis: getById('exportAnalysis')?.checked || false,
        output_folder: (getById('exportOutputFolder')?.value || '').trim() || null,
        exclude_sessions: _getUncheckedValues('export-session-filter'),
        exclude_modalities: _getUncheckedValues('export-modality-filter'),
        exclude_acq: _getUncheckedAcqByModality(),
    };

    let jobId = null;
    let cancelled = false;

    // Cancel button handler
    function onCancelClick() {
        cancelled = true;
        if (jobId) {
            fetch(`/api/projects/export/${encodeURIComponent(jobId)}/cancel`, { method: 'DELETE' })
                .catch(() => {});
        }
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `<div class="alert alert-warning"><i class="fas fa-ban me-2"></i>Export cancelled.</div>`);
        }
        setButtonLoading(btn, false, null, originalText);
    }

    if (cancelBtn) {
        cancelBtn.onclick = onCancelClick;
    }

    try {
        // Start the async job
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

        // Poll for status (max ~2250 iterations = ~30 minutes)
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
                    if (progressDiv) hide(progressDiv);
                    if (resultDiv) {
                        show(resultDiv);
                        const savedPath = status.zip_path || 'unknown location';
                        setHtml(resultDiv, `
                            <div class="alert alert-success">
                                <h5><i class="fas fa-check-circle me-2"></i>Export Successful!</h5>
                                <p class="mb-0">ZIP saved to:<br>
                                <code class="user-select-all">${escapeHtml(savedPath)}</code></p>
                    `);
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
        if (cancelled) return; // already showed cancel message
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            setHtml(resultDiv, `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'Export failed.')}</p>
                </div>
            `);
        }
    } finally {
        if (!cancelled) {
            setButtonLoading(btn, false, null, originalText);
        }
    }
}

/**
 * Return the values of unchecked checkboxes with the given class name.
 * These are the items the user wants to EXCLUDE.
 */
function _getUncheckedValues(className) {
    return Array.from(document.querySelectorAll(`.${className}`))
        .filter(cb => !cb.checked)
        .map(cb => cb.value);
}

/**
 * Return a dict of {modality: [acq_label, ...]} for unchecked acq checkboxes.
 */
function _getUncheckedAcqByModality() {
    const result = {};
    document.querySelectorAll('.export-acq-filter').forEach(cb => {
        if (!cb.checked) {
            const mod = cb.dataset.modality;
            if (mod) {
                if (!result[mod]) result[mod] = [];
                result[mod].push(cb.value);
            }
        }
    });
    return result;
}

/**
 * Initialize ANC export
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
 * Handle ANC export
 */
async function handleAndExport(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this;
    const originalText = setButtonLoading(btn, true, 'Exporting for ANC...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (statusText) statusText.textContent = 'Preparing ANC export...';

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
        project_path: currentProjectPath,
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
                        <h5><i class="fas fa-check-circle me-2"></i>ANC Export Successful!</h5>
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
                                <li>Submit to ANC</li>
                            </ol>
                        </div>
                    </div>
                `;
            }
        } else {
            if (resultDiv) {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>ANC Export Failed</h5>
                        <p class="mb-0">${escapeHtml(result.error || 'Unknown error occurred')}</p>
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
                    <h5><i class="fas fa-exclamation-circle me-2"></i>ANC Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'ANC export failed.')}</p>
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
    initOpenMindsExport();
});

/**
 * Initialize openMINDS export
 */
export function initOpenMindsExport() {
    const enableCheckbox = getById('openmindsEnableExport');
    if (enableCheckbox) {
        enableCheckbox.addEventListener('change', function() {
            const isEnabled = this.checked;
            const optionsGroup = getById('openmindsOptionsGroup');
            const metadataSection = getById('openmindsMetadataSection');
            const exportButton = getById('openmindsExportButton');
            if (optionsGroup) optionsGroup.style.display = isEnabled ? 'block' : 'none';
            if (metadataSection) metadataSection.style.display = isEnabled ? 'block' : 'none';
            if (exportButton) exportButton.style.display = isEnabled ? 'inline-block' : 'none';
            if (isEnabled) _loadOpenMindsTaskDescriptions();
        });
    }

    const exportButton = getById('openmindsExportButton');
    if (exportButton) {
        exportButton.addEventListener('click', handleOpenMindsExport);
    }
}

/**
 * Fetch tasks from the project and render description inputs in the pre-flight form.
 */
async function _loadOpenMindsTaskDescriptions() {
    const container = getById('openmindsProtocolsContainer');
    const placeholder = getById('openmindsProtocolsPlaceholder');
    if (!container) return;

    const currentProjectPath = resolveCurrentProjectPath();
    const params = currentProjectPath ? `?project_path=${encodeURIComponent(currentProjectPath)}` : '';

    try {
        const response = await fetch(`/api/projects/openminds-tasks${params}`);
        const result = await response.json();

        if (!result.success || !result.tasks || result.tasks.length === 0) {
            if (placeholder) placeholder.textContent = 'No tasks found in project.';
            return;
        }

        // Render one textarea per task
        const rows = result.tasks.map(task => `
            <div class="mb-2">
                <label class="form-label small fw-semibold mb-1">${task}</label>
                <textarea class="form-control form-control-sm openminds-protocol-desc"
                          rows="2"
                          data-task="${task}"
                          placeholder="Describe what participants did in this task…"></textarea>
            </div>
        `).join('');

        container.innerHTML = rows;
    } catch (_err) {
        if (placeholder) placeholder.textContent = 'Could not load tasks.';
    }
}

/**
 * Handle openMINDS export
 */
async function handleOpenMindsExport(e) {
    e.preventDefault();

    const currentProjectPath = resolveCurrentProjectPath();
    if (!currentProjectPath) {
        alert('No project is currently loaded');
        return;
    }

    const btn = this;
    const originalText = setButtonLoading(btn, true, 'Exporting to openMINDS...');

    const progressDiv = getById('exportProgress');
    const resultDiv = getById('exportResult');
    const statusText = getById('exportStatusText');

    if (progressDiv) show(progressDiv);
    if (resultDiv) hide(resultDiv);
    if (statusText) statusText.textContent = 'Running bids2openminds...';

    const singleFileRadio = getById('openmindsModeSingle');
    const singleFile = singleFileRadio ? singleFileRadio.checked : true;

    // Collect pre-flight supplements
    const protocolDescriptions = {};
    document.querySelectorAll('.openminds-protocol-desc').forEach(el => {
        const task = el.dataset.task;
        const desc = el.value.trim();
        if (task && desc) protocolDescriptions[task] = desc;
    });
    const ethicsCategory = getById('openmindsEthicsCategory')?.value.trim() || '';

    const data = {
        project_path: currentProjectPath,
        single_file: singleFile,
        include_empty: getById('openmindsIncludeEmpty')?.checked || false,
        supplements: {
            protocol_descriptions: protocolDescriptions,
            ethics_category: ethicsCategory,
        },
    };

    try {
        const response = await fetch('/api/projects/openminds-export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (progressDiv) hide(progressDiv);
        if (resultDiv) show(resultDiv);

        if (result.success) {
            const outputLabel = result.single_file
                ? `<code>${result.output_path}</code>`
                : `folder <code>${result.output_path}</code>`;
            const notesHtml = result.has_notes
                ? `<div class="alert alert-info py-2 mt-2 mb-0">
                       <i class="fas fa-info-circle me-2"></i>
                       Ethics and other supplements saved to
                       <code>${result.output_path.replace(/\.jsonld$/, '_supplements.json')}</code>.
                   </div>`
                : '';
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>openMINDS Export Successful!</h5>
                    <p class="mb-2">Metadata written to: <strong>${outputLabel}</strong></p>
                    ${notesHtml}
                    <div class="mt-3">
                        <strong>Next steps:</strong>
                        <ol class="mb-0 mt-1">
                            <li>Review the generated <code>.jsonld</code> file for completeness</li>
                            <li>Submit or publish the openMINDS metadata alongside your dataset</li>
                        </ol>
                    </div>
                </div>
            `;
        } else {
            const isNotInstalled = (result.error || '').includes('not installed');
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>openMINDS Export Failed</h5>
                    <p class="mb-0">${escapeHtml(result.error || 'Unknown error occurred')}</p>
                    ${isNotInstalled ? `<p class="mb-0 mt-2"><small>Install with: <code>pip install bids2openminds</code></small></p>` : ''}
                </div>
            `;
        }
    } catch (error) {
        if (progressDiv) hide(progressDiv);
        if (resultDiv) {
            show(resultDiv);
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>openMINDS Export Failed</h5>
                    <p class="mb-0">${escapeHtml(error.message || 'openMINDS export failed.')}</p>
                </div>
            `;
        }
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}
