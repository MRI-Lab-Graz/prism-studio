export function initProjectInitOnBidsController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    confirmProjectContextChange,
    applyCurrentProject,
    addRecentProject,
    showStudyMetadataCard,
    showExportCard,
    showMethodsCard,
}) {
    const initBidsSubmitBtn = document.getElementById('initBidsSubmitBtn');
    if (!initBidsSubmitBtn) {
        return;
    }

    initBidsSubmitBtn.addEventListener('click', async function() {
        const bidsPath = (document.getElementById('initBidsPath')?.value || '').trim();
        const displayName = (document.getElementById('initBidsName')?.value || '').trim();

        if (!bidsPath) {
            alert('Please select or enter the BIDS dataset root folder.');
            document.getElementById('initBidsPath')?.focus();
            return;
        }

        if (!confirmProjectContextChange('initialise a PRISM project on another dataset', bidsPath)) {
            return;
        }

        const resultDiv = document.getElementById('initBidsResult');
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = '<div class="alert alert-secondary"><i class="fas fa-spinner fa-spin me-2"></i>Initialising…</div>';

        const originalText = setButtonLoading(initBidsSubmitBtn, true, 'Initialising…');
        initBidsSubmitBtn.disabled = true;

        try {
            const response = await fetchWithApiFallback('/api/projects/init-on-bids', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: bidsPath, name: displayName || undefined })
            });
            const result = await response.json();

            if (result.success) {
                const fileList = (result.created_files || [])
                    .map(filePath => `<li><code>${escapeHtml(filePath)}</code></li>`)
                    .join('');
                const noneAdded = !result.created_files || result.created_files.length === 0;
                resultDiv.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>PRISM Initialised Successfully!</h5>
                        <p class="mb-2">${escapeHtml(result.message)}</p>
                        <p class="mb-2"><strong>Location:</strong> <code>${escapeHtml(result.path)}</code></p>
                        <p class="mb-0 text-success"><i class="fas fa-folder-open me-1"></i>This dataset is now your current working project.</p>
                        ${noneAdded ? '' : `<hr><p class="mb-1"><strong>Added files:</strong></p><ul class="mb-0">${fileList}</ul>`}
                        <div class="mt-3 pt-3 border-top">
                            <h6 class="text-muted mb-2">Next Steps:</h6>
                            <div class="btn-group" role="group">
                                <a href="/validate" class="btn btn-sm btn-outline-primary">
                                    <i class="fas fa-check-double me-1"></i>Validate Dataset
                                </a>
                                <a href="/converter" class="btn btn-sm btn-outline-success">
                                    <i class="fas fa-magic me-1"></i>Open Converter
                                </a>
                            </div>
                        </div>
                    </div>
                `;
                applyCurrentProject(result.current_project);
                addRecentProject(
                    result.current_project?.name || displayName || bidsPath.split(/[\\/]/).pop(),
                    result.path,
                    result.current_project?.icon
                );
                showStudyMetadataCard();
                showExportCard();
                showMethodsCard();
            } else {
                resultDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${escapeHtml(result.error)}</p>
                    </div>
                `;
            }
        } catch (error) {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${escapeHtml(error.message)}</p>
                </div>
            `;
        } finally {
            setButtonLoading(initBidsSubmitBtn, false, null, originalText);
            initBidsSubmitBtn.disabled = false;
        }
    });
}