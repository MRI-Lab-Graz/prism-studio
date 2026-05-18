import { fetchWithApiFallback } from '../../shared/api.js';

export function createParticipantsMergeConflictDownloadController({
    getPreviewData,
    getWorkflowMode,
    getFileAction,
    buildConflictFormData,
    parseJsonResponse,
}) {
    function getResponseDownloadFilename(response, fallbackName) {
        const disposition = String(response.headers.get('Content-Disposition') || '').trim();
        const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utf8Match && utf8Match[1]) {
            try {
                return decodeURIComponent(utf8Match[1]);
            } catch (_error) {
                return utf8Match[1];
            }
        }

        const simpleMatch = disposition.match(/filename="?([^";]+)"?/i);
        if (simpleMatch && simpleMatch[1]) {
            return simpleMatch[1];
        }

        return fallbackName;
    }

    async function parseErrorResponse(response, fallbackMessage) {
        if (typeof parseJsonResponse !== 'function') {
            return fallbackMessage;
        }

        try {
            const payload = await parseJsonResponse(response);
            return payload.error || payload.message || fallbackMessage;
        } catch (_error) {
            return fallbackMessage;
        }
    }

    async function handleDownloadClick(downloadBtn) {
        const errorDiv = document.getElementById('participantsError');
        const originalLabel = downloadBtn.innerHTML;

        if (errorDiv) {
            errorDiv.classList.add('d-none');
            errorDiv.textContent = '';
        }

        downloadBtn.disabled = true;
        downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Preparing CSV...';

        try {
            const previewData = typeof getPreviewData === 'function' ? getPreviewData() : null;
            if (!previewData || !previewData.merge_mode) {
                throw new Error('Run a merge preview first.');
            }
            if (Number(previewData.conflict_count || 0) === 0) {
                throw new Error('This merge preview has no conflicts to export.');
            }

            const workflowMode = typeof getWorkflowMode === 'function' ? getWorkflowMode() : '';
            const fileAction = typeof getFileAction === 'function' ? getFileAction() : '';
            if (workflowMode !== 'file' || fileAction !== 'merge') {
                throw new Error('Conflict export is only available during file merge preview.');
            }

            const formData = buildConflictFormData();
            const response = await fetchWithApiFallback('/api/participants-merge-conflicts', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorMessage = await parseErrorResponse(response, 'Could not download merge conflict report.');
                throw new Error(errorMessage);
            }

            const fileName = getResponseDownloadFilename(response, 'participants_merge_conflicts.csv');
            const blob = await response.blob();
            const objectUrl = window.URL.createObjectURL(blob);
            const downloadLink = document.createElement('a');
            downloadLink.href = objectUrl;
            downloadLink.download = fileName;
            document.body.appendChild(downloadLink);
            downloadLink.click();
            downloadLink.remove();
            window.URL.revokeObjectURL(objectUrl);
        } catch (error) {
            if (errorDiv) {
                errorDiv.textContent = String(error && error.message ? error.message : error || 'Could not download merge conflict report.');
                errorDiv.classList.remove('d-none');
            }
        } finally {
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = originalLabel;
        }
    }

    function bind() {
        const downloadBtn = document.getElementById('participantsDownloadMergeConflictsBtn');
        if (!downloadBtn) {
            return false;
        }

        if (downloadBtn.dataset.participantsMergeConflictsBound === '1') {
            return true;
        }

        downloadBtn.dataset.participantsMergeConflictsBound = '1';
        downloadBtn.addEventListener('click', () => {
            handleDownloadClick(downloadBtn);
        });
        return true;
    }

    return {
        bind,
    };
}
