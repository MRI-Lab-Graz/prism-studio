export function createMetadataStatusController({
    escapeHtml,
    fetchWithApiFallback,
    getCurrentProjectPath,
    withProjectPathQuery,
    isProjectRequestCurrent,
    onStatusesChanged,
}) {
    let lastCitationStatus = {
        exists: null,
        valid: null,
        issues: [],
        consistent: null,
        consistencyIssues: []
    };

    let lastMetadataSyncStatus = {
        projectJsonExists: null,
        datasetDescriptionExists: null,
        citationExists: null,
        consistent: null,
        issues: []
    };

    function renderMetadataRepairHint() {
        const metadataIssues = Array.isArray(lastMetadataSyncStatus.issues)
            ? lastMetadataSyncStatus.issues.filter(issue => String(issue || '').trim())
            : [];
        const citationIssues = Array.isArray(lastCitationStatus.consistencyIssues)
            ? lastCitationStatus.consistencyIssues.filter(issue => String(issue || '').trim())
            : [];

        const metadataNeedsRepair = lastMetadataSyncStatus.consistent === false;
        const citationNeedsRegeneration = (
            lastCitationStatus.exists === true
            && lastCitationStatus.valid === true
            && lastCitationStatus.consistent === false
            && metadataNeedsRepair !== true
        );

        if (!metadataNeedsRepair && !citationNeedsRegeneration) {
            return '';
        }

        const combinedIssues = metadataNeedsRepair ? metadataIssues : citationIssues;
        const visibleIssues = combinedIssues.slice(0, 3);
        const remainingIssues = Math.max(0, combinedIssues.length - visibleIssues.length);
        const issueListHtml = visibleIssues.length
            ? `
                <ul class="mb-0 ps-3 small">
                    ${visibleIssues.map(issue => `<li>${escapeHtml(issue)}</li>`).join('')}
                    ${remainingIssues > 0 ? `<li>+${remainingIssues} more issue${remainingIssues > 1 ? 's' : ''}</li>` : ''}
                </ul>
            `
            : '';

        if (metadataNeedsRepair) {
            return `
                <div class="alert alert-warning mt-3 mb-0" role="status">
                    <div class="d-flex flex-column gap-2">
                        <div>
                            <strong>How to fix this:</strong>
                            Review the metadata fields below, then save the project to rewrite <code>project.json</code>, <code>dataset_description.json</code>, <code>CITATION.cff</code>, and <code>README.md</code> from the current form values.
                        </div>
                        ${issueListHtml}
                        <div class="d-flex flex-wrap gap-2">
                            <button type="button" class="btn btn-sm btn-outline-warning" data-action="repair-metadata-sync">
                                <i class="fas fa-save me-1"></i>Save Current Metadata To Project Files
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        return `
            <div class="alert alert-warning mt-3 mb-0" role="status">
                <div class="d-flex flex-column gap-2">
                    <div>
                        <strong>How to fix this:</strong>
                        The project metadata is already aligned, but <code>CITATION.cff</code> differs from it. Regenerate the citation file to bring it back in sync.
                    </div>
                    ${issueListHtml}
                    <div class="d-flex flex-wrap gap-2">
                        <button type="button" class="btn btn-sm btn-outline-warning" data-action="regenerate-citation-sync">
                            <i class="fas fa-rotate me-1"></i>Regenerate CITATION.cff
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    function renderMetadataSyncStatus(status) {
        lastMetadataSyncStatus = {
            projectJsonExists: status?.project_json_exists,
            datasetDescriptionExists: status?.dataset_description_exists,
            citationExists: status?.citation_exists,
            consistent: status?.consistent,
            issues: Array.isArray(status?.issues) ? status.issues : []
        };
        onStatusesChanged();
    }

    function renderCitationHealthStatus(status) {
        lastCitationStatus = {
            exists: status?.exists,
            valid: status?.valid,
            issues: Array.isArray(status?.issues) ? status.issues : [],
            consistent: status?.consistent,
            consistencyIssues: Array.isArray(status?.consistency_issues)
                ? status.consistency_issues
                : []
        };
        onStatusesChanged();
    }

    async function refreshCitationHealthStatus() {
        const requestProjectPath = getCurrentProjectPath();
        if (!requestProjectPath) {
            renderCitationHealthStatus({ exists: true, valid: true, issues: [] });
            return;
        }

        try {
            const response = await fetchWithApiFallback(
                withProjectPathQuery('/api/projects/citation/status', requestProjectPath)
            );
            const data = await response.json();
            if (!isProjectRequestCurrent(requestProjectPath)) {
                return;
            }
            if (!data.success) {
                renderCitationHealthStatus({
                    exists: true,
                    valid: false,
                    issues: [data.error || 'Could not read citation status.']
                });
                return;
            }
            renderCitationHealthStatus(data);
        } catch (error) {
            if (!isProjectRequestCurrent(requestProjectPath)) {
                return;
            }
            renderCitationHealthStatus({
                exists: true,
                valid: false,
                issues: ['Could not read citation status.']
            });
            console.debug('Citation status check failed:', error);
        }
    }

    async function refreshMetadataSyncStatus() {
        const requestProjectPath = getCurrentProjectPath();
        if (!requestProjectPath) {
            renderMetadataSyncStatus({
                project_json_exists: true,
                dataset_description_exists: true,
                citation_exists: true,
                consistent: true,
                issues: []
            });
            return;
        }

        try {
            const response = await fetchWithApiFallback(
                withProjectPathQuery('/api/projects/metadata/status', requestProjectPath)
            );
            const data = await response.json();
            if (!isProjectRequestCurrent(requestProjectPath)) {
                return;
            }
            if (!data.success) {
                renderMetadataSyncStatus({
                    project_json_exists: true,
                    dataset_description_exists: true,
                    citation_exists: true,
                    consistent: false,
                    issues: [data.error || 'Could not read metadata consistency status.']
                });
                return;
            }
            renderMetadataSyncStatus(data);
        } catch (error) {
            if (!isProjectRequestCurrent(requestProjectPath)) {
                return;
            }
            renderMetadataSyncStatus({
                project_json_exists: true,
                dataset_description_exists: true,
                citation_exists: true,
                consistent: false,
                issues: ['Could not read metadata consistency status.']
            });
            console.debug('Metadata consistency status check failed:', error);
        }
    }

    return {
        getLastCitationStatus: () => lastCitationStatus,
        getLastMetadataSyncStatus: () => lastMetadataSyncStatus,
        renderMetadataRepairHint,
        refreshCitationHealthStatus,
        refreshMetadataSyncStatus,
    };
}