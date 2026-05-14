export function createParticipantsMergePreviewRefreshController({
    getPreviewButton = () => document.getElementById('participantsPreviewBtn'),
    getStatusElement = () => document.getElementById('participantsMergeHarmonizationStatus'),
    refreshDelayMs = 200,
} = {}) {
    let refreshTimerId = null;

    function isPending() {
        return refreshTimerId !== null;
    }

    function schedule() {
        const previewBtn = getPreviewButton();
        if (!previewBtn || previewBtn.disabled) {
            return false;
        }

        const harmonizationStatus = getStatusElement();
        if (harmonizationStatus) {
            harmonizationStatus.classList.remove('d-none', 'text-danger', 'text-warning', 'text-success');
            harmonizationStatus.classList.add('text-muted');
            harmonizationStatus.textContent = 'Refreshing merge preview with updated harmonization settings...';
        }

        if (refreshTimerId !== null) {
            window.clearTimeout(refreshTimerId);
        }

        refreshTimerId = window.setTimeout(() => {
            refreshTimerId = null;
            previewBtn.click();
        }, refreshDelayMs);

        return true;
    }

    return {
        isPending,
        schedule,
    };
}
