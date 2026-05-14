export function createStudyMetadataSaveController({
    fetchWithApiFallback,
    getCurrentProjectPath,
    buildCleanPayload,
    saveDatasetDescription,
    generateReadmeSilent,
    refreshMetadataSyncStatus,
    captureBaseline,
    updateCompletenessUI,
    computeLocalCompleteness,
    setMetadataSaveStatus,
    updateCreateProjectButton,
    showToast,
    showTopFeedback,
    setButtonLoading,
}) {
    async function saveStudyMetadata({ isPreliminarySave = false } = {}) {
        const saveButtons = [
            document.getElementById('createProjectSubmitBtn'),
            document.getElementById('projectBoxSaveBtn'),
            document.getElementById('projectBoxPreliminarySaveBtn')
        ].filter(Boolean);
        const originalButtonTexts = new Map();
        saveButtons.forEach(button => {
            originalButtonTexts.set(button, setButtonLoading(button, true, 'Saving...'));
        });
        if (!isPreliminarySave) {
            setMetadataSaveStatus('Saving metadata...', 'muted');
        }

        let saveSucceeded = false;

        try {
            const cleanPayload = buildCleanPayload();
            const requestProjectPath = getCurrentProjectPath();
            const response = await fetchWithApiFallback('/api/projects/study-metadata', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: requestProjectPath, ...cleanPayload })
            });

            const result = await response.json();
            if (result.success) {
                // Keep frontend readiness scoring semantics stable by recomputing from
                // the current form state after save.
                updateCompletenessUI(computeLocalCompleteness());
                let datasetDescriptionSaved = true;
                try {
                    await saveDatasetDescription(requestProjectPath);
                    showToast('Dataset description saved', 'success');
                } catch (error) {
                    if (!isPreliminarySave) {
                        throw error;
                    }
                    datasetDescriptionSaved = false;
                    console.warn('Preliminary save: dataset_description save deferred:', error);
                }

                const readmeResult = await generateReadmeSilent(requestProjectPath);

                if (requestProjectPath === getCurrentProjectPath()) {
                    await refreshMetadataSyncStatus();
                    captureBaseline();
                }

                saveSucceeded = true;
                saveButtons.forEach(button => {
                    button.innerHTML = '<i class="fas fa-check me-1"></i>Saved Successfully!';
                    button.classList.add('btn-success');
                    button.classList.remove('btn-info', 'btn-warning');
                    button.disabled = false;
                });

                window.scrollTo({ top: 0, behavior: 'smooth' });
                const statsGrid = document.querySelector('.stats-grid');
                if (statsGrid) {
                    statsGrid.classList.add('highlight-success');
                    setTimeout(() => statsGrid.classList.remove('highlight-success'), 1200);
                }

                if (isPreliminarySave) {
                    if (datasetDescriptionSaved) {
                        const preliminaryMessage = readmeResult.success
                            ? 'Preliminary project state saved. You can complete required metadata later.'
                            : 'Preliminary project state saved, but README generation failed. You can complete required metadata later.';
                        showTopFeedback(preliminaryMessage, 'warning');
                        setMetadataSaveStatus(
                            readmeResult.success
                                ? 'Preliminary state saved. Required metadata is still incomplete.'
                                : 'Preliminary state saved. README generation failed.',
                            'warning'
                        );
                    } else {
                        showTopFeedback('Preliminary study metadata saved. Dataset description save deferred until required fields are complete.', 'warning');
                        setMetadataSaveStatus('Preliminary save completed. Dataset description update deferred.', 'warning');
                    }
                } else if (readmeResult.success) {
                    showToast('Study metadata saved successfully', 'success');
                    showTopFeedback('Study metadata saved successfully.', 'success');
                    setMetadataSaveStatus('Saved successfully. Metadata and derived files were updated.', 'success');
                } else {
                    showToast('Study metadata saved, but README generation failed.', 'warning');
                    showTopFeedback('Study metadata saved, but README generation failed.', 'warning');
                    setMetadataSaveStatus('Saved metadata files, but README generation failed.', 'warning');
                }

                setTimeout(() => {
                    saveButtons.forEach(button => {
                        setButtonLoading(button, false, null, originalButtonTexts.get(button) || null);
                    });
                    updateCreateProjectButton();
                }, 2000);
            } else {
                showToast('Failed to save: ' + result.error, 'danger');
                showTopFeedback('Failed to save study metadata: ' + (result.error || 'Unknown error'), 'danger');
                setMetadataSaveStatus('Save failed: ' + (result.error || 'Unknown error'), 'danger');
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        } catch (error) {
            showToast('Error: ' + error.message, 'danger');
            showTopFeedback('Error while saving study metadata: ' + error.message, 'danger');
            setMetadataSaveStatus('Save failed: ' + error.message, 'danger');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } finally {
            if (!saveSucceeded) {
                saveButtons.forEach(button => {
                    setButtonLoading(button, false, null, originalButtonTexts.get(button) || null);
                });
                updateCreateProjectButton();
            }
        }

        return saveSucceeded;
    }

    return {
        saveStudyMetadata,
    };
}