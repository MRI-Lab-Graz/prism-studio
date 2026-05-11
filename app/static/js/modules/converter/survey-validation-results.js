export function createSurveyValidationResultsController({
    escapeHtml,
}) {
    function normalizeValidationIssueText(value) {
        return String(value || '').trim().replace(/\s+/g, ' ');
    }

    function extractValidationIssueMessage(file, normalizedGroupMessage) {
        const fileMessage = normalizeValidationIssueText(file && file.message);
        if (fileMessage && fileMessage !== normalizedGroupMessage) {
            return fileMessage;
        }
        return normalizedGroupMessage || fileMessage || 'Validation issue';
    }

    function extractValidationIssueKind(message) {
        const normalized = normalizeValidationIssueText(message).toLowerCase();
        if (!normalized) {
            return '';
        }

        const schemaErrorMarker = 'schema error:';
        const schemaErrorIndex = normalized.indexOf(schemaErrorMarker);
        if (schemaErrorIndex >= 0) {
            return normalized.slice(schemaErrorIndex).trim();
        }

        const firstColonIndex = normalized.indexOf(':');
        if (firstColonIndex >= 0 && firstColonIndex < normalized.length - 1) {
            return normalized.slice(firstColonIndex + 1).trim();
        }

        return normalized;
    }

    function renderValidationGroupFiles(group) {
        const files = Array.isArray(group && group.files) ? group.files : [];
        if (files.length === 0) {
            return '';
        }

        const normalizedGroupMessage = normalizeValidationIssueText(group && group.message);
        const issueMessages = files.map((file) => extractValidationIssueMessage(file, normalizedGroupMessage));
        const uniqueMessages = [...new Set(issueMessages.filter(Boolean))];
        const issueKinds = issueMessages.map((message) => extractValidationIssueKind(message));
        const uniqueIssueKinds = [...new Set(issueKinds.filter(Boolean))];

        // Collapse repeated copies of the same issue across many files,
        // including cases where the full file message differs only by path.
        if (files.length > 1 && (uniqueMessages.length <= 1 || uniqueIssueKinds.length <= 1)) {
            const uniqueFiles = [...new Set(
                files.map((file) => {
                    const filePath = String((file && file.file) || '').trim();
                    return filePath || 'unknown';
                })
            )];
            const previewLimit = 8;
            const previewFiles = uniqueFiles.slice(0, previewLimit);
            const hiddenCount = uniqueFiles.length - previewFiles.length;
            const issueKindPreview = uniqueIssueKinds.length === 1 ? uniqueIssueKinds[0] : '';

            return `
                <details class="ms-2 mb-0 smaller">
                    <summary class="text-muted">${uniqueFiles.length} files share this same issue${issueKindPreview ? `: ${escapeHtml(issueKindPreview)}` : ''}</summary>
                    <div class="mt-2">
                        ${previewFiles.map((filePath) => `<div><code class="text-dark">${escapeHtml(filePath)}</code></div>`).join('')}
                        ${hiddenCount > 0 ? `<div class="text-muted mt-1">...and ${hiddenCount} more</div>` : ''}
                    </div>
                </details>
            `;
        }

        return `
            <ul class="list-unstyled ms-2 mb-0 smaller">
                ${files.map((file) => `
                    <li class="mb-1 border-bottom pb-1 last-child-no-border">
                        <div class="d-flex justify-content-between">
                            <code class="text-dark fw-bold">${escapeHtml(file.file || 'unknown')}</code>
                            ${file.line ? `<span class="badge bg-secondary">Line ${file.line}</span>` : ''}
                        </div>
                        ${file.message && normalizeValidationIssueText(file.message) !== normalizedGroupMessage ? `<div class="text-muted mt-1">${escapeHtml(file.message)}</div>` : ''}
                        ${file.evidence ? `<div class="text-muted italic ms-2 mt-1 p-1 bg-white border rounded" style="font-size: 0.85em; font-family: monospace;">${escapeHtml(file.evidence)}</div>` : ''}
                    </li>
                `).join('')}
            </ul>
        `;
    }

    function displayValidationResults(validation, prefix = '') {
        const getEl = (id) => document.getElementById(prefix ? prefix + id.charAt(0).toUpperCase() + id.slice(1) : id);

        const container = getEl('validationResultsContainer');
        const card = getEl('validationResultsCard');
        const header = getEl('validationResultsHeader');
        const badge = getEl('validationBadge');
        const summaryEl = getEl('validationSummary');
        const detailsEl = getEl('validationDetails');

        if (!container) return;
        container.classList.remove('d-none');

        const errors = validation.errors || [];
        const warnings = validation.warnings || [];
        const isValid = errors.length === 0;

        card.classList.remove('border-success', 'border-warning', 'border-danger');
        header.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'text-white', 'text-dark');

        if (isValid && warnings.length === 0) {
            card.classList.add('border-success');
            header.classList.add('bg-success', 'text-white');
            badge.className = 'badge bg-light text-success';
            badge.textContent = '✓ Valid';
        } else if (isValid) {
            card.classList.add('border-warning');
            header.classList.add('bg-warning', 'text-dark');
            badge.className = 'badge bg-light text-warning';
            badge.textContent = `⚠ ${warnings.length} Warning(s)`;
        } else {
            card.classList.add('border-danger');
            header.classList.add('bg-danger', 'text-white');
            badge.className = 'badge bg-light text-danger';
            badge.textContent = `✗ ${errors.length} Error(s)`;
        }

        const summary = validation.summary || {};
        summaryEl.innerHTML = `
            <div class="row text-center">
                <div class="col-4">
                    <div class="h4 mb-0 ${errors.length > 0 ? 'text-danger' : 'text-success'}">${errors.length}</div>
                    <small class="text-muted">Errors</small>
                </div>
                <div class="col-4">
                    <div class="h4 mb-0 ${warnings.length > 0 ? 'text-warning' : 'text-success'}">${warnings.length}</div>
                    <small class="text-muted">Warnings</small>
                </div>
                <div class="col-4">
                    <div class="h4 mb-0 text-info">${summary.total_files || summary.files_created || 'n/a'}</div>
                    <small class="text-muted">Files</small>
                </div>
            </div>
        `;

        let detailsHtml = '';

        if (validation.formatted) {
            const f = validation.formatted;

            if (f.errors && f.errors.length > 0) {
                detailsHtml += '<h6 class="text-danger mt-3"><i class="fas fa-times-circle me-1"></i>Errors</h6>';
                f.errors.forEach(group => {
                    detailsHtml += `
                        <div class="validation-group mb-3 p-3 border rounded bg-light shadow-sm">
<div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="fw-bold text-danger">
                                    <span class="badge bg-danger me-2">${group.code}</span>
                                    ${escapeHtml(group.message)}
                                </div>
                                ${group.documentation_url ? `
                                    <a href="${group.documentation_url}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2" style="font-size: 0.75rem;">
                                        <i class="fas fa-book me-1"></i>Docs
                                    </a>
                                ` : ''}
                            </div>

                            ${group.fix_hint ? `
                                <div class="alert alert-info py-2 px-3 mb-2 smaller">
                                    <i class="fas fa-lightbulb me-2 text-warning"></i>
                                    <strong>Fix Hint:</strong> ${escapeHtml(group.fix_hint)}
                                </div>
                            ` : ''}

                            ${renderValidationGroupFiles(group)}
                        </div>
                    `;
                });
            }

            if (f.warnings && f.warnings.length > 0) {
                detailsHtml += '<h6 class="text-warning mt-3"><i class="fas fa-exclamation-triangle me-1"></i>Warnings</h6>';
                f.warnings.forEach(group => {
                    detailsHtml += `
                        <div class="validation-group mb-3 p-3 border rounded bg-light shadow-sm">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="fw-bold text-warning">
                                    <span class="badge bg-warning text-dark me-2">${group.code}</span>
                                    ${escapeHtml(group.message)}
                                </div>
                                ${group.documentation_url ? `
                                    <a href="${group.documentation_url}" target="_blank" class="btn btn-sm btn-outline-primary py-0 px-2" style="font-size: 0.75rem;">
                                        <i class="fas fa-book me-1"></i>Docs
                                    </a>
                                ` : ''}
                            </div>

                            ${group.fix_hint ? `
                                <div class="alert alert-info py-2 px-3 mb-2 smaller">
                                    <i class="fas fa-lightbulb me-2 text-warning"></i>
                                    <strong>Fix Hint:</strong> ${escapeHtml(group.fix_hint)}
                                </div>
                            ` : ''}

                            ${renderValidationGroupFiles(group)}
                        </div>
                    `;
                });
            }
        } else {
            if (errors.length > 0) {
                detailsHtml += '<h6 class="text-danger mt-3"><i class="fas fa-times-circle me-1"></i>Errors</h6><ul class="list-unstyled">';
                errors.forEach(e => {
                    detailsHtml += `<li class="text-danger small"><i class="fas fa-times me-1"></i>${escapeHtml(e)}</li>`;
                });
                detailsHtml += '</ul>';
            }
            if (warnings.length > 0) {
                detailsHtml += '<h6 class="text-warning mt-3"><i class="fas fa-exclamation-triangle me-1"></i>Warnings</h6><ul class="list-unstyled">';
                warnings.forEach(w => {
                    detailsHtml += `<li class="text-warning small"><i class="fas fa-exclamation me-1"></i>${escapeHtml(w)}</li>`;
                });
                detailsHtml += '</ul>';
            }
        }

        detailsEl.innerHTML = detailsHtml;
    }

    return {
        displayValidationResults,
    };
}
